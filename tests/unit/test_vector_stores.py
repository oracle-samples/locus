# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Unit tests for vector stores."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from locus.rag.stores.base import Document, SearchResult, VectorStoreConfig


class TestDocument:
    """Tests for Document model."""

    def test_create_document(self):
        """Create document with all fields."""
        now = datetime.now(UTC)
        doc = Document(
            id="doc1",
            content="Test content",
            embedding=[0.1, 0.2, 0.3],
            metadata={"key": "value"},
            created_at=now,
        )
        assert doc.id == "doc1"
        assert doc.content == "Test content"
        assert doc.embedding == [0.1, 0.2, 0.3]
        assert doc.metadata == {"key": "value"}
        assert doc.created_at == now

    def test_create_document_minimal(self):
        """Create document with minimal fields."""
        doc = Document(id="doc1", content="Test")
        assert doc.id == "doc1"
        assert doc.content == "Test"


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_create_search_result(self):
        """Create search result."""
        doc = Document(id="doc1", content="Test")
        result = SearchResult(
            document=doc,
            score=0.95,
            distance=0.05,
        )
        assert result.document == doc
        assert result.score == 0.95
        assert result.distance == 0.05


class TestVectorStoreConfig:
    """Tests for VectorStoreConfig."""

    def test_create_config(self):
        """Test creating configuration."""
        config = VectorStoreConfig(
            dimension=1024,
            distance_metric="cosine",
            index_type="hnsw",
        )
        assert config.dimension == 1024
        assert config.distance_metric == "cosine"
        assert config.index_type == "hnsw"


class TestChromaVectorStore:
    """Tests for Chroma vector store."""

    @pytest.fixture
    def mock_chromadb(self):
        """Create mock chromadb module."""
        mock_module = MagicMock()
        mock_collection = MagicMock()
        mock_collection.upsert = MagicMock()
        mock_collection.get = MagicMock(
            return_value={
                "ids": ["doc1"],
                "documents": ["content"],
                "embeddings": [[0.1] * 1536],
                "metadatas": [{"created_at": "2024-01-01T00:00:00+00:00"}],
            }
        )
        mock_collection.query = MagicMock(
            return_value={
                "ids": [["doc1"]],
                "documents": [["content"]],
                "embeddings": [[[0.1] * 1536]],
                "metadatas": [[{"created_at": "2024-01-01T00:00:00+00:00"}]],
                "distances": [[0.1]],
            }
        )
        mock_collection.count = MagicMock(return_value=1)
        mock_collection.delete = MagicMock()

        mock_client = MagicMock()
        mock_client.get_or_create_collection = MagicMock(return_value=mock_collection)
        mock_client.delete_collection = MagicMock()

        mock_module.EphemeralClient = MagicMock(return_value=mock_client)
        mock_module.PersistentClient = MagicMock(return_value=mock_client)
        mock_module.HttpClient = MagicMock(return_value=mock_client)

        return mock_module, mock_client, mock_collection

    @pytest.mark.asyncio
    async def test_add_document(self, mock_chromadb):
        """Test adding a document."""
        mock_module, mock_client, mock_collection = mock_chromadb

        with patch.dict("sys.modules", {"chromadb": mock_module}):
            from locus.rag.stores.chroma import ChromaVectorStore

            store = ChromaVectorStore(collection_name="test")
            store._client = mock_client
            store._collection = mock_collection

            doc = Document(
                id="doc1",
                content="Test content",
                embedding=[0.1] * 1536,
            )

            doc_id = await store.add(doc)

            assert doc_id == "doc1"
            mock_collection.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_document(self, mock_chromadb):
        """Test getting a document by ID."""
        mock_module, mock_client, mock_collection = mock_chromadb

        with patch.dict("sys.modules", {"chromadb": mock_module}):
            from locus.rag.stores.chroma import ChromaVectorStore

            store = ChromaVectorStore()
            store._client = mock_client
            store._collection = mock_collection

            doc = await store.get("doc1")

            assert doc is not None
            assert doc.id == "doc1"
            assert doc.content == "content"

    @pytest.mark.asyncio
    async def test_search_documents(self, mock_chromadb):
        """Test searching for similar documents."""
        mock_module, mock_client, mock_collection = mock_chromadb

        with patch.dict("sys.modules", {"chromadb": mock_module}):
            from locus.rag.stores.chroma import ChromaVectorStore

            store = ChromaVectorStore()
            store._client = mock_client
            store._collection = mock_collection

            results = await store.search([0.1] * 1536, limit=5)

            assert len(results) == 1
            assert isinstance(results[0], SearchResult)
            assert results[0].document.id == "doc1"

    @pytest.mark.asyncio
    async def test_delete_document(self, mock_chromadb):
        """Test deleting a document."""
        mock_module, mock_client, mock_collection = mock_chromadb

        with patch.dict("sys.modules", {"chromadb": mock_module}):
            from locus.rag.stores.chroma import ChromaVectorStore

            store = ChromaVectorStore()
            store._client = mock_client
            store._collection = mock_collection

            result = await store.delete("doc1")
            assert result is True

    @pytest.mark.asyncio
    async def test_count_documents(self, mock_chromadb):
        """Test counting documents."""
        mock_module, mock_client, mock_collection = mock_chromadb

        with patch.dict("sys.modules", {"chromadb": mock_module}):
            from locus.rag.stores.chroma import ChromaVectorStore

            store = ChromaVectorStore()
            store._client = mock_client
            store._collection = mock_collection

            count = await store.count()
            assert count == 1

    def test_repr(self, mock_chromadb):
        """Test string representation."""
        mock_module, _, _ = mock_chromadb

        with patch.dict("sys.modules", {"chromadb": mock_module}):
            from locus.rag.stores.chroma import ChromaVectorStore

            store = ChromaVectorStore(collection_name="my_collection")
            assert "my_collection" in repr(store)
