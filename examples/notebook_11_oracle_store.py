#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Notebook 11: cross-thread long-term memory on Oracle Database 26ai.

Where ``oracle_checkpointer`` (notebook 07) persists *per-thread* agent
state, :class:`OracleStore` persists *cross-thread* facts: the
namespaced key/value store the long-term-memory layer reaches for when
something needs to outlive any single conversation. It is the locus
native equivalent of ``langgraph-oracledb.OracleStore`` /
``AsyncOracleStore`` — same schema shape, same surface area — but with
**zero** langchain / langgraph imports.

Key concepts:

- Namespaces are ``tuple[str, ...]`` and flatten to ``/``-joined
  strings inside the table; ``list_namespaces(prefix=...)`` enumerates
  every namespace beneath a parent.
- Plain K/V mode: ``put(...)`` / ``get(...)`` against a CLOB JSON
  column, keyed on ``(namespace, key)``.
- Vector mode: pass ``dimension=N`` and the store provisions a
  ``VECTOR(N, FLOAT32)`` column; ``put_with_embedding`` /
  ``search_by_embedding`` use the same ``VECTOR_DISTANCE`` SQL function
  the RAG store uses, but scoped to a namespace.
- The same connection envelope works alongside ``oracle_checkpointer``
  in notebook 07 and ``OracleCheckpointSaver`` in notebook 12 — one
  Autonomous Database wallet, three primitives.

This notebook uses a tiny 4-dim fake embedding so the vector demo can
run without an embedding model. Real workloads hand in 1024-dim Cohere
V3 or 1536-dim Cohere V4 vectors.

Run it::

    export ORACLE_DSN=mydb_low                   # tnsnames alias
    export ORACLE_USER=locus_app                 # least-privileged app schema
    export ORACLE_PASSWORD='<app-password>'
    export ORACLE_WALLET=~/.oci/wallets/mydb
    export ORACLE_WALLET_PASSWORD='<wallet-pw>'  # if encrypted

    python examples/notebook_11_oracle_store.py

If those env vars aren't set the notebook prints the wiring snippet and
exits cleanly — no traceback, no half-initialised state.

Difficulty: Intermediate. Self-contained — no prior notebook required.
"""

from __future__ import annotations

import asyncio
import os
import sys

from locus.memory.store_backends import OracleStore


_REQUIRED_ENV = (
    "ORACLE_DSN",
    "ORACLE_USER",
    "ORACLE_PASSWORD",
    "ORACLE_WALLET",
)

# Single base name — the store uses it for the table and the namespace
# index. Drop at the end of the demo so the notebook is re-runnable.
TABLE_NAME = "locus_notebook_11_store"

# 4-dim vectors are obviously a toy; production stores hand in real
# embedder output (1024-dim Cohere V3 etc.).
FAKE_DIM = 4


def _missing_env() -> list[str]:
    return [name for name in _REQUIRED_ENV if not os.environ.get(name)]


def _print_skip_banner(missing: list[str]) -> None:
    print("\n--- Notebook 11: OracleStore (long-term memory) ---")
    print(
        "Required environment variables not set; skipping the live demo so "
        "this file still runs cleanly in CI.\n"
    )
    print("Missing:")
    for name in missing:
        print(f"  - {name}")
    print(
        "\nProvision an Autonomous Database, drop its wallet under "
        "$ORACLE_WALLET, then set the variables above and re-run."
    )
    print("\nMinimal wiring (what the live path below builds):")
    print(
        """
    from locus.memory.store_backends import OracleStore

    store = OracleStore(
        dsn=os.environ["ORACLE_DSN"],
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        wallet_location=os.environ["ORACLE_WALLET"],
        wallet_password=os.environ.get("ORACLE_WALLET_PASSWORD", ""),
        table_name="locus_notebook_11_store",
        dimension=4,
    )
    await store.put(("memory", "u42"), "fact-1", {"note": "user likes cats"})
    item = await store.get(("memory", "u42"), "fact-1")
        """.rstrip()
    )


def _build_store() -> OracleStore:
    return OracleStore(
        dsn=os.environ["ORACLE_DSN"],
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        wallet_location=os.path.expanduser(os.environ["ORACLE_WALLET"]),
        wallet_password=os.environ.get("ORACLE_WALLET_PASSWORD", ""),
        table_name=TABLE_NAME,
        dimension=FAKE_DIM,
    )


async def _drop_table(store: OracleStore) -> None:
    """Drop the demo table so the notebook is re-runnable."""
    pool = await store._get_pool()  # noqa: SLF001 — cleanup helper, not public API
    async with pool.acquire() as conn, conn.cursor() as cursor:
        try:
            await cursor.execute(f"DROP TABLE {TABLE_NAME} PURGE")
            await conn.commit()
        except Exception as exc:  # pragma: no cover — cleanup is best-effort
            print(f"  (cleanup) DROP TABLE {TABLE_NAME} skipped: {exc}")


async def plain_kv_demo(store: OracleStore) -> None:
    """K/V mode — the simplest BaseStore surface."""
    print("\n--- 1. Plain K/V: namespaced (namespace, key) -> JSON value ---")
    ns = ("memory", "u42")
    await store.put(ns, "fact-1", {"note": "user likes cats"})
    await store.put(ns, "fact-2", {"note": "user dislikes mornings"})

    fact_1 = await store.get(ns, "fact-1")
    fact_2 = await store.get(ns, "fact-2")
    print(f"  get(('memory','u42'), 'fact-1') -> {fact_1!r}")
    print(f"  get(('memory','u42'), 'fact-2') -> {fact_2!r}")

    print(
        "\n  Namespaces are tuples; the store flattens them to 'memory/u42' "
        "in the table and reverses the join on read."
    )


async def list_namespaces_demo(store: OracleStore) -> None:
    """Show how prefix-scoped namespace enumeration works."""
    print("\n--- 2. list_namespaces(prefix=('memory',)) ---")
    # Add a second user so the prefix scan returns more than one row.
    await store.put(("memory", "u99"), "fact-1", {"note": "second user"})
    namespaces = await store.list_namespaces(prefix=("memory",), limit=10)
    for ns in namespaces:
        print(f"  - {ns}")
    print(
        "\n  The store uses LIKE 'memory/%' under the hood with a guard against "
        "false matches (e.g. ('memorial',) would NOT match prefix ('memo',))."
    )


async def vector_demo(store: OracleStore) -> None:
    """Vector-search mode — ``VECTOR_DISTANCE`` scoped to one namespace."""
    print("\n--- 3. Vector mode: put_with_embedding + search_by_embedding ---")
    ns = ("memory", "u42")
    await store.put_with_embedding(
        ns,
        "fact-3",
        {"note": "favorite color is blue"},
        embedding=[0.1, 0.2, 0.3, 0.4],
    )
    await store.put_with_embedding(
        ns,
        "fact-4",
        {"note": "favorite color is green"},
        embedding=[0.4, 0.3, 0.2, 0.1],
    )

    hits = await store.search_by_embedding(
        ns,
        query_embedding=[0.1, 0.2, 0.3, 0.4],
        limit=3,
    )
    print("  search_by_embedding (top-3, COSINE):")
    for i, hit in enumerate(hits, start=1):
        print(f"    #{i}  score={hit.score:.4f}  key={hit.item.key!r}  value={hit.item.value!r}")

    print(
        "\n  Vector search uses VECTOR_DISTANCE(embedding, TO_VECTOR(:q), COSINE) "
        "with a namespace = :ns WHERE-clause — same SQL the RAG store uses, "
        "but scoped to one logical owner."
    )


async def main() -> None:
    missing = _missing_env()
    if missing:
        _print_skip_banner(missing)
        return

    print("Opening pool against Oracle 26ai…")
    store = _build_store()
    try:
        await plain_kv_demo(store)
        await list_namespaces_demo(store)
        await vector_demo(store)
        print(
            "\nThe same connection envelope wires "
            "oracle_checkpointer (notebook 07), OracleStore (this notebook), "
            "and OracleCheckpointSaver (notebook 12) side-by-side."
        )
    finally:
        print("\n--- Cleanup: drop the demo table ---")
        await _drop_table(store)
        await store.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
