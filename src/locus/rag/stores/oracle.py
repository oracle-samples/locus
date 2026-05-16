# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Oracle 26ai Vector Store - Native vector support.

Uses Oracle Database 23ai/26ai with native VECTOR data type.
Requires python-oracledb in thin mode (no Oracle Client needed).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel, Field, SecretStr

from locus.rag.stores.base import (
    BaseVectorStore,
    Document,
    SearchResult,
    VectorStoreConfig,
)


if TYPE_CHECKING:
    import oracledb


_SAFE_SQL_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_$#]{0,127}$")
_ALLOWED_DISTANCE_METRICS = frozenset({"COSINE", "DOT", "EUCLIDEAN", "MANHATTAN", "HAMMING"})


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


class OracleVectorConfig(BaseModel):
    """Configuration for Oracle Vector Store."""

    # Connection options
    dsn: str | None = None
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
    table_name: str = "locus_vectors"
    schema_name: str | None = None

    # Column overrides — let an existing table written by another tool be read
    # without re-ingestion. The langchain_oracledb.OracleVS schema, for
    # example, uses ``text`` instead of ``content`` and has no ``created_at``
    # column. Set ``content_column="text"`` and ``created_at_column=None`` to
    # point at one of those tables.
    id_column: str = "id"
    content_column: str = "content"
    embedding_column: str = "embedding"
    metadata_column: str = "metadata"
    created_at_column: str | None = "created_at"

    # When False, ``_ensure_table`` won't issue CREATE statements — useful for
    # read-only attachment to a foreign-schema table populated by a different
    # ingestion pipeline.
    auto_create_table: bool = True

    # Vector settings
    dimension: int = 1024  # Cohere embed-v3 default
    distance_metric: str = "COSINE"  # COSINE, DOT, EUCLIDEAN

    # Pool settings
    min_pool_size: int = 1
    max_pool_size: int = 5

    def model_post_init(self, __context: Any) -> None:
        """Validate SQL identifiers and distance metric to prevent injection."""
        _validate_sql_identifier(self.table_name, "table_name")
        if self.schema_name is not None:
            _validate_sql_identifier(self.schema_name, "schema_name")
        for col_field in (
            "id_column",
            "content_column",
            "embedding_column",
            "metadata_column",
        ):
            _validate_sql_identifier(getattr(self, col_field), col_field)
        if self.created_at_column is not None:
            _validate_sql_identifier(self.created_at_column, "created_at_column")
        if self.distance_metric.upper() not in _ALLOWED_DISTANCE_METRICS:
            raise ValueError(
                f"Invalid distance_metric: {self.distance_metric!r}. "
                f"Must be one of: {sorted(_ALLOWED_DISTANCE_METRICS)}"
            )


class OracleVectorStore(BaseModel, BaseVectorStore):
    """
    Oracle 26ai Vector Store with native VECTOR support.

    Uses Oracle Database 23ai/26ai's native VECTOR data type for
    efficient similarity search. Supports cosine, dot product,
    and Euclidean distance metrics.

    Example with DSN:
        >>> store = OracleVectorStore(
        ...     dsn="mydb_high",
        ...     user="admin",
        ...     password="secret",
        ...     dimension=1024,
        ... )
        >>> await store.add(document)
        >>> results = await store.search(query_embedding, limit=5)

    Example with connection string:
        >>> store = OracleVectorStore(
        ...     host="adb.us-ashburn-1.oraclecloud.com",
        ...     port=1522,
        ...     service_name="xxx_high.adb.oraclecloud.com",
        ... )

    Example attaching to a langchain_oracledb-formatted table (column
    names differ, no created_at column, table already exists):
        >>> store = OracleVectorStore(
        ...     dsn="mydb_low",
        ...     user="ADMIN",
        ...     password=adb_password,
        ...     wallet_location="~/.oci/wallets/mydb",
        ...     table_name="VECTOR_DOCUMENTS",
        ...     content_column="text",
        ...     created_at_column=None,
        ...     auto_create_table=False,  # don't try to CREATE TABLE
        ...     dimension=1536,  # match the existing column
        ... )
    """

    oracle_config: OracleVectorConfig = Field(default_factory=OracleVectorConfig)
    _pool: oracledb.AsyncConnectionPool | None = None
    _initialized: bool = False

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        dsn: str | None = None,
        user: str = "admin",
        password: str | SecretStr = "",
        host: str | None = None,
        port: int = 1521,
        service_name: str | None = None,
        dimension: int = 1024,
        distance_metric: str = "COSINE",
        **kwargs: Any,
    ) -> None:
        oracle_config = OracleVectorConfig(
            dsn=dsn,
            user=user,
            password=SecretStr(password) if isinstance(password, str) else password,
            host=host,
            port=port,
            service_name=service_name,
            dimension=dimension,
            distance_metric=distance_metric,
            **kwargs,
        )
        super().__init__(oracle_config=oracle_config)

    @property
    def config(self) -> VectorStoreConfig:
        """Get store configuration."""
        return VectorStoreConfig(
            dimension=self.oracle_config.dimension,
            distance_metric=self.oracle_config.distance_metric.lower(),
            index_type="hnsw",
        )

    async def _get_pool(self) -> oracledb.AsyncConnectionPool:
        """Get or create connection pool."""
        if self._pool is None:
            try:
                import oracledb
            except ImportError as e:
                raise ImportError(
                    "OracleVectorStore requires the 'oracledb' package. "
                    "Install with: pip install oracledb"
                ) from e

            # Build DSN if not provided
            dsn = self.oracle_config.dsn
            if dsn is None and self.oracle_config.host and self.oracle_config.service_name:
                dsn = oracledb.makedsn(
                    self.oracle_config.host,
                    self.oracle_config.port,
                    service_name=self.oracle_config.service_name,
                )

            # Configure wallet if provided
            params = {}
            if self.oracle_config.wallet_location:
                params["config_dir"] = self.oracle_config.wallet_location
                params["wallet_location"] = self.oracle_config.wallet_location
                if self.oracle_config.wallet_password:
                    params["wallet_password"] = (
                        self.oracle_config.wallet_password.get_secret_value()
                    )

            self._pool = oracledb.create_pool_async(
                user=self.oracle_config.user,
                password=self.oracle_config.password.get_secret_value(),
                dsn=dsn,
                min=self.oracle_config.min_pool_size,
                max=self.oracle_config.max_pool_size,
                **params,
            )

        return self._pool

    @property
    def _full_table_name(self) -> str:
        """Get fully qualified table name."""
        if self.oracle_config.schema_name:
            return f"{self.oracle_config.schema_name}.{self.oracle_config.table_name}"
        return self.oracle_config.table_name

    async def _ensure_table(self) -> None:
        """Create table if not exists, unless ``auto_create_table=False``."""
        if self._initialized:
            return

        pool = await self._get_pool()
        cfg = self.oracle_config
        dim = cfg.dimension
        id_col = cfg.id_column
        content_col = cfg.content_column
        embedding_col = cfg.embedding_column
        metadata_col = cfg.metadata_column
        created_col = cfg.created_at_column

        async with pool.acquire() as conn, conn.cursor() as cursor:
            # Check if table exists
            await cursor.execute(
                """
                    SELECT COUNT(*) FROM user_tables
                    WHERE table_name = UPPER(:table_name)
                    """,
                {"table_name": cfg.table_name},
            )
            result = await cursor.fetchone()
            table_exists = result[0] > 0 if result else False

            if not table_exists and cfg.auto_create_table:
                # Create table with VECTOR column (Oracle 23ai/26ai)
                created_at_ddl = (
                    f", {created_col} TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP"
                    if created_col
                    else ""
                )
                await cursor.execute(f"""
                        CREATE TABLE {self._full_table_name} (
                            {id_col} VARCHAR2(255) PRIMARY KEY,
                            {content_col} CLOB,
                            {embedding_col} VECTOR({dim}, FLOAT32),
                            {metadata_col} CLOB DEFAULT '{{}}'
                                CHECK ({metadata_col} IS JSON)
                            {created_at_ddl}
                        )
                    """)

                # Create vector index for fast similarity search
                # Using IVF index for large datasets
                await cursor.execute(f"""
                        CREATE VECTOR INDEX idx_{cfg.table_name}_vec
                        ON {self._full_table_name} ({embedding_col})
                        ORGANIZATION NEIGHBOR PARTITIONS
                        WITH DISTANCE {cfg.distance_metric}
                    """)

                if created_col:
                    await cursor.execute(f"""
                            CREATE INDEX idx_{cfg.table_name}_created
                            ON {self._full_table_name} ({created_col} DESC)
                        """)

                await conn.commit()
            # When auto_create_table=False and the table is missing, we leave
            # it for the first SQL operation to surface ORA-00942 with full
            # table context.

        self._initialized = True

    def _vector_to_string(self, embedding: list[float]) -> str:
        """Convert embedding list to Oracle VECTOR string format."""
        return "[" + ",".join(str(f) for f in embedding) + "]"

    def _insert_sql(self) -> str:
        """Build an INSERT statement that respects column-name overrides."""
        cfg = self.oracle_config
        cols = [cfg.id_column, cfg.content_column, cfg.embedding_column, cfg.metadata_column]
        values = [":id", ":content", "TO_VECTOR(:embedding)", ":metadata"]
        if cfg.created_at_column:
            cols.append(cfg.created_at_column)
            values.append(":created_at")
        return (
            f"INSERT INTO {self._full_table_name} ({', '.join(cols)}) VALUES ({', '.join(values)})"
        )

    def _insert_params(self, doc_id: str, doc: Document) -> dict[str, Any]:
        params: dict[str, Any] = {
            "id": doc_id,
            "content": doc.content,
            "embedding": self._vector_to_string(doc.embedding or []),
            "metadata": json.dumps(doc.metadata),
        }
        if self.oracle_config.created_at_column:
            params["created_at"] = doc.created_at
        return params

    async def add(self, document: Document) -> str:
        """Add a document with embedding."""
        await self._ensure_table()
        pool = await self._get_pool()

        doc_id = document.id or uuid4().hex

        if document.embedding is None:
            raise ValueError("Document must have an embedding")

        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(self._insert_sql(), self._insert_params(doc_id, document))
            await conn.commit()

        return doc_id

    async def add_batch(self, documents: list[Document]) -> list[str]:
        """Add multiple documents."""
        await self._ensure_table()
        pool = await self._get_pool()

        ids = []
        sql = self._insert_sql()
        async with pool.acquire() as conn, conn.cursor() as cursor:
            for doc in documents:
                doc_id = doc.id or uuid4().hex
                ids.append(doc_id)

                if doc.embedding is None:
                    raise ValueError(f"Document {doc_id} must have an embedding")

                await cursor.execute(sql, self._insert_params(doc_id, doc))
            await conn.commit()

        return ids

    def _select_columns_sql(self, *, with_distance: str | None = None) -> str:
        """Build the SELECT clause, optionally with a distance expression."""
        cfg = self.oracle_config
        parts = [
            f"{cfg.id_column} AS id_",
            f"{cfg.content_column} AS content_",
            f"VECTOR_SERIALIZE({cfg.embedding_column}) AS embedding_",
            f"{cfg.metadata_column} AS metadata_",
        ]
        if cfg.created_at_column:
            parts.append(f"{cfg.created_at_column} AS created_at_")
        else:
            parts.append("NULL AS created_at_")
        if with_distance:
            parts.append(f"{with_distance} AS distance_")
        return ", ".join(parts)

    async def get(self, doc_id: str) -> Document | None:
        """Get a document by ID."""
        await self._ensure_table()
        pool = await self._get_pool()

        cfg = self.oracle_config
        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(
                f"""
                SELECT {self._select_columns_sql()}
                FROM {self._full_table_name}
                WHERE {cfg.id_column} = :id
                """,
                {"id": doc_id},
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        # Parse embedding from serialized format
        embedding_str = row[2]
        if embedding_str:
            # Remove brackets and parse floats
            embedding_str = embedding_str.strip("[]")
            embedding = [float(x) for x in embedding_str.split(",")]
        else:
            embedding = None

        # Parse metadata (handle async LOB)
        metadata = row[3]
        if hasattr(metadata, "read"):
            metadata = await metadata.read()
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}

        # Parse content (handle async LOB)
        content = row[1]
        if hasattr(content, "read"):
            content = await content.read()

        return Document(
            id=row[0],
            content=content,
            embedding=embedding,
            metadata=metadata,
            created_at=row[4] if row[4] else datetime.now(UTC),
        )

    async def delete(self, doc_id: str) -> bool:
        """Delete a document."""
        await self._ensure_table()
        pool = await self._get_pool()

        cfg = self.oracle_config
        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(
                f"DELETE FROM {self._full_table_name} WHERE {cfg.id_column} = :id",
                {"id": doc_id},
            )
            deleted: bool = cursor.rowcount > 0
            await conn.commit()

        return deleted

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        threshold: float | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents using vector similarity.

        Uses Oracle's VECTOR_DISTANCE function for efficient similarity search.
        """
        # Some LLMs (notably gpt-5.x via tool calls) JSON-encode floats as
        # strings (e.g. "0.5"); coerce defensively so the `score < threshold`
        # comparison below doesn't TypeError.
        if isinstance(threshold, str):
            try:
                threshold = float(threshold)
            except ValueError:
                threshold = None
        await self._ensure_table()
        pool = await self._get_pool()

        cfg = self.oracle_config
        # Build distance function based on metric
        metric = cfg.distance_metric.upper()
        distance_func = f"VECTOR_DISTANCE({cfg.embedding_column}, TO_VECTOR(:query_vec), {metric})"

        # Build WHERE clause for metadata filtering
        where_clauses = []
        params: dict[str, Any] = {
            "query_vec": self._vector_to_string(query_embedding),
            "limit": limit,
        }

        if metadata_filter:
            for key, value in metadata_filter.items():
                if not key.isidentifier():
                    msg = f"Invalid metadata filter key: {key!r}"
                    raise ValueError(msg)
                param_name = f"meta_{key}"
                where_clauses.append(
                    f"JSON_VALUE({cfg.metadata_column}, '$.{key}') = :{param_name}"
                )
                params[param_name] = str(value)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        # For cosine distance, lower is better (0 = identical)
        # Convert to similarity score: 1 - distance for cosine
        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(
                f"""
                SELECT {self._select_columns_sql(with_distance=distance_func)}
                FROM {self._full_table_name}
                {where_sql}
                ORDER BY distance_ ASC
                FETCH FIRST :limit ROWS ONLY
                """,
                params,
            )
            rows = await cursor.fetchall()

        results = []
        for row in rows:
            distance = row[5]

            # Convert distance to similarity score (0-1, higher is better)
            if metric == "COSINE":
                # Cosine distance is 0-2, convert to similarity
                score = 1.0 - (distance / 2.0)
            elif metric == "DOT":
                # Dot product: higher is better, normalize
                score = max(0.0, min(1.0, (distance + 1.0) / 2.0))
            else:  # EUCLIDEAN
                # Euclidean: lower is better, use exponential decay
                score = 1.0 / (1.0 + distance)

            # Apply threshold filter
            if threshold is not None and score < threshold:
                continue

            # Parse embedding
            embedding_str = row[2]
            if embedding_str:
                embedding_str = embedding_str.strip("[]")
                embedding = [float(x) for x in embedding_str.split(",")]
            else:
                embedding = None

            # Parse metadata (handle async LOB)
            metadata = row[3]
            if hasattr(metadata, "read"):
                metadata = await metadata.read()
            if isinstance(metadata, str):
                metadata = json.loads(metadata) if metadata else {}

            # Parse content (handle async LOB)
            content = row[1]
            if hasattr(content, "read"):
                content = await content.read()

            doc = Document(
                id=row[0],
                content=content,
                embedding=embedding,
                metadata=metadata,
                created_at=row[4] if row[4] else datetime.now(UTC),
            )

            results.append(
                SearchResult(
                    document=doc,
                    score=score,
                    distance=distance,
                )
            )

        return results

    async def count(self) -> int:
        """Count documents in store."""
        await self._ensure_table()
        pool = await self._get_pool()

        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(f"SELECT COUNT(*) FROM {self._full_table_name}")
            row = await cursor.fetchone()

        return row[0] if row else 0

    async def clear(self) -> int:
        """Delete all documents."""
        await self._ensure_table()
        pool = await self._get_pool()

        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(f"SELECT COUNT(*) FROM {self._full_table_name}")
            row = await cursor.fetchone()
            count = row[0] if row else 0

            await cursor.execute(f"TRUNCATE TABLE {self._full_table_name}")
            await conn.commit()

        return count

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    def __repr__(self) -> str:
        if self.oracle_config.dsn:
            return f"OracleVectorStore(dsn={self.oracle_config.dsn!r})"
        if self.oracle_config.host:
            return f"OracleVectorStore(host={self.oracle_config.host!r})"
        return "OracleVectorStore()"
