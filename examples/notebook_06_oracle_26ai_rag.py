#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Notebook 06: production RAG against Oracle Database 26ai with native vectors.

This is the Oracle-native RAG target on Oracle Cloud Infrastructure
(OCI). The retriever pipeline you'll see is the same one the in-memory
RAG notebooks use — only the store import changes — but here it is
backed by Oracle Database 26ai's native vector column and indexed for
production cosine similarity search.

Key concepts:

- ``VECTOR(N, FLOAT32)`` is 26ai's native vector column type. Embeddings
  live in a real column, not a JSON blob or a side index.
- ``VECTOR_DISTANCE(col, :query, COSINE)`` is the SQL function for
  similarity search. ``OracleVectorStore`` issues this under the hood.
- ``CREATE VECTOR INDEX ... ORGANIZATION NEIGHBOR PARTITIONS`` is 26ai's
  native HNSW/IVF index, built asynchronously after the first insert.
- ``OCIEmbeddings`` produces 1024-dim Cohere V3 vectors on OCI GenAI;
  ``OracleVectorStore`` opens an async pool against the Autonomous
  Database wallet and auto-creates the table on first use.
- ``RAGRetriever`` is the same class every other Locus RAG notebook
  uses — swap to in-memory, pgvector, Qdrant, or OpenSearch by changing
  only the store import.

Run it::

    # Database side — Autonomous Database wallet (TLS) + credentials.
    export ORACLE_DSN=mydb_low                  # tnsnames alias in the wallet
    export ORACLE_USER=locus_app                # least-privileged app schema
    export ORACLE_PASSWORD='<app-password>'
    export ORACLE_WALLET=~/.oci/wallets/mydb    # directory with tnsnames.ora
    export ORACLE_WALLET_PASSWORD='<wallet-pw>' # if the wallet is encrypted

    # Embedding side — OCI GenAI in us-chicago-1.
    export OCI_PROFILE=DEFAULT
    export OCI_REGION=us-chicago-1
    export OCI_COMPARTMENT=ocid1.compartment.oc1..xxx
    export OCI_AUTH_TYPE=api_key                # or security_token

    python examples/notebook_06_oracle_26ai_rag.py

If ``ORACLE_DSN`` / ``ORACLE_PASSWORD`` / ``OCI_COMPARTMENT`` aren't set
the notebook prints the wiring snippet and exits cleanly — no
traceback, no half-initialised state.

**Schema hygiene.** This notebook uses ``auto_create_table=True`` so the
demo provisions the table on first run. For production, create the
table out-of-band as a least-privileged app schema owner and set
``auto_create_table=False`` — see ``docs/concepts/rag.md`` for the
``CREATE USER locus_app`` and ``CREATE VECTOR INDEX`` DDL.

Difficulty: Intermediate. Self-contained — no prior notebook required.
"""

from __future__ import annotations

import asyncio
import os
import sys

from locus.rag import OCIEmbeddings, OracleVectorStore, RAGRetriever


_REQUIRED_ENV = (
    "ORACLE_DSN",
    "ORACLE_USER",
    "ORACLE_PASSWORD",
    "ORACLE_WALLET",
    "OCI_COMPARTMENT",
)


CORPUS = [
    "Oracle 26ai introduces a native VECTOR(N, FLOAT32) column type "
    "with HNSW and IVF index organisations.",
    "VECTOR_DISTANCE(embedding, :query, COSINE) returns the cosine "
    "distance between a stored vector and a query vector.",
    "Autonomous Database wallets bundle a tnsnames.ora alias per "
    "consumer group — _low, _medium, _high, _tp, _tpurgent.",
    "Locus exposes Oracle 26ai through OracleVectorStore; the same "
    "RAGRetriever drives every backend uniformly.",
    "A vector index on a VECTOR column is built asynchronously after "
    "the first INSERT, so the first query may be slower than steady-state.",
    "PostgreSQL stores embeddings through the pgvector extension, not a native type.",
]


QUERY = "How does Oracle 26ai store and search embeddings?"


def _missing_env() -> list[str]:
    return [name for name in _REQUIRED_ENV if not os.environ.get(name)]


def _print_skip_banner(missing: list[str]) -> None:
    print("\n--- Notebook 06: Oracle 26ai RAG ---")
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
    from locus.rag import OCIEmbeddings, OracleVectorStore, RAGRetriever

    embedder = OCIEmbeddings(
        model_id="cohere.embed-english-v3.0",
        profile_name=os.environ["OCI_PROFILE"],
        compartment_id=os.environ["OCI_COMPARTMENT"],
        service_endpoint=(
            f"https://inference.generativeai."
            f"{os.environ['OCI_REGION']}.oci.oraclecloud.com"
        ),
    )

    store = OracleVectorStore(
        dsn=os.environ["ORACLE_DSN"],
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        wallet_location=os.environ["ORACLE_WALLET"],
        wallet_password=os.environ.get("ORACLE_WALLET_PASSWORD", ""),
        dimension=1024,
    )

    retriever = RAGRetriever(embedder=embedder, store=store)
    await retriever.add_documents(corpus)
    hits = await retriever.retrieve("…", limit=3)
        """.rstrip()
    )


def _print_hits(title: str, hits) -> None:
    print(f"\n--- {title} ---")
    for i, hit in enumerate(hits.documents, start=1):
        snippet = hit.document.content.replace("\n", " ")[:110]
        print(f"  #{i}  score={hit.score:.4f}  {snippet}")


async def main() -> None:
    missing = _missing_env()
    if missing:
        _print_skip_banner(missing)
        return

    profile = os.environ.get("LOCUS_OCI_PROFILE") or os.environ.get("OCI_PROFILE", "DEFAULT")
    region = os.environ.get("LOCUS_OCI_REGION") or os.environ.get("OCI_REGION", "us-chicago-1")
    compartment = os.environ["OCI_COMPARTMENT"]
    auth_type = os.environ.get("LOCUS_OCI_AUTH_TYPE") or os.environ.get("OCI_AUTH_TYPE", "api_key")

    embedder = OCIEmbeddings(
        # 1024-dim Cohere V3 on OCI GenAI — matches the VECTOR(1024, FLOAT32) column.
        model_id="cohere.embed-english-v3.0",
        profile_name=profile,
        auth_type=auth_type,
        compartment_id=compartment,
        service_endpoint=(f"https://inference.generativeai.{region}.oci.oraclecloud.com"),
    )

    print("Opening pool against Oracle 26ai…")
    store = OracleVectorStore(
        dsn=os.environ["ORACLE_DSN"],
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        wallet_location=os.path.expanduser(os.environ["ORACLE_WALLET"]),
        wallet_password=os.environ.get("ORACLE_WALLET_PASSWORD", ""),
        # Demo defaults. For production, pre-create the table and pass
        # auto_create_table=False so the runtime user only needs DML.
        table_name="locus_notebook_06",
        dimension=1024,
        distance_metric="COSINE",
    )

    retriever = RAGRetriever(embedder=embedder, store=store)

    print(f"Embedding and inserting {len(CORPUS)} passages…")
    await retriever.add_documents(CORPUS)

    print(f"Query: {QUERY!r}")
    hits = await retriever.retrieve(QUERY, limit=3)
    _print_hits("Top-3 (VECTOR_DISTANCE, COSINE)", hits)

    print(
        "\nThe same RAGRetriever drove an Oracle 26ai vector search. "
        "Swap to OpenSearch, pgvector, Qdrant, or in-memory by changing "
        "the store import only."
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
