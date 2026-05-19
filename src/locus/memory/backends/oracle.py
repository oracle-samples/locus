# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Oracle Database checkpoint backend - 100% Pydantic.

Supports Oracle Autonomous Database (including AI 26 with vector support).
Uses python-oracledb in thin mode (no Oracle Client required).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, SecretStr

from locus.core.state import AgentState
from locus.memory.backends._oracle_config import (
    OracleConfig,
)


if TYPE_CHECKING:
    import oracledb


class OracleBackend(BaseModel):
    """
    Oracle Database checkpoint backend.

    Production-grade persistent storage with JSON support and full-text search.

    Features:
    - Connection pooling
    - JSON column storage with search
    - Metadata indexing
    - Vacuum (cleanup old checkpoints)
    - Works with Autonomous Database (wallet-based auth)

    Example with DSN:
        >>> backend = OracleBackend(
        ...     dsn="mydb_high",  # TNS name from tnsnames.ora
        ...     user="admin",
        ...     password="secret",
        ...     wallet_location="/path/to/wallet",
        ... )
        >>> await backend.save("thread_1", state.model_dump())

    Example with connection string:
        >>> backend = OracleBackend(
        ...     host="adb.us-ashburn-1.oraclecloud.com",
        ...     port=1522,
        ...     service_name="xxx_high.adb.oraclecloud.com",
        ...     user="admin",
        ...     password="secret",
        ... )
    """

    config: OracleConfig = Field(default_factory=OracleConfig)
    _pool: oracledb.AsyncConnectionPool | None = None
    _pool_loop: Any = None  # asyncio.AbstractEventLoop the pool is bound to
    _initialized: bool = False

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        dsn: str | None = None,
        user: str = "admin",
        password: str | SecretStr = "",
        wallet_location: str | None = None,
        wallet_password: str | SecretStr | None = None,
        host: str | None = None,
        port: int = 1521,
        service_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        config = OracleConfig(
            dsn=dsn,
            user=user,
            password=SecretStr(password) if isinstance(password, str) else password,
            wallet_location=wallet_location,
            wallet_password=SecretStr(wallet_password)
            if isinstance(wallet_password, str)
            else wallet_password,
            host=host,
            port=port,
            service_name=service_name,
            **kwargs,
        )
        super().__init__(config=config)

    async def _get_pool(self) -> oracledb.AsyncConnectionPool:
        """Get or create the connection pool, rebuilding on loop change."""
        from locus._oracle_pool_cache import get_pool

        def _build() -> oracledb.AsyncConnectionPool:
            try:
                import oracledb
            except ImportError as e:
                raise ImportError(
                    "OracleBackend requires the 'oracledb' package. "
                    "Install with: pip install oracledb"
                ) from e

            dsn = self.config.dsn
            if dsn is None and self.config.host and self.config.service_name:
                dsn = oracledb.makedsn(
                    self.config.host,
                    self.config.port,
                    service_name=self.config.service_name,
                )

            params: dict[str, Any] = {}
            if self.config.wallet_location:
                params["config_dir"] = self.config.wallet_location
                params["wallet_location"] = self.config.wallet_location
                if self.config.wallet_password:
                    params["wallet_password"] = self.config.wallet_password.get_secret_value()

            return oracledb.create_pool_async(
                user=self.config.user,
                password=self.config.password.get_secret_value(),
                dsn=dsn,
                min=self.config.min_pool_size,
                max=self.config.max_pool_size,
                **params,
            )

        return await get_pool(self, _build)

    @property
    def _full_table_name(self) -> str:
        """Get fully qualified table name."""
        if self.config.schema_name:
            return f"{self.config.schema_name}.{self.config.table_name}"
        return self.config.table_name

    async def _ensure_table(self) -> None:
        """Create table if not exists."""
        if self._initialized:
            return

        pool = await self._get_pool()

        async with pool.acquire() as conn, conn.cursor() as cursor:
            # Check if table exists
            await cursor.execute(
                """
                    SELECT COUNT(*) FROM user_tables
                    WHERE table_name = UPPER(:table_name)
                    """,
                {"table_name": self.config.table_name},
            )
            result = await cursor.fetchone()
            table_exists = result[0] > 0 if result else False

            if not table_exists:
                # Create table with JSON column
                # Note: DEFAULT must come before CHECK constraint in Oracle
                await cursor.execute(f"""
                        CREATE TABLE {self._full_table_name} (
                            thread_id VARCHAR2(255) PRIMARY KEY,
                            checkpoint_id VARCHAR2(255),
                            data CLOB CHECK (data IS JSON),
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP,
                            metadata CLOB DEFAULT '{{}}' CHECK (metadata IS JSON)
                        )
                    """)

                # Create index on updated_at
                await cursor.execute(f"""
                        CREATE INDEX idx_{self.config.table_name}_updated
                        ON {self._full_table_name} (updated_at DESC)
                    """)

                await conn.commit()

        self._initialized = True

    async def save(
        self,
        state: AgentState,
        thread_id: str,
        checkpoint_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Save agent state to Oracle Database.

        Implements :meth:`BaseCheckpointer.save`. Parameter order is
        ``(state, thread_id, ...)`` to match the abstract — the prior
        ``(thread_id, data, ...)`` signature silently mismatched the
        agent runtime, which calls ``save(state, thread_id)`` and would
        end up trying to bind an :class:`AgentState` to the
        ``VARCHAR2(255) thread_id`` column.

        Args:
            state: Current agent state. Serialized via
                :meth:`AgentState.to_checkpoint` (Pydantic JSON dump).
            thread_id: Thread identifier (column primary key).
            checkpoint_id: Optional checkpoint ID. Generated if omitted.
            metadata: Optional metadata for querying.

        Returns:
            Checkpoint ID.
        """
        await self._ensure_table()
        pool = await self._get_pool()

        from uuid import uuid4

        # Handle both calling conventions:
        #   1. BaseCheckpointer:        save(state, thread_id, ...)
        #   2. StorageBackendAdapter:   save(storage_key_str, data_dict, ...)
        # Detected by the type of the first arg.
        if isinstance(state, str) and isinstance(thread_id, dict):
            state, thread_id = thread_id, state  # swap to (data_dict, key_str)

        checkpoint_id = checkpoint_id or uuid4().hex
        data = state.to_checkpoint() if isinstance(state, AgentState) else state

        async with pool.acquire() as conn, conn.cursor() as cursor:
            # Pin :data / :metadata to CLOB so large agent-state payloads
            # don't hit ORA-01461 (character-to-LOB conversion) when
            # oracledb thin mode tries to bind them as VARCHAR2. Mirrors
            # the temporary-BLOB binding pattern langgraph-oracledb adopted
            # for its checkpoint blob columns (oracle/langchain-oracle#224).
            import oracledb as _oracledb

            cursor.setinputsizes(
                data=_oracledb.DB_TYPE_CLOB,
                metadata=_oracledb.DB_TYPE_CLOB,
            )
            # Use MERGE for upsert
            await cursor.execute(
                f"""
                    MERGE INTO {self._full_table_name} t
                    USING (SELECT :thread_id AS thread_id FROM dual) s
                    ON (t.thread_id = s.thread_id)
                    WHEN MATCHED THEN
                        UPDATE SET
                            checkpoint_id = :checkpoint_id,
                            data = :data,
                            updated_at = SYSTIMESTAMP,
                            metadata = :metadata
                    WHEN NOT MATCHED THEN
                        INSERT (thread_id, checkpoint_id, data, metadata)
                        VALUES (:thread_id, :checkpoint_id, :data, :metadata)
                    """,
                {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                    "data": json.dumps(data, default=str),
                    "metadata": json.dumps(metadata or {}),
                },
            )
            await conn.commit()

        return checkpoint_id

    async def load(
        self,
        thread_id: str,
        checkpoint_id: str | None = None,
    ) -> dict | None:
        """Load a saved payload from Oracle Database.

        Returns the raw dict payload as written by :meth:`save`. The
        :class:`StorageBackendAdapter` wrapper rehydrates this into an
        :class:`AgentState` for the agent runtime; callers that hold a
        bare ``OracleBackend`` get the dict directly.

        ``checkpoint_id`` is accepted for signature parity but ignored —
        this backend stores one row per ``thread_id`` (MERGE upsert), so
        latest-state is the only retrievable checkpoint.
        """
        del checkpoint_id  # one-row-per-thread; arg present for parity
        await self._ensure_table()
        pool = await self._get_pool()

        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(
                f"SELECT data FROM {self._full_table_name} WHERE thread_id = :thread_id",
                {"thread_id": thread_id},
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        # Handle CLOB - read if needed
        data = row[0]
        if hasattr(data, "read"):
            data = data.read()

        # oracledb might already return JSON as dict
        if isinstance(data, dict):
            return data
        loaded: dict = json.loads(data)
        return loaded

    async def delete(self, thread_id: str) -> bool:
        """Delete checkpoint from Oracle Database."""
        await self._ensure_table()
        pool = await self._get_pool()

        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(
                f"DELETE FROM {self._full_table_name} WHERE thread_id = :thread_id",
                {"thread_id": thread_id},
            )
            deleted: bool = cursor.rowcount > 0
            await conn.commit()

        return deleted

    async def exists(self, thread_id: str) -> bool:
        """Check if checkpoint exists."""
        await self._ensure_table()
        pool = await self._get_pool()

        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(
                f"SELECT 1 FROM {self._full_table_name} WHERE thread_id = :thread_id",
                {"thread_id": thread_id},
            )
            row = await cursor.fetchone()

        return row is not None

    async def list_threads(
        self,
        limit: int = 100,
        offset: int = 0,
        pattern: str = "%",
    ) -> list[str]:
        """List all thread IDs matching pattern."""
        await self._ensure_table()
        pool = await self._get_pool()

        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(
                f"""
                    SELECT thread_id FROM {self._full_table_name}
                    WHERE thread_id LIKE :pattern
                    ORDER BY updated_at DESC
                    OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
                    """,
                {"pattern": pattern, "limit": limit, "offset": offset},
            )
            rows = await cursor.fetchall()

        return [row[0] for row in rows]

    async def get_metadata(self, thread_id: str) -> dict[str, Any] | None:
        """Get checkpoint metadata."""
        await self._ensure_table()
        pool = await self._get_pool()

        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(
                f"""
                    SELECT checkpoint_id, created_at, updated_at, metadata
                    FROM {self._full_table_name}
                    WHERE thread_id = :thread_id
                    """,
                {"thread_id": thread_id},
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        metadata = row[3]
        if hasattr(metadata, "read"):
            metadata = metadata.read()
        # oracledb might already return JSON as dict
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}
        elif metadata is None:
            metadata = {}

        return {
            "checkpoint_id": row[0],
            "created_at": row[1].isoformat() if row[1] else None,
            "updated_at": row[2].isoformat() if row[2] else None,
            "metadata": metadata,
        }

    async def query_by_metadata(
        self,
        key: str,
        value: Any,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query checkpoints by metadata field.

        Uses Oracle JSON path expressions.
        """
        await self._ensure_table()
        pool = await self._get_pool()

        async with pool.acquire() as conn, conn.cursor() as cursor:
            # Validate key to prevent JSON path injection
            if not key.isidentifier():
                raise ValueError(f"Invalid metadata key: {key!r}")
            # Use JSON_VALUE for querying
            await cursor.execute(
                f"""
                    SELECT thread_id, data, updated_at
                    FROM {self._full_table_name}
                    WHERE JSON_VALUE(metadata, '$.{key}') = :value
                    ORDER BY updated_at DESC
                    FETCH FIRST :limit ROWS ONLY
                    """,
                {"value": str(value), "limit": limit},
            )
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            data = row[1]
            if hasattr(data, "read"):
                data = data.read()
            # oracledb might already return JSON as dict
            if isinstance(data, str):
                data = json.loads(data)
            results.append(
                {
                    "thread_id": row[0],
                    "data": data,
                    "updated_at": row[2].isoformat() if row[2] else None,
                }
            )

        return results

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search checkpoints by content.

        Uses Oracle JSON_TEXTCONTAINS for full-text search within JSON.
        """
        await self._ensure_table()
        pool = await self._get_pool()

        async with pool.acquire() as conn, conn.cursor() as cursor:
            # Simple LIKE search on JSON content
            # For production, use Oracle Text or JSON search index
            await cursor.execute(
                f"""
                    SELECT thread_id, data, updated_at
                    FROM {self._full_table_name}
                    WHERE LOWER(data) LIKE LOWER(:query_pattern)
                    ORDER BY updated_at DESC
                    FETCH FIRST :limit ROWS ONLY
                    """,
                {"query_pattern": f"%{query}%", "limit": limit},
            )
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            data = row[1]
            if hasattr(data, "read"):
                data = data.read()
            # oracledb might already return JSON as dict
            if isinstance(data, str):
                data = json.loads(data)
            results.append(
                {
                    "thread_id": row[0],
                    "data": data,
                    "updated_at": row[2].isoformat() if row[2] else None,
                }
            )

        return results

    async def vacuum(self, older_than_days: int = 30) -> int:
        """
        Delete old checkpoints.

        Args:
            older_than_days: Delete checkpoints older than this

        Returns:
            Number of deleted rows
        """
        await self._ensure_table()
        pool = await self._get_pool()

        async with pool.acquire() as conn, conn.cursor() as cursor:
            # Use NUMTODSINTERVAL for dynamic interval
            await cursor.execute(
                f"""
                    DELETE FROM {self._full_table_name}
                    WHERE updated_at < SYSTIMESTAMP - NUMTODSINTERVAL(:days, 'DAY')
                    """,
                {"days": older_than_days},
            )
            deleted_count: int = cursor.rowcount
            await conn.commit()

        return deleted_count

    async def count(self, pattern: str = "%") -> int:
        """Count checkpoints matching pattern."""
        await self._ensure_table()
        pool = await self._get_pool()

        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(
                f"SELECT COUNT(*) FROM {self._full_table_name} WHERE thread_id LIKE :pattern",
                {"pattern": pattern},
            )
            row = await cursor.fetchone()

        return row[0] if row else 0

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    def __repr__(self) -> str:
        if self.config.dsn:
            return f"OracleBackend(dsn={self.config.dsn!r})"
        if self.config.host:
            return f"OracleBackend(host={self.config.host!r}, service={self.config.service_name!r})"
        return "OracleBackend()"
