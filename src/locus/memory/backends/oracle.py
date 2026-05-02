# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Oracle Database checkpoint backend - 100% Pydantic.

Supports Oracle Autonomous Database (including AI 26 with vector support).
Uses python-oracledb in thin mode (no Oracle Client required).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, SecretStr


if TYPE_CHECKING:
    import oracledb


_SAFE_SQL_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_$#]{0,127}$")


def _validate_sql_identifier(value: str, field_name: str) -> str:
    """Validate that a string is a safe Oracle SQL identifier."""
    if not _SAFE_SQL_IDENTIFIER.match(value):
        msg = (
            f"Invalid {field_name}: {value!r}. "
            "Must start with a letter or underscore and contain only "
            "alphanumeric characters, underscores, $, or # (max 128 chars)."
        )
        raise ValueError(msg)
    return value


class OracleConfig(BaseModel):
    """Configuration for Oracle Database backend."""

    # Connection options
    dsn: str | None = None  # TNS name or connection string
    user: str = "admin"
    password: SecretStr = SecretStr("")

    # For Autonomous Database with wallet
    wallet_location: str | None = None
    wallet_password: SecretStr | None = None

    # Connection string components (alternative to DSN)
    host: str | None = None
    port: int = 1521
    service_name: str | None = None

    # Table settings
    table_name: str = "locus_checkpoints"
    schema_name: str | None = None  # Uses user's default schema if None

    # Pool settings
    min_pool_size: int = 1
    max_pool_size: int = 5

    def model_post_init(self, __context: Any) -> None:
        """Validate SQL identifiers to prevent injection."""
        _validate_sql_identifier(self.table_name, "table_name")
        if self.schema_name is not None:
            _validate_sql_identifier(self.schema_name, "schema_name")


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
        """Get or create connection pool."""
        if self._pool is None:
            try:
                import oracledb
            except ImportError as e:
                raise ImportError(
                    "OracleBackend requires the 'oracledb' package. "
                    "Install with: pip install oracledb"
                ) from e

            # Build DSN if not provided
            dsn = self.config.dsn
            if dsn is None and self.config.host and self.config.service_name:
                dsn = oracledb.makedsn(
                    self.config.host,
                    self.config.port,
                    service_name=self.config.service_name,
                )

            # Configure wallet if provided
            params = {}
            if self.config.wallet_location:
                params["config_dir"] = self.config.wallet_location
                params["wallet_location"] = self.config.wallet_location
                if self.config.wallet_password:
                    params["wallet_password"] = self.config.wallet_password.get_secret_value()

            # Note: create_pool_async returns the pool directly (not a coroutine)
            # The "async" refers to the pool type, not the creation function
            self._pool = oracledb.create_pool_async(
                user=self.config.user,
                password=self.config.password.get_secret_value(),
                dsn=dsn,
                min=self.config.min_pool_size,
                max=self.config.max_pool_size,
                **params,
            )

        return self._pool

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
        thread_id: str,
        data: dict[str, Any],
        checkpoint_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Save checkpoint to Oracle Database.

        Args:
            thread_id: Thread identifier
            data: Checkpoint data
            checkpoint_id: Optional checkpoint ID
            metadata: Optional metadata for querying

        Returns:
            Checkpoint ID
        """
        await self._ensure_table()
        pool = await self._get_pool()

        from uuid import uuid4

        checkpoint_id = checkpoint_id or uuid4().hex

        async with pool.acquire() as conn, conn.cursor() as cursor:
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
                    "data": json.dumps(data),
                    "metadata": json.dumps(metadata or {}),
                },
            )
            await conn.commit()

        return checkpoint_id

    async def load(self, thread_id: str) -> dict[str, Any] | None:
        """Load checkpoint from Oracle Database."""
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
        parsed: dict[str, Any] = json.loads(data)
        return parsed

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
