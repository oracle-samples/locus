# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Vector stores for RAG.

Available stores:
- OracleVectorStore: Oracle 26ai with native VECTOR type (recommended)
- OpenSearchVectorStore: OpenSearch with k-NN plugin
- QdrantVectorStore: Qdrant vector database
- PineconeVectorStore: Pinecone managed vector database
- ChromaVectorStore: Chroma lightweight vector database
- PgVectorStore: PostgreSQL with pgvector extension
- InMemoryVectorStore: In-memory store (testing)
"""

from typing import Any

from locus.rag.stores.base import (
    BaseVectorStore,
    Document,
    SearchResult,
    VectorStore,
    VectorStoreConfig,
)


__all__ = [
    # Base
    "BaseVectorStore",
    "Document",
    "SearchResult",
    "VectorStore",
    "VectorStoreConfig",
    # Stores (lazy imports)
    "OracleVectorStore",
    "OpenSearchVectorStore",
    "QdrantVectorStore",
    "PineconeVectorStore",
    "ChromaVectorStore",
    "PgVectorStore",
    "InMemoryVectorStore",
]


def __getattr__(name: str) -> Any:
    """Lazy import stores to avoid requiring all dependencies."""
    if name == "OracleVectorStore":
        from locus.rag.stores.oracle import OracleVectorStore

        return OracleVectorStore

    if name == "OpenSearchVectorStore":
        from locus.rag.stores.opensearch import OpenSearchVectorStore

        return OpenSearchVectorStore

    if name == "QdrantVectorStore":
        from locus.rag.stores.qdrant import QdrantVectorStore

        return QdrantVectorStore

    if name == "PineconeVectorStore":
        from locus.rag.stores.pinecone import PineconeVectorStore

        return PineconeVectorStore

    if name == "ChromaVectorStore":
        from locus.rag.stores.chroma import ChromaVectorStore

        return ChromaVectorStore

    if name == "PgVectorStore":
        from locus.rag.stores.pgvector import PgVectorStore

        return PgVectorStore

    if name == "InMemoryVectorStore":
        from locus.rag.stores.memory import InMemoryVectorStore

        return InMemoryVectorStore

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
