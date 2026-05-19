#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Notebook 09: chunk text **inside the database** with ``OracleInDBChunker``.

Oracle 23ai / 26ai ships a server-side chunking primitive,
``DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS``. It tokenises and segments text
without ever shipping the content back to Python — the perfect first
stage of an ingest pipeline that already has the source CLOBs in the
database. Locus wraps it as
:class:`locus.rag.chunkers.OracleInDBChunker`.

Key concepts:

- ``OracleInDBChunker(dsn=..., max_tokens=20, overlap=0, by="words")``
  builds the chunker bound to an Autonomous Database wallet. Same
  connection envelope as the loader (notebook 08) and the vector store
  (notebook 06).
- ``await chunker.chunk_text(long_paragraph)`` returns
  ``[{chunk_id, offset, length, text}, …]`` for a single Python string
  — useful when you've already pulled the raw text out (loader output,
  uploaded blob, etc.).
- ``async for chunk in chunker.chunk_column(table_name=..., text_column=...)``
  streams chunks of *every row* in a table, with no Python round-trip
  for the source text. Each chunk carries the ``source_id`` of the row
  it came from so you can write the chunks into a vector store keyed
  back to the document.

Prerequisite (one-time, out-of-band)::

    GRANT EXECUTE ON DBMS_VECTOR_CHAIN TO locus_app;

Run it::

    export ORACLE_DSN=mydb_low                   # tnsnames alias in the wallet
    export ORACLE_USER=locus_app                 # least-privileged app schema
    export ORACLE_PASSWORD='<app-password>'
    export ORACLE_WALLET=~/.oci/wallets/mydb     # directory holding tnsnames.ora
    export ORACLE_WALLET_PASSWORD='<wallet-pw>'  # if the wallet is encrypted

    python examples/notebook_09_oracle_indb_chunker.py

If ``ORACLE_DSN`` / ``ORACLE_PASSWORD`` / ``ORACLE_WALLET`` aren't set
the notebook prints the wiring snippet and exits cleanly — no
traceback, no half-initialised state.

Difficulty: Intermediate. Self-contained — no prior notebook required.
"""

from __future__ import annotations

import asyncio
import os
import sys

from locus.rag.chunkers import OracleInDBChunker


_REQUIRED_ENV = (
    "ORACLE_DSN",
    "ORACLE_USER",
    "ORACLE_PASSWORD",
    "ORACLE_WALLET",
)


_TABLE = "locus_notebook_09_docs"


_LONG_PARAGRAPH = (
    "Oracle Database 26ai introduces native vector search through the "
    "VECTOR column type and the VECTOR_DISTANCE SQL function. Vectors "
    "live in a real column with a configurable dimension and storage "
    "format such as FLOAT32 or INT8. The CREATE VECTOR INDEX statement "
    "builds an HNSW or IVF index asynchronously after the first INSERT, "
    "and the database keeps it incrementally updated as new rows arrive. "
    "DBMS_VECTOR_CHAIN exposes server-side primitives for chunking, "
    "embedding, and reranking so the whole pipeline can run inside the "
    "database when data residency rules require it."
)


def _missing_env() -> list[str]:
    return [name for name in _REQUIRED_ENV if not os.environ.get(name)]


def _print_skip_banner(missing: list[str]) -> None:
    print("\n--- Notebook 09: OracleInDBChunker ---")
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
    print("\nPrerequisite (one-time, out-of-band):")
    print("    GRANT EXECUTE ON DBMS_VECTOR_CHAIN TO locus_app;")
    print("\nMinimal wiring (what the live path below builds):")
    print(
        """
    from locus.rag.chunkers import OracleInDBChunker

    chunker = OracleInDBChunker(
        dsn=os.environ["ORACLE_DSN"],
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        wallet_location=os.environ["ORACLE_WALLET"],
        wallet_password=os.environ.get("ORACLE_WALLET_PASSWORD", ""),
        max_tokens=20,
        overlap=0,
        by="words",
    )
    chunks = await chunker.chunk_text(long_paragraph)
    async for chunk in chunker.chunk_column(
        table_name="locus_notebook_09_docs",
        text_column="body",
    ):
        ...
        """.rstrip()
    )


def _conn_kwargs() -> dict[str, str]:
    return {
        "dsn": os.environ["ORACLE_DSN"],
        "user": os.environ["ORACLE_USER"],
        "password": os.environ["ORACLE_PASSWORD"],
        "wallet_location": os.path.expanduser(os.environ["ORACLE_WALLET"]),
        "wallet_password": os.environ.get("ORACLE_WALLET_PASSWORD", ""),
    }


async def _setup_demo_table() -> None:
    """Create + populate a tiny ``locus_notebook_09_docs`` table.

    Only used by the ``chunk_column`` leg of the demo. The single-string
    leg (:meth:`chunk_text`) needs no table at all.
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
        user=kw["user"], password=kw["password"], dsn=kw["dsn"], **params
    )
    try:
        cursor = conn.cursor()
        try:
            await cursor.execute(f"DROP TABLE {_TABLE}")
        except Exception:  # noqa: BLE001 - may not exist; fine.
            pass
        await cursor.execute(
            f"""
            CREATE TABLE {_TABLE} (
                id   NUMBER PRIMARY KEY,
                body CLOB NOT NULL
            )
            """
        )
        await cursor.execute(
            f"INSERT INTO {_TABLE} (id, body) VALUES (:1, :2)",
            (1, _LONG_PARAGRAPH),
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
        user=kw["user"], password=kw["password"], dsn=kw["dsn"], **params
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

    chunker = OracleInDBChunker(
        **_conn_kwargs(),
        max_tokens=20,
        overlap=0,
        by="words",
    )

    try:
        print("\n--- chunk_text(): one Python string → list of chunks ---")
        chunks = await chunker.chunk_text(_LONG_PARAGRAPH)
        print(f"Got {len(chunks)} chunks from a {len(_LONG_PARAGRAPH)}-char paragraph:")
        for c in chunks:
            preview = (c["text"] or "").replace("\n", " ")[:70]
            print(
                f"  chunk_id={c['chunk_id']:<3} "
                f"offset={c['offset']:<5} "
                f"length={c['length']:<5} "
                f"text={preview!r}"
            )

        print(f"\n--- chunk_column(): streaming chunks from table {_TABLE!r} ---")
        await _setup_demo_table()
        try:
            seen = 0
            async for chunk in chunker.chunk_column(
                table_name=_TABLE,
                text_column="body",
                id_column="id",
            ):
                if seen < 5:
                    preview = (chunk["text"] or "").replace("\n", " ")[:60]
                    print(
                        f"  source_id={chunk['source_id']} "
                        f"chunk_id={chunk['chunk_id']:<3} "
                        f"offset={chunk['offset']:<5} "
                        f"{preview!r}"
                    )
                seen += 1
            print(f"  … {seen} chunks total streamed from {_TABLE}.")
        finally:
            await _drop_demo_table()
    finally:
        await chunker.close()

    print(
        "\nUTL_TO_CHUNKS ran entirely DB-side. Pair with OracleInDBEmbeddings "
        "(notebook 10) for a fully in-database ingest pipeline."
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
