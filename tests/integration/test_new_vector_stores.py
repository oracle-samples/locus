# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Integration tests for new vector stores: Chroma, Pinecone, pgvector."""

from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.integration

try:
    import chromadb  # noqa: F401

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


def get_embedder():
    """Get embedder based on available credentials."""
    if os.environ.get("OPENAI_API_KEY"):
        from locus.rag.embeddings import OpenAIEmbeddings

        return OpenAIEmbeddings(model="text-embedding-3-small")
    return None


# =============================================================================
# Chroma Tests (in-memory, requires chromadb package)
# =============================================================================


@pytest.mark.skipif(not CHROMA_AVAILABLE, reason="chromadb package not installed")
class TestChromaVectorStore:
    """Tests for Chroma vector store."""

    @pytest.mark.asyncio
    async def test_chroma_basic_operations(self):
        """Test basic CRUD operations with Chroma."""
        from locus.rag.stores import ChromaVectorStore
        from locus.rag.stores.base import Document

        embedder = get_embedder()
        if not embedder:
            pytest.skip("No embedder available")

        store = ChromaVectorStore(
            collection_name="test_basic",
            dimension=embedder.config.dimension,
        )

        try:
            # Add document
            result = await embedder.embed("Test document content")
            doc = Document(
                id="chroma_test_1",
                content="Test document content",
                embedding=result.embedding,
                metadata={"source": "test"},
            )
            doc_id = await store.add(doc)
            assert doc_id == "chroma_test_1"

            # Get document
            retrieved = await store.get("chroma_test_1")
            assert retrieved is not None
            assert retrieved.content == "Test document content"

            # Count
            count = await store.count()
            assert count == 1

            # Delete
            deleted = await store.delete("chroma_test_1")
            assert deleted is True
            assert await store.count() == 0

        finally:
            await store.clear()
            await store.close()
            await embedder.close()

    @pytest.mark.asyncio
    async def test_chroma_search(self):
        """Test vector similarity search with Chroma."""
        from locus.rag.stores import ChromaVectorStore
        from locus.rag.stores.base import Document

        embedder = get_embedder()
        if not embedder:
            pytest.skip("No embedder available")

        store = ChromaVectorStore(
            collection_name="test_search",
            dimension=embedder.config.dimension,
        )

        try:
            # Add test documents
            texts = [
                "Python is a programming language",
                "JavaScript runs in browsers",
                "Cats are fluffy pets",
            ]

            for i, text in enumerate(texts):
                result = await embedder.embed(text)
                doc = Document(
                    id=f"search_doc_{i}",
                    content=text,
                    embedding=result.embedding,
                )
                await store.add(doc)

            # Search
            query_result = await embedder.embed("programming languages")
            results = await store.search(query_result.embedding, limit=2)

            assert len(results) == 2
            contents = [r.document.content for r in results]
            assert any("Python" in c or "JavaScript" in c for c in contents)

        finally:
            await store.clear()
            await store.close()
            await embedder.close()

    @pytest.mark.asyncio
    async def test_chroma_with_retriever(self):
        """Test RAGRetriever with Chroma backend."""
        from locus.rag import RAGRetriever
        from locus.rag.stores import ChromaVectorStore

        embedder = get_embedder()
        if not embedder:
            pytest.skip("No embedder available")

        store = ChromaVectorStore(
            collection_name="test_retriever",
            dimension=embedder.config.dimension,
        )

        try:
            retriever = RAGRetriever(embedder=embedder, store=store)

            await retriever.add_documents(
                [
                    "Chroma is a lightweight vector database.",
                    "Vector search enables semantic similarity.",
                ]
            )

            result = await retriever.retrieve("vector database", limit=1)

            assert len(result.documents) == 1
            assert "Chroma" in result.documents[0].document.content

        finally:
            await store.clear()
            await store.close()
            await embedder.close()


# =============================================================================
# pgvector Tests (requires PostgreSQL with pgvector extension)
# =============================================================================


def has_postgres_available() -> bool:
    """Check if PostgreSQL is available."""
    return bool(os.environ.get("POSTGRES_DSN") or os.environ.get("PGVECTOR_DSN"))


@pytest.mark.skipif(not has_postgres_available(), reason="PostgreSQL not configured")
class TestPgVectorStore:
    """Tests for pgvector store."""

    @pytest.mark.asyncio
    async def test_pgvector_basic_operations(self):
        """Test basic operations with pgvector."""
        from locus.rag.stores import PgVectorStore
        from locus.rag.stores.base import Document

        embedder = get_embedder()
        if not embedder:
            pytest.skip("No embedder available")

        dsn = os.environ.get("POSTGRES_DSN") or os.environ.get("PGVECTOR_DSN")

        store = PgVectorStore(
            dsn=dsn,
            table_name="test_pgvector",
            dimension=embedder.config.dimension,
        )

        try:
            result = await embedder.embed("Test document")
            doc = Document(
                id="pg_test_1",
                content="Test document",
                embedding=result.embedding,
            )
            doc_id = await store.add(doc)
            assert doc_id == "pg_test_1"

            retrieved = await store.get("pg_test_1")
            assert retrieved is not None
            assert retrieved.content == "Test document"

        finally:
            await store.clear()
            await store.close()
            await embedder.close()
