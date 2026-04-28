# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Pinecone vector store.

Pinecone is a fully managed, cloud-native vector database
designed for production AI applications at scale.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel, Field

from locus.rag.stores.base import (
    BaseVectorStore,
    Document,
    SearchResult,
    VectorStoreConfig,
)


if TYPE_CHECKING:
    from pinecone import Index


class PineconeVectorConfig(BaseModel):
    """Configuration for Pinecone Vector Store."""

    api_key: str = Field(description="Pinecone API key")
    index_name: str = Field(
        default="locus-vectors",
        description="Pinecone index name",
    )
    namespace: str = Field(
        default="",
        description="Namespace within the index",
    )
    dimension: int = Field(default=1536, description="Vector dimension")
    metric: str = Field(
        default="cosine",
        description="Distance metric: cosine, euclidean, dotproduct",
    )

    # Serverless configuration
    cloud: str = Field(default="aws", description="Cloud provider: aws, gcp, azure")
    region: str = Field(default="us-east-1", description="Cloud region")

    # Pod configuration (alternative to serverless)
    environment: str | None = Field(
        default=None,
        description="Pod environment (e.g., 'us-west1-gcp'). If set, uses pods instead of serverless.",
    )
    pod_type: str = Field(default="p1.x1", description="Pod type")
    replicas: int = Field(default=1, description="Number of replicas")


class PineconeVectorStore(BaseModel, BaseVectorStore):
    """
    Pinecone vector store.

    Pinecone is a fully managed vector database with:
    - Serverless or pod-based deployment
    - Automatic scaling and high availability
    - Real-time indexing
    - Rich metadata filtering

    Example (Serverless):
        >>> store = PineconeVectorStore(
        ...     api_key="your-api-key",
        ...     index_name="my-index",
        ...     dimension=1536,
        ...     cloud="aws",
        ...     region="us-east-1",
        ... )
        >>> await store.add(document)
        >>> results = await store.search(query_embedding, limit=5)

    Example (Pod-based):
        >>> store = PineconeVectorStore(
        ...     api_key="your-api-key",
        ...     index_name="my-index",
        ...     environment="us-west1-gcp",
        ...     pod_type="p1.x1",
        ... )

    Note:
        Pinecone requires creating an index first. The store will
        create one if it doesn't exist (serverless mode only).
    """

    pinecone_config: PineconeVectorConfig
    _pc: Any = None  # Pinecone client
    _index: Index | None = None
    _initialized: bool = False

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        api_key: str,
        index_name: str = "locus-vectors",
        namespace: str = "",
        dimension: int = 1536,
        metric: str = "cosine",
        cloud: str = "aws",
        region: str = "us-east-1",
        environment: str | None = None,
        **kwargs: Any,
    ) -> None:
        pinecone_config = PineconeVectorConfig(
            api_key=api_key,
            index_name=index_name,
            namespace=namespace,
            dimension=dimension,
            metric=metric,
            cloud=cloud,
            region=region,
            environment=environment,
            **kwargs,
        )
        super().__init__(pinecone_config=pinecone_config)

    @property
    def config(self) -> VectorStoreConfig:
        """Get store configuration."""
        return VectorStoreConfig(
            dimension=self.pinecone_config.dimension,
            distance_metric=self.pinecone_config.metric,
            index_type="hnsw",
        )

    def _get_client(self) -> Any:
        """Get or create Pinecone client."""
        if self._pc is None:
            try:
                from pinecone import Pinecone
            except ImportError as e:
                raise ImportError(
                    "PineconeVectorStore requires 'pinecone'. Install with: pip install pinecone"
                ) from e

            self._pc = Pinecone(api_key=self.pinecone_config.api_key)

        return self._pc

    def _get_index(self) -> Index:
        """Get or create Pinecone index."""
        if self._index is None:
            pc = self._get_client()

            # Check if index exists
            existing_indexes = [idx.name for idx in pc.list_indexes()]

            if self.pinecone_config.index_name not in existing_indexes:
                # Create index
                try:
                    from pinecone import PodSpec, ServerlessSpec
                except ImportError as e:
                    raise ImportError(
                        "PineconeVectorStore requires 'pinecone'. "
                        "Install with: pip install pinecone"
                    ) from e

                if self.pinecone_config.environment:
                    # Pod-based
                    spec = PodSpec(
                        environment=self.pinecone_config.environment,
                        pod_type=self.pinecone_config.pod_type,
                        replicas=self.pinecone_config.replicas,
                    )
                else:
                    # Serverless
                    spec = ServerlessSpec(
                        cloud=self.pinecone_config.cloud,
                        region=self.pinecone_config.region,
                    )

                pc.create_index(
                    name=self.pinecone_config.index_name,
                    dimension=self.pinecone_config.dimension,
                    metric=self.pinecone_config.metric,
                    spec=spec,
                )

            self._index = pc.Index(self.pinecone_config.index_name)
            self._initialized = True

        return self._index

    async def add(self, document: Document) -> str:
        """Add a document."""
        index = self._get_index()

        doc_id = document.id or uuid4().hex

        if document.embedding is None:
            raise ValueError("Document must have an embedding")

        # Prepare metadata (Pinecone has limits on metadata size)
        metadata = {
            "content": document.content[:40000],  # Pinecone metadata limit
            "created_at": document.created_at.isoformat(),
            **{
                k: v
                for k, v in document.metadata.items()
                if isinstance(v, (str, int, float, bool, list))
            },
        }

        index.upsert(
            vectors=[
                {
                    "id": doc_id,
                    "values": document.embedding,
                    "metadata": metadata,
                }
            ],
            namespace=self.pinecone_config.namespace,
        )

        return doc_id

    async def add_batch(self, documents: list[Document]) -> list[str]:
        """Add multiple documents."""
        index = self._get_index()

        vectors = []
        ids = []

        for doc in documents:
            doc_id = doc.id or uuid4().hex
            ids.append(doc_id)

            if doc.embedding is None:
                raise ValueError(f"Document {doc_id} must have an embedding")

            metadata = {
                "content": doc.content[:40000],
                "created_at": doc.created_at.isoformat(),
                **{
                    k: v
                    for k, v in doc.metadata.items()
                    if isinstance(v, (str, int, float, bool, list))
                },
            }

            vectors.append(
                {
                    "id": doc_id,
                    "values": doc.embedding,
                    "metadata": metadata,
                }
            )

        # Pinecone recommends batches of 100
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]
            index.upsert(
                vectors=batch,
                namespace=self.pinecone_config.namespace,
            )

        return ids

    async def get(self, doc_id: str) -> Document | None:
        """Get a document by ID."""
        index = self._get_index()

        try:
            result = index.fetch(
                ids=[doc_id],
                namespace=self.pinecone_config.namespace,
            )
        except Exception:  # noqa: BLE001 — vector store lookup/delete; return falsy on any failure
            return None

        if not result.vectors or doc_id not in result.vectors:
            return None

        vector = result.vectors[doc_id]
        metadata = vector.metadata or {}

        content = metadata.pop("content", "")
        created_at_str = metadata.pop("created_at", None)
        created_at = datetime.fromisoformat(created_at_str) if created_at_str else datetime.now(UTC)

        return Document(
            id=doc_id,
            content=content,
            embedding=list(vector.values),
            metadata=metadata,
            created_at=created_at,
        )

    async def delete(self, doc_id: str) -> bool:
        """Delete a document."""
        index = self._get_index()

        try:
            index.delete(
                ids=[doc_id],
                namespace=self.pinecone_config.namespace,
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
        index = self._get_index()

        # Build filter
        filter_dict = None
        if metadata_filter:
            filter_dict = {k: {"$eq": v} for k, v in metadata_filter.items()}

        result = index.query(
            vector=query_embedding,
            top_k=limit,
            include_metadata=True,
            include_values=True,
            namespace=self.pinecone_config.namespace,
            filter=filter_dict,
        )

        results = []
        for match in result.matches:
            score = match.score

            # Pinecone returns similarity score for cosine/dotproduct
            # and distance for euclidean
            if self.pinecone_config.metric == "euclidean":
                # Convert distance to similarity
                score = 1.0 / (1.0 + score)

            if threshold is not None and score < threshold:
                continue

            metadata = match.metadata or {}
            content = metadata.pop("content", "")
            created_at_str = metadata.pop("created_at", None)
            created_at = (
                datetime.fromisoformat(created_at_str) if created_at_str else datetime.now(UTC)
            )

            doc = Document(
                id=match.id,
                content=content,
                embedding=list(match.values) if match.values else None,
                metadata=metadata,
                created_at=created_at,
            )

            results.append(
                SearchResult(
                    document=doc,
                    score=score,
                    distance=1.0 - score if self.pinecone_config.metric == "cosine" else None,
                )
            )

        return results

    async def count(self) -> int:
        """Count documents."""
        index = self._get_index()
        stats = index.describe_index_stats()

        if self.pinecone_config.namespace:
            ns_stats = stats.namespaces.get(self.pinecone_config.namespace, {})
            return ns_stats.get("vector_count", 0)

        return stats.total_vector_count

    async def clear(self) -> int:
        """Delete all documents."""
        index = self._get_index()
        count = await self.count()

        # Delete all vectors in namespace
        index.delete(
            delete_all=True,
            namespace=self.pinecone_config.namespace,
        )

        return count

    async def close(self) -> None:
        """Close the client."""
        self._index = None
        self._pc = None

    def __repr__(self) -> str:
        return f"PineconeVectorStore(index={self.pinecone_config.index_name!r})"
