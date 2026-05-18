#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tutorial 60: retrieve-then-rerank with Cohere Reranker V4 (#216).

For RAG to be production-grade, embedding-only retrieval often isn't
enough — the embedding model sees query and document independently and
can mis-rank candidates whose surface form scores high but whose
semantic relevance is lower. A **cross-encoder reranker** sees the
query and each candidate together, so it catches relevance signals
embeddings miss.

The pattern:

  1. Embed the corpus once into a vector store.
  2. At query time, **over-fetch** a wide candidate set (e.g. top-50)
     cheaply from the embedding store.
  3. Have a reranker rescore each candidate against the query and
     return the top-N (e.g. top-5).
  4. Feed the top-N to the LLM as grounded context.

This tutorial shows the lift on a small medical corpus: a passage that
ranks 4th by embedding similarity to a hepcidin question is the
*actual* canonical answer — and the reranker promotes it to 1st.

What you'll see:

  * Baseline ordering (embedding only).
  * Reranked ordering (``CohereReranker`` over the OCI on-demand
    rerank-v4 wire — closes #216).
  * Side-by-side scores so the lift is visible.

Run with::

    export OCI_PROFILE=DEFAULT      # or your locus_app-typed profile
    export OCI_AUTH_TYPE=api_key    # or security_token
    export OCI_REGION=us-chicago-1
    export OCI_COMPARTMENT=ocid1.compartment.oc1..xxx
    python examples/tutorial_60_cohere_reranker.py

Difficulty: intermediate. Prerequisites: tutorial 22 (RAG basics).
"""

from __future__ import annotations

import asyncio
import os

from locus.rag import (
    CohereReranker,
    InMemoryVectorStore,
    OCIEmbeddings,
    RAGRetriever,
)


CORPUS = [
    "Iron is primarily absorbed in the duodenum and proximal jejunum of the small intestine.",
    "Phlebotomy is the first-line treatment for hereditary hemochromatosis.",
    "Ferritin is the primary iron storage protein and an acute-phase reactant.",
    (
        "Hepcidin, produced by the liver, is the master regulator of systemic iron homeostasis. "
        "It binds ferroportin and induces its degradation, blocking iron export from "
        "enterocytes and macrophages."
    ),
    "Transferrin saturation below 16% suggests iron deficiency.",
    "MRI T2* relaxometry is the gold standard for non-invasive iron quantification.",
    "Iron deficiency anemia is the most common nutritional deficiency worldwide.",
    "First-line treatment for iron deficiency anemia is oral ferrous sulfate.",
]


QUERY = "What is hepcidin's role in iron homeostasis?"


def _print_table(title: str, rows: list[tuple[int, float, str]]) -> None:
    print(f"\n--- {title} ---")
    for rank, score, content in rows:
        print(f"  #{rank}  score={score:.4f}  {content[:90]}")


async def main() -> None:
    profile = os.environ.get("LOCUS_OCI_PROFILE") or os.environ.get("OCI_PROFILE", "DEFAULT")
    region = os.environ.get("LOCUS_OCI_REGION") or os.environ.get("OCI_REGION", "us-chicago-1")
    compartment = os.environ.get("LOCUS_OCI_COMPARTMENT") or os.environ.get("OCI_COMPARTMENT")
    auth_type = os.environ.get("LOCUS_OCI_AUTH_TYPE") or os.environ.get("OCI_AUTH_TYPE", "api_key")

    if not compartment:
        print("Set OCI_COMPARTMENT (or LOCUS_OCI_COMPARTMENT) — required for OCI GenAI calls.")
        return

    embedder = OCIEmbeddings(
        model_id="cohere.embed-english-v3.0",
        profile_name=profile,
        auth_type=auth_type,
        compartment_id=compartment,
        service_endpoint=f"https://inference.generativeai.{region}.oci.oraclecloud.com",
    )

    store = InMemoryVectorStore(dimension=1024)
    print(f"Embedding {len(CORPUS)} passages and seeding InMemoryVectorStore…")
    baseline = RAGRetriever(embedder=embedder, store=store)
    await baseline.add_documents(CORPUS)

    # ------------------------------------------------------------------
    # 1. Baseline retrieval — embedding similarity only.
    # ------------------------------------------------------------------
    print(f"\nQuery: {QUERY!r}")
    baseline_hits = await baseline.retrieve(QUERY, limit=4)
    _print_table(
        "Baseline (embedding similarity)",
        [(i + 1, h.score, h.document.content) for i, h in enumerate(baseline_hits.documents)],
    )

    # ------------------------------------------------------------------
    # 2. Retrieve-then-rerank — over-fetch + Cohere V4 cross-encoder.
    # ------------------------------------------------------------------
    reranker = CohereReranker(
        model="cohere.rerank-v4.0-fast",  # frontier V4 fast on OCI on-demand
        compartment_id=compartment,
        profile_name=profile,
        auth_type=auth_type,
        region=region,
        top_n=4,
    )
    reranked_retriever = RAGRetriever(
        embedder=embedder,
        store=store,
        reranker=reranker,
        rerank_candidate_pool=len(CORPUS),  # rerank the whole corpus
    )
    reranked_hits = await reranked_retriever.retrieve(QUERY, limit=4)
    _print_table(
        "Reranked (Cohere V4 cross-encoder)",
        [(i + 1, h.score, h.document.content) for i, h in enumerate(reranked_hits.documents)],
    )

    # ------------------------------------------------------------------
    # 3. The lift — show where the canonical answer ranked under each.
    # ------------------------------------------------------------------
    canonical_marker = "Hepcidin, produced by the liver"
    baseline_rank = next(
        (
            i + 1
            for i, h in enumerate(baseline_hits.documents)
            if h.document.content.startswith(canonical_marker)
        ),
        None,
    )
    reranked_rank = next(
        (
            i + 1
            for i, h in enumerate(reranked_hits.documents)
            if h.document.content.startswith(canonical_marker)
        ),
        None,
    )
    print(
        f"\nCanonical hepcidin passage rank: baseline = {baseline_rank}, reranked = {reranked_rank}"
    )
    print(
        "→ Reranking promoted the canonical answer to the top position even though "
        "embedding similarity placed less-relevant passages above it.\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
