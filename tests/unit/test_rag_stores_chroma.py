# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Unit tests for ``locus.rag.stores.chroma`` (ChromaVectorStore).

The store talks to a chromadb client. We inject a recordable stub
client + collection so we never need a real Chroma server. Coverage:

- ``_get_client`` matrix: Chroma Cloud (api_key + host), remote HTTP
  (host only), persistent local dir, in-memory ephemeral, plus the
  ``ssl=False + api_key`` refusal path
- ``_get_collection`` distance-metric mapping (cosine, l2, ip, dot
  alias, unknown → cosine fallback)
- ``add``/``add_batch`` happy path + missing-embedding errors
- ``get`` round-trips the document, returns None on missing or on
  client exception
- ``delete`` returns True on hit, False on miss, False on exception
- ``search`` distance→score conversion for cosine / l2 / ip metrics,
  threshold filter, metadata-filter ``$and`` and single-key paths
- ``count`` / ``clear`` (recreate after delete)
- ``close`` resets client + collection
- ``__repr__``
- missing-chromadb package import error
"""

from __future__ import annotations

import sys
import types
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import SecretStr

from locus.rag.stores.base import Document
from locus.rag.stores.chroma import ChromaVectorConfig, ChromaVectorStore


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _StubCollection:
    """Recordable stand-in for chromadb's ``Collection``."""

    def __init__(
        self,
        *,
        get_result: dict[str, Any] | None = None,
        query_result: dict[str, Any] | None = None,
        get_raises: bool = False,
        delete_raises: bool = False,
        count_value: int = 0,
    ) -> None:
        self.get_result = get_result
        self.query_result = query_result
        self.get_raises = get_raises
        self.delete_raises = delete_raises
        self.count_value = count_value
        self.upserts: list[dict[str, Any]] = []
        self.deletes: list[list[str]] = []

    def upsert(
        self,
        *,
        ids: list[str],
        embeddings: Any,
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self.upserts.append(
            {
                "ids": ids,
                "embeddings": embeddings,
                "documents": documents,
                "metadatas": metadatas,
            }
        )

    def get(self, *, ids: list[str], include: list[str] | None = None) -> dict[str, Any]:
        if self.get_raises:
            raise RuntimeError("simulated get failure")
        return self.get_result or {"ids": [], "documents": [], "embeddings": [], "metadatas": []}

    def query(
        self,
        *,
        query_embeddings: Any,
        n_results: int,
        where: Any = None,
        include: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.query_result or {
            "ids": [[]],
            "documents": [[]],
            "embeddings": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

    def delete(self, *, ids: list[str]) -> None:
        if self.delete_raises:
            raise RuntimeError("simulated delete failure")
        self.deletes.append(ids)

    def count(self) -> int:
        return self.count_value


class _StubClient:
    """Stand-in for chromadb's ``ClientAPI``."""

    def __init__(self, collection: _StubCollection | None = None) -> None:
        self._collection = collection or _StubCollection()
        self.created_collections: list[dict[str, Any]] = []
        self.deleted_collections: list[str] = []

    def get_or_create_collection(
        self, *, name: str, metadata: dict[str, Any] | None = None
    ) -> _StubCollection:
        self.created_collections.append({"name": name, "metadata": metadata})
        return self._collection

    def delete_collection(self, name: str) -> None:
        self.deleted_collections.append(name)


def _stub_chromadb(
    monkeypatch: pytest.MonkeyPatch,
    *,
    collection: _StubCollection | None = None,
) -> dict[str, Any]:
    """Install a fake ``chromadb`` module."""
    probes: dict[str, Any] = {
        "http_client_kwargs": [],
        "persistent_kwargs": [],
        "ephemeral_calls": 0,
    }

    client = _StubClient(collection=collection)

    fake = types.ModuleType("chromadb")

    def http_client(**kwargs: Any) -> _StubClient:
        probes["http_client_kwargs"].append(kwargs)
        return client

    def persistent_client(**kwargs: Any) -> _StubClient:
        probes["persistent_kwargs"].append(kwargs)
        return client

    def ephemeral_client() -> _StubClient:
        probes["ephemeral_calls"] += 1
        return client

    fake.HttpClient = http_client  # type: ignore[attr-defined]
    fake.PersistentClient = persistent_client  # type: ignore[attr-defined]
    fake.EphemeralClient = ephemeral_client  # type: ignore[attr-defined]
    fake.ClientAPI = _StubClient  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "chromadb", fake)
    probes["client"] = client
    return probes


def _doc(
    *,
    doc_id: str | None = None,
    content: str = "hello",
    embedding: list[float] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Document:
    return Document(
        id=doc_id or "doc-1",
        content=content,
        embedding=embedding if embedding is not None else [0.1, 0.2, 0.3],
        metadata=metadata or {},
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Config + property
# ---------------------------------------------------------------------------


class TestConfig:
    def test_defaults(self) -> None:
        cfg = ChromaVectorConfig()
        assert cfg.collection_name == "locus_vectors"
        assert cfg.distance_metric == "cosine"
        assert cfg.dimension == 1536
        assert cfg.ssl is True

    def test_constructor_promotes_string_api_key_to_secretstr(self) -> None:
        store = ChromaVectorStore(api_key="secret-key", host="api.trychroma.com")
        assert isinstance(store.chroma_config.api_key, SecretStr)
        assert store.chroma_config.api_key.get_secret_value() == "secret-key"

    def test_config_property(self) -> None:
        store = ChromaVectorStore(dimension=256, distance_metric="l2")
        assert store.config.dimension == 256
        assert store.config.distance_metric == "l2"
        assert store.config.index_type == "hnsw"

    def test_repr(self) -> None:
        store = ChromaVectorStore(collection_name="my_docs")
        assert "my_docs" in repr(store)


# ---------------------------------------------------------------------------
# _get_client matrix
# ---------------------------------------------------------------------------


class TestGetClient:
    def test_chroma_cloud_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        probes = _stub_chromadb(monkeypatch)
        store = ChromaVectorStore(host="api.trychroma.com", api_key="secret")
        store._get_client()
        kwargs = probes["http_client_kwargs"][0]
        assert kwargs["host"] == "api.trychroma.com"
        assert kwargs["ssl"] is True
        assert "Authorization" in kwargs["headers"]
        assert "Bearer secret" in kwargs["headers"]["Authorization"]

    def test_remote_chroma_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        probes = _stub_chromadb(monkeypatch)
        store = ChromaVectorStore(host="local.chroma")
        store._get_client()
        kwargs = probes["http_client_kwargs"][0]
        assert kwargs["host"] == "local.chroma"
        assert "headers" not in kwargs

    def test_persistent_local(self, monkeypatch: pytest.MonkeyPatch) -> None:
        probes = _stub_chromadb(monkeypatch)
        store = ChromaVectorStore(persist_directory="/tmp/chromadb")  # noqa: S108
        store._get_client()
        kwargs = probes["persistent_kwargs"][0]
        assert kwargs["path"] == "/tmp/chromadb"  # noqa: S108

    def test_ephemeral_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        probes = _stub_chromadb(monkeypatch)
        store = ChromaVectorStore()
        store._get_client()
        assert probes["ephemeral_calls"] == 1

    def test_chroma_cloud_refuses_cleartext_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_chromadb(monkeypatch)
        store = ChromaVectorStore(host="api.trychroma.com", api_key="secret", ssl=False)
        with pytest.raises(ValueError, match="Refusing to send Chroma API key"):
            store._get_client()

    def test_client_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        probes = _stub_chromadb(monkeypatch)
        store = ChromaVectorStore()
        c1 = store._get_client()
        c2 = store._get_client()
        assert c1 is c2
        assert probes["ephemeral_calls"] == 1

    def test_missing_chromadb_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "chromadb", None)
        store = ChromaVectorStore()
        with pytest.raises(ImportError, match="ChromaVectorStore requires 'chromadb'"):
            store._get_client()


# ---------------------------------------------------------------------------
# _get_collection — distance metric mapping
# ---------------------------------------------------------------------------


class TestGetCollection:
    @pytest.mark.parametrize(
        ("metric", "expected"),
        [("cosine", "cosine"), ("l2", "l2"), ("ip", "ip"), ("dot", "ip"), ("unknown", "cosine")],
    )
    def test_distance_metric_mapping(
        self,
        monkeypatch: pytest.MonkeyPatch,
        metric: str,
        expected: str,
    ) -> None:
        probes = _stub_chromadb(monkeypatch)
        store = ChromaVectorStore(distance_metric=metric)
        store._get_collection()
        created = probes["client"].created_collections[0]
        assert created["metadata"] == {"hnsw:space": expected}

    def test_collection_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        probes = _stub_chromadb(monkeypatch)
        store = ChromaVectorStore()
        c1 = store._get_collection()
        c2 = store._get_collection()
        assert c1 is c2
        assert len(probes["client"].created_collections) == 1


# ---------------------------------------------------------------------------
# add / add_batch
# ---------------------------------------------------------------------------


class TestAdd:
    @pytest.mark.asyncio
    async def test_add_returns_doc_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        col = _StubCollection()
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        doc_id = await store.add(_doc(doc_id="explicit"))
        assert doc_id == "explicit"
        assert col.upserts[0]["ids"] == ["explicit"]

    @pytest.mark.asyncio
    async def test_add_generates_id_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        col = _StubCollection()
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        # Use an empty string for id — Document defaults aren't auto-id;
        # the chroma store generates one when the doc's id is falsy.
        doc = _doc(doc_id="")
        out_id = await store.add(doc)
        assert out_id  # non-empty
        assert col.upserts[0]["ids"][0] == out_id

    @pytest.mark.asyncio
    async def test_add_normalises_non_primitive_metadata_to_str(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        col = _StubCollection()
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        doc = _doc(metadata={"tags": ["a", "b"], "count": 5})
        await store.add(doc)
        meta = col.upserts[0]["metadatas"][0]
        # Non-primitive ``tags`` is str-coerced, primitive ``count`` kept.
        assert isinstance(meta["tags"], str)
        assert meta["count"] == 5

    @pytest.mark.asyncio
    async def test_add_missing_embedding_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_chromadb(monkeypatch)
        store = ChromaVectorStore()
        with pytest.raises(ValueError, match="must have an embedding"):
            await store.add(
                Document(
                    id="d",
                    content="x",
                    embedding=None,
                    metadata={},
                    created_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
            )

    @pytest.mark.asyncio
    async def test_add_batch_returns_all_ids(self, monkeypatch: pytest.MonkeyPatch) -> None:
        col = _StubCollection()
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        ids = await store.add_batch(
            [_doc(doc_id="a", embedding=[0.1]), _doc(doc_id="b", embedding=[0.2])]
        )
        assert ids == ["a", "b"]

    @pytest.mark.asyncio
    async def test_add_batch_empty_inputs_skips_upsert(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        col = _StubCollection()
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        ids = await store.add_batch([])
        assert ids == []
        assert col.upserts == []

    @pytest.mark.asyncio
    async def test_add_batch_missing_embedding_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_chromadb(monkeypatch)
        store = ChromaVectorStore()
        bad = Document(
            id="d",
            content="x",
            embedding=None,
            metadata={},
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        with pytest.raises(ValueError, match="must have an embedding"):
            await store.add_batch([bad])


# ---------------------------------------------------------------------------
# get / delete
# ---------------------------------------------------------------------------


class TestGet:
    @pytest.mark.asyncio
    async def test_get_returns_document(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
        col = _StubCollection(
            get_result={
                "ids": ["d1"],
                "documents": ["body"],
                "embeddings": [[0.1, 0.2]],
                "metadatas": [{"created_at": ts, "tag": "a"}],
            }
        )
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        doc = await store.get("d1")
        assert doc is not None
        assert doc.id == "d1"
        assert doc.content == "body"
        assert doc.metadata == {"tag": "a"}

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        col = _StubCollection(
            get_result={"ids": [], "documents": [], "embeddings": [], "metadatas": []}
        )
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        assert await store.get("missing") is None

    @pytest.mark.asyncio
    async def test_get_exception_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        col = _StubCollection(get_raises=True)
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        assert await store.get("d1") is None

    @pytest.mark.asyncio
    async def test_get_missing_created_at_uses_now(self, monkeypatch: pytest.MonkeyPatch) -> None:
        col = _StubCollection(
            get_result={
                "ids": ["d1"],
                "documents": ["body"],
                "embeddings": [[0.0]],
                "metadatas": [{}],
            }
        )
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        doc = await store.get("d1")
        assert doc is not None
        # Defaulted to ``datetime.now`` — just check it's tz-aware.
        assert doc.created_at.tzinfo is not None


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        col = _StubCollection(get_result={"ids": ["d1"]})
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        assert await store.delete("d1") is True
        assert col.deletes == [["d1"]]

    @pytest.mark.asyncio
    async def test_delete_missing_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        col = _StubCollection(get_result={"ids": []})
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        assert await store.delete("missing") is False

    @pytest.mark.asyncio
    async def test_delete_exception_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        col = _StubCollection(get_result={"ids": ["d1"]}, delete_raises=True)
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        assert await store.delete("d1") is False


# ---------------------------------------------------------------------------
# search — distance → score conversion
# ---------------------------------------------------------------------------


class TestSearch:
    @pytest.mark.asyncio
    async def test_cosine_distance_to_similarity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
        col = _StubCollection(
            query_result={
                "ids": [["d1", "d2"]],
                "documents": [["a", "b"]],
                "embeddings": [[[0.1], [0.2]]],
                "metadatas": [[{"created_at": ts}, {"created_at": ts}]],
                "distances": [[0.0, 2.0]],  # min distance + max distance
            }
        )
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore(distance_metric="cosine")
        results = await store.search([0.0, 0.0])
        # cosine distance 0 → similarity 1; distance 2 → similarity 0.
        assert results[0].score == pytest.approx(1.0)
        assert results[1].score == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_l2_distance_to_similarity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
        col = _StubCollection(
            query_result={
                "ids": [["d1"]],
                "documents": [["a"]],
                "embeddings": [[[0.1]]],
                "metadatas": [[{"created_at": ts}]],
                "distances": [[1.0]],
            }
        )
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore(distance_metric="l2")
        results = await store.search([0.0])
        # 1 / (1 + 1) = 0.5
        assert results[0].score == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_ip_distance_to_similarity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
        col = _StubCollection(
            query_result={
                "ids": [["d1"]],
                "documents": [["a"]],
                "embeddings": [[[0.1]]],
                "metadatas": [[{"created_at": ts}]],
                "distances": [[0.0]],  # neutral inner product
            }
        )
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore(distance_metric="ip")
        results = await store.search([0.0])
        # (0 + 1) / 2 = 0.5
        assert results[0].score == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_threshold_filters_below_score(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
        col = _StubCollection(
            query_result={
                "ids": [["d1", "d2"]],
                "documents": [["a", "b"]],
                "embeddings": [[[0.1], [0.2]]],
                "metadatas": [[{"created_at": ts}, {"created_at": ts}]],
                "distances": [[0.0, 2.0]],
            }
        )
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore(distance_metric="cosine")
        results = await store.search([0.0], threshold=0.5)
        # Only the high-similarity result survives.
        assert [r.document.id for r in results] == ["d1"]

    @pytest.mark.asyncio
    async def test_metadata_filter_single_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        col = _StubCollection(
            query_result={
                "ids": [[]],
                "documents": [[]],
                "embeddings": [[]],
                "metadatas": [[]],
                "distances": [[]],
            }
        )
        captured: dict[str, Any] = {}
        original_query = col.query

        def capture_query(**kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return original_query(**kwargs)

        col.query = capture_query  # type: ignore[method-assign]
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        await store.search([0.0], metadata_filter={"tier": "gold"})
        assert captured["where"] == {"tier": {"$eq": "gold"}}

    @pytest.mark.asyncio
    async def test_metadata_filter_multi_key_uses_and(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        col = _StubCollection(
            query_result={
                "ids": [[]],
                "documents": [[]],
                "embeddings": [[]],
                "metadatas": [[]],
                "distances": [[]],
            }
        )
        captured: dict[str, Any] = {}
        original_query = col.query

        def capture_query(**kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return original_query(**kwargs)

        col.query = capture_query  # type: ignore[method-assign]
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        await store.search([0.0], metadata_filter={"a": 1, "b": 2})
        assert "$and" in captured["where"]

    @pytest.mark.asyncio
    async def test_search_handles_empty_result_lists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        col = _StubCollection(
            query_result={
                "ids": None,
                "documents": None,
                "embeddings": None,
                "metadatas": None,
                "distances": None,
            }
        )
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        # Falsy lists short-circuit each branch — no crash.
        assert await store.search([0.0]) == []


# ---------------------------------------------------------------------------
# count / clear / close
# ---------------------------------------------------------------------------


class TestCountClearClose:
    @pytest.mark.asyncio
    async def test_count_returns_collection_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        col = _StubCollection(count_value=42)
        _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore()
        assert await store.count() == 42

    @pytest.mark.asyncio
    async def test_clear_deletes_collection_and_recreates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        col = _StubCollection(count_value=7)
        probes = _stub_chromadb(monkeypatch, collection=col)
        store = ChromaVectorStore(collection_name="my_docs")
        n = await store.clear()
        assert n == 7
        # Collection deleted then recreated on the same client.
        assert "my_docs" in probes["client"].deleted_collections
        assert len(probes["client"].created_collections) >= 2

    @pytest.mark.asyncio
    async def test_close_resets_client_and_collection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_chromadb(monkeypatch)
        store = ChromaVectorStore()
        store._get_collection()  # prime
        await store.close()
        assert store._client is None
        assert store._collection is None
