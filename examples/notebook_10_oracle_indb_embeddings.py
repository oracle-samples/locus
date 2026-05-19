#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Notebook 10: in-database embeddings with ``OracleInDBEmbeddings``.

Oracle 23ai / 26ai can host ONNX embedding models *inside* the
database (via ``DBMS_VECTOR.LOAD_ONNX_MODEL``). When the model lives
in the DB the embedding generation happens DB-side: the application
ships text over the wire, the database produces the vector locally,
and the caller gets back a serialized ``VECTOR`` ready to write into
a ``VECTOR`` column. This is the canonical pattern when data residency
rules forbid sending text out to OCI GenAI / OpenAI / a third-party
endpoint, or when the latency budget can't absorb a remote round-trip.

Locus wraps the in-DB primitives — ``DBMS_VECTOR_CHAIN.UTL_TO_EMBEDDING``
and ``UTL_TO_EMBEDDINGS`` — as
:class:`locus.rag.embeddings.oracle_indb.OracleInDBEmbeddings`.

Key concepts:

- ``OracleInDBEmbeddings(model_name="ALL_MINILM_L12_V2", dimension=384,
  dsn=..., user=..., password=..., wallet_location=...)`` binds the
  embedder to an in-DB ONNX model. The connection envelope mirrors the
  loader, chunker, and vector store.
- ``await emb.embed(text)`` returns a single
  :class:`EmbeddingResult` (``.embedding`` is ``list[float]`` of length
  ``dimension``).
- ``await emb.embed_batch([t1, t2, …])`` batches via
  ``UTL_TO_EMBEDDINGS`` when available, with a per-text fallback for
  older patch levels.

Prerequisites
-------------

The ONNX model must be loaded into the database before this notebook
can run a query. Typical one-time path::

    BEGIN
        DBMS_VECTOR.LOAD_ONNX_MODEL(
            directory  => 'DM_DUMP',
            file_name  => 'all_MiniLM_L12_v2.onnx',
            model_name => 'ALL_MINILM_L12_V2');
    END;
    /

And the schema running this notebook needs the grants::

    GRANT EXECUTE ON DBMS_VECTOR_CHAIN TO locus_app;
    GRANT MINING MODEL SELECT ON ALL_MINILM_L12_V2 TO locus_app;

The notebook accepts ``OCI_INDB_MODEL`` as an env override for the
model name (default ``ALL_MINILM_L12_V2``). If the model isn't loaded
in the target DB, the live path will catch ``ORA-29024`` / ``ORA-20100``
/ similar and skip-banner cleanly instead of stack-tracing.

Run it::

    export ORACLE_DSN=mydb_low                   # tnsnames alias in the wallet
    export ORACLE_USER=locus_app                 # least-privileged app schema
    export ORACLE_PASSWORD='<app-password>'
    export ORACLE_WALLET=~/.oci/wallets/mydb     # directory holding tnsnames.ora
    export ORACLE_WALLET_PASSWORD='<wallet-pw>'  # if the wallet is encrypted
    export OCI_INDB_MODEL=ALL_MINILM_L12_V2      # optional — defaults to this

    python examples/notebook_10_oracle_indb_embeddings.py

If ``ORACLE_DSN`` / ``ORACLE_PASSWORD`` / ``ORACLE_WALLET`` aren't set
the tutorial prints the wiring snippet and exits cleanly — no
traceback, no half-initialised state.

Difficulty: Intermediate. Self-contained — no prior tutorial required.
"""

from __future__ import annotations

import asyncio
import os
import sys

from locus.rag.embeddings.oracle_indb import OracleInDBEmbeddings


_REQUIRED_ENV = (
    "ORACLE_DSN",
    "ORACLE_USER",
    "ORACLE_PASSWORD",
    "ORACLE_WALLET",
)


# Default to the most common ONNX model loaded into 23ai / 26ai demos.
# Override via ``OCI_INDB_MODEL`` if your database has a different one.
_DEFAULT_MODEL = "ALL_MINILM_L12_V2"
_DEFAULT_DIM = 384


def _missing_env() -> list[str]:
    return [name for name in _REQUIRED_ENV if not os.environ.get(name)]


def _print_skip_banner(missing: list[str]) -> None:
    print("\n--- Notebook 10: OracleInDBEmbeddings ---")
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
    print(
        "\nPrerequisite: the ONNX model must be loaded into the DB once via "
        "DBMS_VECTOR.LOAD_ONNX_MODEL, and the schema needs:\n"
        "    GRANT EXECUTE ON DBMS_VECTOR_CHAIN TO locus_app;\n"
        "    GRANT MINING MODEL SELECT ON ALL_MINILM_L12_V2 TO locus_app;"
    )
    print("\nMinimal wiring (what the live path below builds):")
    print(
        """
    from locus.rag.embeddings.oracle_indb import OracleInDBEmbeddings

    emb = OracleInDBEmbeddings(
        model_name=os.environ.get("OCI_INDB_MODEL", "ALL_MINILM_L12_V2"),
        dimension=384,
        dsn=os.environ["ORACLE_DSN"],
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        wallet_location=os.environ["ORACLE_WALLET"],
        wallet_password=os.environ.get("ORACLE_WALLET_PASSWORD", ""),
    )
    vec = await emb.embed("hello world")
    vecs = await emb.embed_batch(["foo", "bar", "baz"])
    await emb.close()
        """.rstrip()
    )


def _print_model_skip_banner(model: str, exc: Exception) -> None:
    print("\n--- Notebook 10: OracleInDBEmbeddings ---")
    print(
        f"The ONNX model {model!r} isn't loaded (or accessible) in the "
        "target database, so the live path can't run.\n"
    )
    print(f"Driver / DB reported:\n  {type(exc).__name__}: {exc}")
    print(
        "\nLoad the model once via DBMS_VECTOR.LOAD_ONNX_MODEL "
        "and grant 'MINING MODEL SELECT' on it to the runtime user, "
        "then re-run. Or set OCI_INDB_MODEL to a model that's already "
        "loaded in your DB."
    )


def _is_missing_model_error(exc: BaseException) -> bool:
    """Heuristic: did the DB tell us the ONNX model isn't there?"""
    text = str(exc)
    return any(
        marker in text
        for marker in ("ORA-29024", "ORA-20100", "ORA-04063", "ORA-20000", "ORA-40284")
    )


async def main() -> None:
    missing = _missing_env()
    if missing:
        _print_skip_banner(missing)
        return

    model_name = os.environ.get("OCI_INDB_MODEL", _DEFAULT_MODEL)

    emb = OracleInDBEmbeddings(
        model_name=model_name,
        dimension=_DEFAULT_DIM,
        dsn=os.environ["ORACLE_DSN"],
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        wallet_location=os.path.expanduser(os.environ["ORACLE_WALLET"]),
        wallet_password=os.environ.get("ORACLE_WALLET_PASSWORD", ""),
    )

    try:
        print(f"\n--- embed(): single text → list[float] (model={model_name}) ---")
        try:
            result = await emb.embed("hello world")
        except Exception as exc:  # noqa: BLE001 - we want to detect ORA-* and skip.
            if _is_missing_model_error(exc):
                _print_model_skip_banner(model_name, exc)
                return
            raise

        vec = result.embedding
        head = ", ".join(f"{x:+.4f}" for x in vec[:5])
        print(f"  text     : {result.text!r}")
        print(f"  dimension: {len(vec)}")
        print(f"  first 5  : [{head}, …]")

        print("\n--- embed_batch(): three texts → three vectors ---")
        batch = await emb.embed_batch(["foo", "bar", "baz"])
        for r in batch:
            print(f"  text={r.text!r:<8}  dim={len(r.embedding)}  model={r.model}")
    finally:
        await emb.close()

    print(
        "\nThe vectors were generated entirely DB-side via "
        "DBMS_VECTOR_CHAIN.UTL_TO_EMBEDDING — no text ever left the database. "
        "Pair with OracleVectorStore (notebook 06) to keep the full pipeline in-DB."
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
