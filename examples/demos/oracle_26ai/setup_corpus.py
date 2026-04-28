"""One-shot ingest of the demo corpus into Oracle 26ai.

Run once before ``demo.py``. Idempotent — re-running just no-ops if the
table already has data.

Required env vars:
    OCI_PROFILE          — OCI config profile (default DEFAULT)
    ORACLE_PASSWORD      — ADB ADMIN password
    ORACLE_WALLET        — wallet directory (default ~/.oci/wallets/deepresearch)
    ORACLE_DSN           — TNS alias (default deepresearch_low)
"""

from __future__ import annotations

import asyncio
import os

from locus.rag import OCIEmbeddings, OracleVectorStore, RAGRetriever


CORPUS = [
    (
        "hnsw",
        "Hierarchical Navigable Small World (HNSW) is a graph-based "
        "approximate nearest-neighbor index. Each node connects to neighbors "
        "at multiple layers; queries descend from the top layer to local "
        "neighborhoods. Search is logarithmic in corpus size and routinely "
        "beats inverted-file methods on recall at the same latency. Malkov "
        "and Yashunin published the seminal paper in 2018.",
    ),
    (
        "ivf",
        "Inverted-file (IVF) indexes partition the vector space into Voronoi "
        "cells and search only the cells closest to the query. They trade "
        "recall for throughput: smaller `nprobe` is faster but less accurate. "
        "Faiss popularised IVF on GPUs; Oracle 26ai supports IVF via "
        "ORGANIZATION NEIGHBOR PARTITIONS for billion-scale workloads.",
    ),
    (
        "rag",
        "Retrieval-Augmented Generation grounds an LLM in an external "
        "corpus by retrieving relevant passages at query time and prepending "
        "them to the prompt. Lewis et al. (NeurIPS 2020) introduced the term. "
        "Modern systems chunk at 500-1000 tokens, embed with a strong "
        "encoder, and store in a vector index — exactly the pipeline this "
        "demo runs.",
    ),
    (
        "embeddings",
        "Embedding models map text to dense vectors where semantic "
        "similarity corresponds to cosine distance. Cohere's "
        "embed-english-v3 produces 1024-dim vectors and is hosted on OCI "
        "GenAI. Larger dimensions cost more storage and search time; 1024 is "
        "the sweet spot for most retrieval workloads.",
    ),
    (
        "reflexion",
        "Reflexion (Shinn et al., 2023) lets an agent self-evaluate after "
        "each iteration: did my last step make progress? If not, the agent "
        "revises its approach instead of stacking another tool call on top "
        "of a wrong premise. Locus exposes Reflexion as `reflexion=True` on "
        "Agent — no separate library, no agent rewrite.",
    ),
]


async def main():
    profile = os.environ.get("OCI_PROFILE", "DEFAULT")
    wallet = os.environ.get("ORACLE_WALLET", os.path.expanduser("~/.oci/wallets/deepresearch"))
    pw = os.environ["ORACLE_PASSWORD"]

    # Tenancy root is fine as the compartment for free-tier accounts.
    embedder = OCIEmbeddings(
        model_id="cohere.embed-english-v3.0",
        profile_name=profile,
        compartment_id=os.environ.get(
            "OCI_COMPARTMENT",
            "ocid1.tenancy.oc1..aaaaaaaaqlhpnytg33ztkwrdpq62p5yxx5gn5ltmkah23m7qebwjzc7x3lcq",
        ),
        service_endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
    )

    store = OracleVectorStore(
        dsn=os.environ.get("ORACLE_DSN", "deepresearch_low"),
        user="ADMIN",
        password=pw,
        wallet_location=wallet,
        wallet_password=pw,
        dimension=1024,
        table_name="LOCUS_DEMO_DOCS",
    )

    retriever = RAGRetriever(embedder=embedder, store=store)

    already = await retriever.retrieve("HNSW", limit=1)
    if already.documents:
        print(f"Corpus already populated ({len(CORPUS)} docs) — skipping ingest.")
        return

    print(f"Ingesting {len(CORPUS)} documents into Oracle 26ai…")
    for doc_id, content in CORPUS:
        await retriever.add_document(content, doc_id=doc_id, chunk=False)
        print(f"  + {doc_id}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
