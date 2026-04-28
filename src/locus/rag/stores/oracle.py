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
        """Create table if not exists."""
        if self._initialized:
            return

        pool = await self._get_pool()
        dim = self.oracle_config.dimension

        async with pool.acquire() as conn, conn.cursor() as cursor:
            # Check if table exists
            await cursor.execute(
                """
                    SELECT COUNT(*) FROM user_tables
                    WHERE table_name = UPPER(:table_name)
                    """,
                {"table_name": self.oracle_config.table_name},
            )
            result = await cursor.fetchone()
            table_exists = result[0] > 0 if result else False

            if not table_exists:
                # Create table with VECTOR column (Oracle 23ai/26ai)
                await cursor.execute(f"""
                        CREATE TABLE {self._full_table_name} (
                            id VARCHAR2(255) PRIMARY KEY,
                            content CLOB,
                            embedding VECTOR({dim}, FLOAT32),
                            metadata CLOB DEFAULT '{{}}' CHECK (metadata IS JSON),
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP
                        )
                    """)

                # Create vector index for fast similarity search
                # Using IVF index for large datasets
                await cursor.execute(f"""
                        CREATE VECTOR INDEX idx_{self.oracle_config.table_name}_vec
                        ON {self._full_table_name} (embedding)
                        ORGANIZATION NEIGHBOR PARTITIONS
                        WITH DISTANCE {self.oracle_config.distance_metric}
                    """)

                # Create index on created_at for ordering
                await cursor.execute(f"""
                        CREATE INDEX idx_{self.oracle_config.table_name}_created
                        ON {self._full_table_name} (created_at DESC)
                    """)

                await conn.commit()

        self._initialized = True

    def _vector_to_string(self, embedding: list[float]) -> str:
        """Convert embedding list to Oracle VECTOR string format."""
        return "[" + ",".join(str(f) for f in embedding) + "]"

    async def add(self, document: Document) -> str:
        """Add a document with embedding."""
        await self._ensure_table()
        pool = await self._get_pool()

        doc_id = document.id or uuid4().hex

        if document.embedding is None:
            raise ValueError("Document must have an embedding")

        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(
                f"""
                INSERT INTO {self._full_table_name}
                (id, content, embedding, metadata, created_at)
                VALUES (:id, :content, TO_VECTOR(:embedding), :metadata, :created_at)
                """,
                {
                    "id": doc_id,
                    "content": document.content,
                    "embedding": self._vector_to_string(document.embedding),
                    "metadata": json.dumps(document.metadata),
                    "created_at": document.created_at,
                },
            )
            await conn.commit()

        return doc_id

    async def add_batch(self, documents: list[Document]) -> list[str]:
        """Add multiple documents."""
        await self._ensure_table()
        pool = await self._get_pool()

        ids = []
        async with pool.acquire() as conn, conn.cursor() as cursor:
            for doc in documents:
                doc_id = doc.id or uuid4().hex
                ids.append(doc_id)

                if doc.embedding is None:
                    raise ValueError(f"Document {doc_id} must have an embedding")

                await cursor.execute(
                    f"""
                    INSERT INTO {self._full_table_name}
                    (id, content, embedding, metadata, created_at)
                    VALUES (:id, :content, TO_VECTOR(:embedding), :metadata, :created_at)
                    """,
                    {
                        "id": doc_id,
                        "content": doc.content,
                        "embedding": self._vector_to_string(doc.embedding),
                        "metadata": json.dumps(doc.metadata),
                        "created_at": doc.created_at,
                    },
                )
            await conn.commit()

        return ids

    async def get(self, doc_id: str) -> Document | None:
        """Get a document by ID."""
        await self._ensure_table()
        pool = await self._get_pool()

        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(
                f"""
                SELECT id, content, VECTOR_SERIALIZE(embedding) as embedding,
                       metadata, created_at
                FROM {self._full_table_name}
                WHERE id = :id
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

        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(
                f"DELETE FROM {self._full_table_name} WHERE id = :id",
                {"id": doc_id},
            )
            deleted = cursor.rowcount > 0
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
        await self._ensure_table()
        pool = await self._get_pool()

        # Build distance function based on metric
        metric = self.oracle_config.distance_metric.upper()
        distance_func = f"VECTOR_DISTANCE(embedding, TO_VECTOR(:query_vec), {metric})"

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
                where_clauses.append(f"JSON_VALUE(metadata, '$.{key}') = :{param_name}")
                params[param_name] = str(value)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        # For cosine distance, lower is better (0 = identical)
        # Convert to similarity score: 1 - distance for cosine
        async with pool.acquire() as conn, conn.cursor() as cursor:
            await cursor.execute(
                f"""
                SELECT id, content, VECTOR_SERIALIZE(embedding) as embedding,
                       metadata, created_at,
                       {distance_func} as distance
                FROM {self._full_table_name}
                {where_sql}
                ORDER BY distance ASC
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
