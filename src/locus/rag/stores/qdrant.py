# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Qdrant vector store.

Qdrant is a purpose-built vector database with rich filtering,
payload storage, and multiple distance metrics.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from locus.rag.stores.base import (
    BaseVectorStore,
    Document,
    SearchResult,
    VectorStoreConfig,
)


# Fixed namespace for deriving deterministic Qdrant point IDs from
# caller-supplied doc_id strings. Using UUIDv5 instead of MD5 avoids
# collision-based payload-poisoning where an attacker-controlled doc_id
# overwrites a legitimate document by engineering a hash collision.
_QDRANT_DOC_ID_NAMESPACE = uuid.UUID("6f0c1b9e-2a9b-4e2a-9f1e-00000c0a5a5a")


if TYPE_CHECKING:
    from qdrant_client import AsyncQdrantClient


class QdrantVectorConfig(BaseModel):
    """Configuration for Qdrant Vector Store."""

    url: str = Field(
        default="http://localhost:6333",
        description="Qdrant server URL",
    )
    api_key: str | None = Field(
        default=None,
        description="Qdrant API key (for Qdrant Cloud)",
    )
    collection_name: str = Field(
        default="locus_vectors",
        description="Collection name",
    )
    dimension: int = Field(default=1024, description="Vector dimension")
    distance_metric: str = Field(
        default="Cosine",
        description="Distance metric: Cosine, Euclid, Dot",
    )

    # HNSW settings
    on_disk: bool = Field(default=False, description="Store vectors on disk")
    hnsw_ef_construct: int = Field(default=100, description="HNSW ef_construct")
    hnsw_m: int = Field(default=16, description="HNSW M parameter")


class QdrantVectorStore(BaseModel, BaseVectorStore):
    """
    Qdrant vector store.

    Qdrant is a purpose-built vector database with:
    - Rich filtering by payload fields
    - Multiple distance metrics
    - Efficient HNSW indexing
    - Scalar quantization for memory efficiency

    Example:
        >>> store = QdrantVectorStore(
        ...     url="http://localhost:6333",
        ...     collection_name="my_docs",
        ...     dimension=1024,
        ... )
        >>> await store.add(document)
        >>> results = await store.search(query_embedding, limit=5)

    Example with Qdrant Cloud:
        >>> store = QdrantVectorStore(
        ...     url="https://xxx.qdrant.io",
        ...     api_key="your-api-key",
        ... )
    """

    qdrant_config: QdrantVectorConfig = Field(default_factory=QdrantVectorConfig)
    _client: AsyncQdrantClient | None = None
    _initialized: bool = False

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
        collection_name: str = "locus_vectors",
        dimension: int = 1024,
        distance_metric: str = "Cosine",
        **kwargs: Any,
    ) -> None:
        qdrant_config = QdrantVectorConfig(
            url=url,
            api_key=api_key,
            collection_name=collection_name,
            dimension=dimension,
            distance_metric=distance_metric,
            **kwargs,
        )
        super().__init__(qdrant_config=qdrant_config)

    @property
    def config(self) -> VectorStoreConfig:
        """Get store configuration."""
        return VectorStoreConfig(
            dimension=self.qdrant_config.dimension,
            distance_metric=self.qdrant_config.distance_metric.lower(),
            index_type="hnsw",
        )

    async def _get_client(self) -> AsyncQdrantClient:
        """Get or create Qdrant client."""
        if self._client is None:
            try:
                from qdrant_client import AsyncQdrantClient
            except ImportError as e:
                raise ImportError(
                    "QdrantVectorStore requires 'qdrant-client'. "
                    "Install with: pip install qdrant-client"
                ) from e

            self._client = AsyncQdrantClient(
                url=self.qdrant_config.url,
                api_key=self.qdrant_config.api_key,
            )

        return self._client

    async def _ensure_collection(self) -> None:
        """Create collection if not exists."""
        if self._initialized:
            return

        try:
            from qdrant_client.models import Distance, VectorParams
        except ImportError as e:
            raise ImportError(
                "QdrantVectorStore requires 'qdrant-client'. "
                "Install with: pip install qdrant-client"
            ) from e

        client = await self._get_client()

        # Check if collection exists
        collections = await client.get_collections()
        collection_names = [c.name for c in collections.collections]

        if self.qdrant_config.collection_name not in collection_names:
            # Map distance metric
            distance_map = {
                "cosine": Distance.COSINE,
                "euclid": Distance.EUCLID,
                "dot": Distance.DOT,
            }
            distance = distance_map.get(
                self.qdrant_config.distance_metric.lower(),
                Distance.COSINE,
            )

            await client.create_collection(
                collection_name=self.qdrant_config.collection_name,
                vectors_config=VectorParams(
                    size=self.qdrant_config.dimension,
                    distance=distance,
                    on_disk=self.qdrant_config.on_disk,
                ),
            )

        self._initialized = True

    def _to_uuid(self, doc_id: str) -> str:
        """Convert document ID to valid UUID format for Qdrant.

        Qdrant requires UUIDs or unsigned integers for point IDs.
        We generate a deterministic UUID from the document ID using
        UUIDv5 under a fixed namespace (collision-resistant SHA-1 vs
        collision-broken MD5, and does not trip FIPS mode).
        """
        # If already a valid UUID, use it
        try:
            UUID(doc_id)
            return doc_id
        except ValueError:
            pass

        return str(uuid.uuid5(_QDRANT_DOC_ID_NAMESPACE, doc_id))

    async def add(self, document: Document) -> str:
        """Add a document."""
        await self._ensure_collection()

        try:
            from qdrant_client.models import PointStruct
        except ImportError as e:
            raise ImportError(
                "QdrantVectorStore requires 'qdrant-client'. "
                "Install with: pip install qdrant-client"
            ) from e

        client = await self._get_client()

        doc_id = document.id or uuid4().hex
        qdrant_id = self._to_uuid(doc_id)

        if document.embedding is None:
            raise ValueError("Document must have an embedding")

        point = PointStruct(
            id=qdrant_id,
            vector=document.embedding,
            payload={
                "doc_id": doc_id,  # Store original ID in payload
                "content": document.content,
                "metadata": document.metadata,
                "created_at": document.created_at.isoformat(),
            },
        )

        await client.upsert(
            collection_name=self.qdrant_config.collection_name,
            points=[point],
        )

        return doc_id

    async def add_batch(self, documents: list[Document]) -> list[str]:
        """Add multiple documents."""
        await self._ensure_collection()

        try:
            from qdrant_client.models import PointStruct
        except ImportError as e:
            raise ImportError(
                "QdrantVectorStore requires 'qdrant-client'. "
                "Install with: pip install qdrant-client"
            ) from e

        client = await self._get_client()

        points = []
        ids = []

        for doc in documents:
            doc_id = doc.id or uuid4().hex
            qdrant_id = self._to_uuid(doc_id)
            ids.append(doc_id)

            if doc.embedding is None:
                raise ValueError(f"Document {doc_id} must have an embedding")

            points.append(
                PointStruct(
                    id=qdrant_id,
                    vector=doc.embedding,
                    payload={
                        "doc_id": doc_id,  # Store original ID in payload
                        "content": doc.content,
                        "metadata": doc.metadata,
                        "created_at": doc.created_at.isoformat(),
                    },
                )
            )

        if points:
            await client.upsert(
                collection_name=self.qdrant_config.collection_name,
                points=points,
            )

        return ids

    async def get(self, doc_id: str) -> Document | None:
        """Get a document by ID."""
        await self._ensure_collection()
        client = await self._get_client()
        qdrant_id = self._to_uuid(doc_id)

        try:
            results = await client.retrieve(
                collection_name=self.qdrant_config.collection_name,
                ids=[qdrant_id],
                with_vectors=True,
            )
        except Exception:  # noqa: BLE001 — vector store lookup/delete; return falsy on any failure
            return None

        if not results:
            return None

        point = results[0]
        payload = point.payload or {}

        return Document(
            id=payload.get("doc_id", str(point.id)),
            content=payload.get("content", ""),
            embedding=list(point.vector) if point.vector else None,
            metadata=payload.get("metadata", {}),
            created_at=datetime.fromisoformat(payload["created_at"])
            if payload.get("created_at")
            else datetime.now(UTC),
        )

    async def delete(self, doc_id: str) -> bool:
        """Delete a document."""
        await self._ensure_collection()

        try:
            from qdrant_client.models import PointIdsList
        except ImportError as e:
            raise ImportError(
                "QdrantVectorStore requires 'qdrant-client'. "
                "Install with: pip install qdrant-client"
            ) from e

        client = await self._get_client()
        qdrant_id = self._to_uuid(doc_id)

        try:
            await client.delete(
                collection_name=self.qdrant_config.collection_name,
                points_selector=PointIdsList(points=[qdrant_id]),
            )
            return True
        except Exception:  # noqa: BLE001 — vector store lookup/delete; return falsy on any failure
            return False

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        threshold: float | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents."""
        await self._ensure_collection()
        client = await self._get_client()

        # Build filter if metadata provided
        query_filter = None
        if metadata_filter:
            try:
                from qdrant_client.models import FieldCondition, Filter, MatchValue
            except ImportError:
                pass
            else:
                conditions = []
                for key, value in metadata_filter.items():
                    conditions.append(
                        FieldCondition(
                            key=f"metadata.{key}",
                            match=MatchValue(value=value),
                        )
                    )
                query_filter = Filter(must=conditions)

        # Search using query_points (newer API)

        search_result = await client.query_points(
            collection_name=self.qdrant_config.collection_name,
            query=query_embedding,
            limit=limit,
            query_filter=query_filter,
            with_vectors=True,
        )

        # Get points from result
        points = search_result.points if hasattr(search_result, "points") else search_result

        results = []
        for point in points:
            # Qdrant returns similarity score (higher is better for cosine)
            score = point.score

            if threshold is not None and score < threshold:
                continue

            payload = point.payload or {}

            doc = Document(
                id=payload.get("doc_id", str(point.id)),
                content=payload.get("content", ""),
                embedding=list(point.vector) if point.vector else None,
                metadata=payload.get("metadata", {}),
                created_at=datetime.fromisoformat(payload["created_at"])
                if payload.get("created_at")
                else datetime.now(UTC),
            )

            results.append(
                SearchResult(
                    document=doc,
                    score=score,
                    distance=1.0 - score
                    if self.qdrant_config.distance_metric.lower() == "cosine"
                    else None,
                )
            )

        return results

    async def count(self) -> int:
        """Count documents."""
        await self._ensure_collection()
        client = await self._get_client()

        info = await client.get_collection(collection_name=self.qdrant_config.collection_name)
        return info.points_count or 0

    async def clear(self) -> int:
        """Delete all documents."""
        await self._ensure_collection()
        client = await self._get_client()

        count = await self.count()

        # Delete and recreate collection
        await client.delete_collection(collection_name=self.qdrant_config.collection_name)
        self._initialized = False
        await self._ensure_collection()

        return count

    async def close(self) -> None:
        """Close the client."""
        if self._client:
            await self._client.close()
            self._client = None

    def __repr__(self) -> str:
        return f"QdrantVectorStore(collection={self.qdrant_config.collection_name!r})"
