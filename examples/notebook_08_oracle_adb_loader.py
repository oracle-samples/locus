#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tutorial 64: stream rows from an Autonomous Database with ``OracleADBLoader``.

The first link of any Oracle-native RAG pipeline is "get the source
rows out of the database as ``Document`` objects". Locus ships
:class:`locus.rag.loaders.OracleADBLoader` for exactly this: it opens
an async ``oracledb`` pool against an Autonomous Database wallet, runs
a single ``SELECT``, and yields one
:class:`locus.rag.stores.base.Document` per row — content column to
``Document.content``, optional ``id_column`` to ``Document.id``, every
other projected column into ``Document.metadata``.

Key concepts:

- ``OracleADBLoader(dsn=..., user=..., password=..., wallet_location=...,
  sql=..., content_column=..., id_column=..., metadata_columns=[...])``
  is the canonical constructor. The connection envelope mirrors
  :class:`OracleVectorStore` and :class:`OracleBackend` so a single
  wallet block configures all three.
- ``async for doc in loader.lazy_load():`` streams rows as the cursor
  produces them — memory stays flat on large pulls.
- ``await loader.load()`` is the eager variant, returning a
  ``list[Document]``.
- ``await loader.close()`` releases the pool.

This notebook is self-contained: it creates a disposable demo table
``locus_notebook_64_articles``, populates three rows, walks the loader
through both the streaming and eager paths, then drops the table.

Run it::

    export ORACLE_DSN=mydb_low                   # tnsnames alias in the wallet
    export ORACLE_USER=locus_app                 # least-privileged app schema
    export ORACLE_PASSWORD='<app-password>'
    export ORACLE_WALLET=~/.oci/wallets/mydb     # directory holding tnsnames.ora
    export ORACLE_WALLET_PASSWORD='<wallet-pw>'  # if the wallet is encrypted

    python examples/notebook_08_oracle_adb_loader.py

If ``ORACLE_DSN`` / ``ORACLE_PASSWORD`` / ``ORACLE_WALLET`` aren't set
the tutorial prints the wiring snippet and exits cleanly — no
traceback, no half-initialised state.

Difficulty: Intermediate. Self-contained — no prior tutorial required.
"""

from __future__ import annotations

import asyncio
import os
import sys

# Both imports work; the package-level alias is shorter and matches the
# rest of the locus RAG surface (``from locus.rag import OCIEmbeddings``).
from locus.rag.loaders import OracleADBLoader


_REQUIRED_ENV = (
    "ORACLE_DSN",
    "ORACLE_USER",
    "ORACLE_PASSWORD",
    "ORACLE_WALLET",
)


_TABLE = "locus_notebook_64_articles"

_DEMO_ROWS = [
    (
        1,
        "oracle-26ai-vectors",
        "Oracle 26ai introduces a native VECTOR(N, FLOAT32) column type "
        "with HNSW and IVF organisations.",
        "AI Vector Search",
    ),
    (
        2,
        "oracle-26ai-similarity",
        "VECTOR_DISTANCE(col, :query, COSINE) returns the cosine distance "
        "between a stored vector and a query vector.",
        "AI Vector Search",
    ),
    (
        3,
        "adb-wallets",
        "Autonomous Database wallets bundle a tnsnames.ora alias per "
        "consumer group — _low, _medium, _high, _tp, _tpurgent.",
        "Autonomous Database",
    ),
]


def _missing_env() -> list[str]:
    return [name for name in _REQUIRED_ENV if not os.environ.get(name)]


def _print_skip_banner(missing: list[str]) -> None:
    print("\n--- Tutorial 64: OracleADBLoader ---")
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
    from locus.rag.loaders import OracleADBLoader

    loader = OracleADBLoader(
        dsn=os.environ["ORACLE_DSN"],
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        wallet_location=os.environ["ORACLE_WALLET"],
        wallet_password=os.environ.get("ORACLE_WALLET_PASSWORD", ""),
        sql="SELECT id, slug, body, topic FROM articles WHERE topic = :topic",
        bind_params={"topic": "AI Vector Search"},
        content_column="body",
        id_column="slug",
        metadata_columns=["topic"],
    )
    async for doc in loader.lazy_load():
        print(doc.id, doc.content[:80])
    await loader.close()
        """.rstrip()
    )


def _conn_kwargs() -> dict[str, str]:
    """Connection envelope shared by the helper DDL/DML and the loader."""
    return {
        "dsn": os.environ["ORACLE_DSN"],
        "user": os.environ["ORACLE_USER"],
        "password": os.environ["ORACLE_PASSWORD"],
        "wallet_location": os.path.expanduser(os.environ["ORACLE_WALLET"]),
        "wallet_password": os.environ.get("ORACLE_WALLET_PASSWORD", ""),
    }


async def _setup_demo_table() -> None:
    """Create + populate ``locus_notebook_64_articles`` via plain ``oracledb``.

    Kept off the loader on purpose — the loader is a read-only primitive.
    For a one-shot notebook we issue the DDL/DML ourselves so the source
    rows exist before ``lazy_load()`` is called.
    """
    import oracledb

    kw = _conn_kwargs()
    params: dict[str, str] = {}
    if kw["wallet_location"]:
        params["config_dir"] = kw["wallet_location"]
        params["wallet_location"] = kw["wallet_location"]
        if kw["wallet_password"]:
            params["wallet_password"] = kw["wallet_password"]

    conn = await oracledb.connect_async(
        user=kw["user"],
        password=kw["password"],
        dsn=kw["dsn"],
        **params,
    )
    try:
        cursor = conn.cursor()
        # Best-effort drop in case a previous run left it behind.
        try:
            await cursor.execute(f"DROP TABLE {_TABLE}")
        except Exception:  # noqa: BLE001 - table may not exist; fine.
            pass
        await cursor.execute(
            f"""
            CREATE TABLE {_TABLE} (
                id      NUMBER PRIMARY KEY,
                slug    VARCHAR2(64) NOT NULL,
                body    CLOB NOT NULL,
                topic   VARCHAR2(64) NOT NULL
            )
            """
        )
        await cursor.executemany(
            f"INSERT INTO {_TABLE} (id, slug, body, topic) VALUES (:1, :2, :3, :4)",
            _DEMO_ROWS,
        )
        await conn.commit()
    finally:
        await conn.close()


async def _drop_demo_table() -> None:
    import oracledb

    kw = _conn_kwargs()
    params: dict[str, str] = {}
    if kw["wallet_location"]:
        params["config_dir"] = kw["wallet_location"]
        params["wallet_location"] = kw["wallet_location"]
        if kw["wallet_password"]:
            params["wallet_password"] = kw["wallet_password"]

    conn = await oracledb.connect_async(
        user=kw["user"],
        password=kw["password"],
        dsn=kw["dsn"],
        **params,
    )
    try:
        cursor = conn.cursor()
        try:
            await cursor.execute(f"DROP TABLE {_TABLE}")
        except Exception:  # noqa: BLE001 - already gone; fine.
            pass
        await conn.commit()
    finally:
        await conn.close()


async def main() -> None:
    missing = _missing_env()
    if missing:
        _print_skip_banner(missing)
        return

    print(f"Creating disposable demo table {_TABLE}…")
    await _setup_demo_table()

    loader = OracleADBLoader(
        **_conn_kwargs(),
        sql=(f"SELECT id, slug, body, topic FROM {_TABLE} WHERE topic = :topic ORDER BY id"),
        bind_params={"topic": "AI Vector Search"},
        content_column="body",
        id_column="slug",
        metadata_columns=["topic"],
    )

    try:
        print("\n--- lazy_load(): streaming rows as the cursor produces them ---")
        async for doc in loader.lazy_load():
            snippet = doc.content.replace("\n", " ")[:80]
            print(f"  id={doc.id!r}  topic={doc.metadata.get('topic')!r}  {snippet}")

        print("\n--- load(): eager variant returning list[Document] ---")
        docs = await loader.load()
        print(f"  retrieved {len(docs)} documents")
        for doc in docs:
            print(f"    - {doc.id}: {len(doc.content)} chars, metadata={doc.metadata}")
    finally:
        await loader.close()
        print(f"\nDropping demo table {_TABLE}…")
        await _drop_demo_table()

    print(
        "\nThe loader yielded Document objects directly from the ADB SELECT — "
        "feed them into RAGRetriever.add_documents() or an OracleInDBChunker "
        "(tutorial 65) without any langchain glue."
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
