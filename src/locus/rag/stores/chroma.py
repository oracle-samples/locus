# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Chroma vector store.

Chroma is a lightweight, developer-friendly vector database
perfect for prototyping and small-to-medium applications.
"""

from __future__ import annotations

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
    import chromadb
    from chromadb.api.models.Collection import Collection


class ChromaVectorConfig(BaseModel):
    """Configuration for Chroma Vector Store."""

    collection_name: str = Field(
        default="locus_vectors",
        description="Collection name",
    )
    persist_directory: str | None = Field(
        default=None,
        description="Directory for persistent storage (None for in-memory)",
    )
    dimension: int = Field(default=1536, description="Vector dimension")
    distance_metric: str = Field(
        default="cosine",
        description="Distance metric: cosine, l2, ip (inner product)",
    )

    # Chroma Cloud / remote Chroma settings
    host: str | None = Field(default=None, description="Chroma server host")
    port: int = Field(default=8000, description="Chroma server port")
    # Store the API key as SecretStr so it does not leak via repr() /
    # model_dump_json(); .get_secret_value() is called only at the point
    # where the Authorization header is built.
    api_key: SecretStr | None = Field(default=None, description="Chroma Cloud API key")
    tenant: str | None = Field(default=None, description="Chroma Cloud tenant")
    database: str | None = Field(default=None, description="Chroma Cloud database")
    # Use HTTPS for every remote connection by default. The chromadb
    # HttpClient defaults to plain HTTP, which would ship the Bearer API key
    # (and every embedding / document body) in cleartext (CWE-319). Set to
    # False only for an explicit local-dev / loopback setup.
    ssl: bool = Field(
        default=True,
        description="Use HTTPS for the remote Chroma connection",
    )


class ChromaVectorStore(BaseModel, BaseVectorStore):
    """
    Chroma vector store.

    Chroma is a lightweight, open-source embedding database with:
    - Simple API and minimal setup
    - In-memory or persistent storage
    - Automatic embedding generation (optional)
    - Metadata filtering

    Example (in-memory):
        >>> store = ChromaVectorStore(
        ...     collection_name="my_docs",
        ...     dimension=1536,
        ... )
        >>> await store.add(document)
        >>> results = await store.search(query_embedding, limit=5)

    Example (persistent):
        >>> store = ChromaVectorStore(
        ...     collection_name="my_docs",
        ...     persist_directory="./chroma_data",
        ... )

    Example (Chroma Cloud):
        >>> store = ChromaVectorStore(
        ...     host="api.trychroma.com",
        ...     api_key="your-api-key",
        ...     tenant="your-tenant",
        ...     database="your-database",
        ... )
    """

    chroma_config: ChromaVectorConfig = Field(default_factory=ChromaVectorConfig)
    _client: chromadb.ClientAPI | None = None
    _collection: Collection | None = None
    _initialized: bool = False

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        collection_name: str = "locus_vectors",
        persist_directory: str | None = None,
        dimension: int = 1536,
        distance_metric: str = "cosine",
        host: str | None = None,
        port: int = 8000,
        api_key: str | SecretStr | None = None,
        **kwargs: Any,
    ) -> None:
        if isinstance(api_key, str):
            api_key = SecretStr(api_key)
        chroma_config = ChromaVectorConfig(
            collection_name=collection_name,
            persist_directory=persist_directory,
            dimension=dimension,
            distance_metric=distance_metric,
            host=host,
            port=port,
            api_key=api_key,
            **kwargs,
        )
        super().__init__(chroma_config=chroma_config)

    @property
    def config(self) -> VectorStoreConfig:
        """Get store configuration."""
        return VectorStoreConfig(
            dimension=self.chroma_config.dimension,
            distance_metric=self.chroma_config.distance_metric,
            index_type="hnsw",
        )

    def _get_client(self) -> chromadb.ClientAPI:
        """Get or create Chroma client."""
        if self._client is None:
            try:
                import chromadb
            except ImportError as e:
                raise ImportError(
                    "ChromaVectorStore requires 'chromadb'. Install with: pip install chromadb"
                ) from e

            ssl = self.chroma_config.ssl
            # Chroma Cloud
            if self.chroma_config.api_key and self.chroma_config.host:
                if not ssl:
                    raise ValueError(
                        "Refusing to send Chroma API key over cleartext HTTP. "
                        "Set ChromaVectorConfig(ssl=True) or drop the api_key "
                        "for a local/non-authenticated server."
                    )
                self._client = chromadb.HttpClient(
                    host=self.chroma_config.host,
                    port=self.chroma_config.port,
                    ssl=ssl,
                    headers={
                        "Authorization": (
                            f"Bearer {self.chroma_config.api_key.get_secret_value()}"
                        ),
                    },
                )
            # Remote Chroma server
            elif self.chroma_config.host:
                self._client = chromadb.HttpClient(
                    host=self.chroma_config.host,
                    port=self.chroma_config.port,
                    ssl=ssl,
                )
            # Persistent local storage
            elif self.chroma_config.persist_directory:
                self._client = chromadb.PersistentClient(
                    path=self.chroma_config.persist_directory,
                )
            # In-memory (ephemeral)
            else:
                self._client = chromadb.EphemeralClient()

        return self._client

    def _get_collection(self) -> Collection:
        """Get or create collection."""
        if self._collection is None:
            client = self._get_client()

            # Map distance metric
            distance_map = {
                "cosine": "cosine",
                "l2": "l2",
                "ip": "ip",
                "dot": "ip",  # Alias
            }
            distance = distance_map.get(
                self.chroma_config.distance_metric.lower(),
                "cosine",
            )

            self._collection = client.get_or_create_collection(
                name=self.chroma_config.collection_name,
                metadata={"hnsw:space": distance},
            )
            self._initialized = True

        return self._collection

    async def add(self, document: Document) -> str:
        """Add a document."""
        collection = self._get_collection()

        doc_id = document.id or uuid4().hex

        if document.embedding is None:
            raise ValueError("Document must have an embedding")

        # Prepare metadata (Chroma requires flat structure)
        metadata = {
            "created_at": document.created_at.isoformat(),
            **{
                k: str(v) if not isinstance(v, str | int | float | bool) else v
                for k, v in document.metadata.items()
            },
        }

        # chromadb's typed shapes ask for ``Sequence[Sequence[float]]``;
        # we pass the wider ``list[list[float]]`` we have at hand.
        collection.upsert(
            ids=[doc_id],
            embeddings=[document.embedding],  # type: ignore[arg-type, unused-ignore]
            documents=[document.content],
            metadatas=[metadata],
        )

        return doc_id

    async def add_batch(self, documents: list[Document]) -> list[str]:
        """Add multiple documents."""
        collection = self._get_collection()

        ids = []
        embeddings = []
        docs = []
        metadatas = []

        for doc in documents:
            doc_id = doc.id or uuid4().hex
            ids.append(doc_id)

            if doc.embedding is None:
                raise ValueError(f"Document {doc_id} must have an embedding")

            embeddings.append(doc.embedding)
            docs.append(doc.content)
            metadatas.append(
                {
                    "created_at": doc.created_at.isoformat(),
                    **{
                        k: str(v) if not isinstance(v, str | int | float | bool) else v
                        for k, v in doc.metadata.items()
                    },
                }
            )

        if ids:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,  # type: ignore[arg-type, unused-ignore]
                documents=docs,
                metadatas=metadatas,  # type: ignore[arg-type, unused-ignore]
            )

        return ids

    async def get(self, doc_id: str) -> Document | None:
        """Get a document by ID."""
        collection = self._get_collection()

        try:
            result = collection.get(
                ids=[doc_id],
                include=["embeddings", "documents", "metadatas"],
            )
        except Exception:  # noqa: BLE001 — vector store lookup/delete; return falsy on any failure
            return None

        if not result["ids"]:
            return None

        metadata: dict[str, Any] = dict(result["metadatas"][0]) if result["metadatas"] else {}
        created_at_str = metadata.pop("created_at", None)
        created_at = datetime.fromisoformat(created_at_str) if created_at_str else datetime.now(UTC)

        # Handle embeddings - check for None and length since numpy arrays can't be used as bool
        embedding = None
        if result["embeddings"] is not None and len(result["embeddings"]) > 0:
            embedding = result["embeddings"][0]

        return Document(
            id=result["ids"][0],
            content=result["documents"][0] if result["documents"] else "",
            embedding=embedding,  # type: ignore[arg-type, unused-ignore]
            metadata=metadata,
            created_at=created_at,
        )

    async def delete(self, doc_id: str) -> bool:
        """Delete a document."""
        collection = self._get_collection()

        try:
            # Check if exists first
            existing = collection.get(ids=[doc_id])
            if not existing["ids"]:
                return False

            collection.delete(ids=[doc_id])
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
        collection = self._get_collection()

        # Build where filter for metadata
        where: dict[str, Any] | None = None
        if metadata_filter:
            if len(metadata_filter) == 1:
                key, value = next(iter(metadata_filter.items()))
                where = {key: {"$eq": value}}
            else:
                where = {"$and": [{k: {"$eq": v}} for k, v in metadata_filter.items()]}

        result = collection.query(
            query_embeddings=[query_embedding],  # type: ignore[arg-type, unused-ignore]
            n_results=limit,
            where=where,
            include=["embeddings", "documents", "metadatas", "distances"],
        )

        results = []
        ids = result["ids"][0] if result["ids"] else []
        documents = result["documents"][0] if result["documents"] else []
        embeddings = result["embeddings"][0] if result["embeddings"] else []
        metadatas = result["metadatas"][0] if result["metadatas"] else []
        distances = result["distances"][0] if result["distances"] else []

        for i, doc_id in enumerate(ids):
            distance = distances[i] if i < len(distances) else 0

            # Convert distance to similarity score (0-1, higher is better)
            # Chroma returns L2 distance or cosine distance depending on config
            if self.chroma_config.distance_metric.lower() == "cosine":
                # Cosine distance is 0-2, convert to similarity
                score = 1.0 - (distance / 2.0)
            elif self.chroma_config.distance_metric.lower() in ("l2", "euclidean"):
                # L2 distance: use exponential decay
                score = 1.0 / (1.0 + distance)
            else:  # ip (inner product)
                # Inner product can be negative, normalize
                score = max(0.0, min(1.0, (distance + 1.0) / 2.0))

            if threshold is not None and score < threshold:
                continue

            metadata: dict[str, Any] = dict(metadatas[i]) if i < len(metadatas) else {}
            created_at_str = metadata.pop("created_at", None)
            created_at = (
                datetime.fromisoformat(created_at_str) if created_at_str else datetime.now(UTC)
            )

            doc = Document(
                id=doc_id,
                content=documents[i] if i < len(documents) else "",
                embedding=embeddings[i] if i < len(embeddings) else None,  # type: ignore[arg-type, unused-ignore]
                metadata=metadata,
                created_at=created_at,
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
        """Count documents."""
        collection = self._get_collection()
        n: int = collection.count()
        return n

    async def clear(self) -> int:
        """Delete all documents."""
        collection = self._get_collection()
        count: int = collection.count()

        # Delete collection and recreate
        client = self._get_client()
        client.delete_collection(self.chroma_config.collection_name)
        self._collection = None
        self._get_collection()  # Recreate

        return count

    async def close(self) -> None:
        """Close the client."""
        self._collection = None
        self._client = None

    def __repr__(self) -> str:
        return f"ChromaVectorStore(collection={self.chroma_config.collection_name!r})"
