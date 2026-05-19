# Production RAG against Oracle Database 26ai with native vectors

The Oracle-native RAG target on Oracle Cloud Infrastructure (OCI).
Embeddings live in a real `VECTOR(N, FLOAT32)` column, similarity is
the `VECTOR_DISTANCE` SQL function, and the index is `CREATE VECTOR
INDEX ... ORGANIZATION NEIGHBOR PARTITIONS WITH DISTANCE COSINE` — all
native to Oracle Database 26ai. The retriever pipeline is the same one
the in-memory RAG tutorials use; only the store import changes.

## What this covers

- `OCIEmbeddings` producing 1024-dim Cohere V3 vectors on OCI GenAI.
- `OracleVectorStore` opening an async pool against an Autonomous
  Database wallet, auto-creating the table with a native
  `VECTOR(1024, FLOAT32)` column on first use, and serving cosine
  similarity queries via `VECTOR_DISTANCE`.
- `RAGRetriever` driving the search — swap to OpenSearch, pgvector,
  Qdrant, or in-memory by changing the store import only.

## Prerequisites

```bash
# Database side — Autonomous Database wallet (TLS) + credentials.
export ORACLE_DSN=mydb_low                   # tnsnames alias in the wallet
export ORACLE_USER=locus_app                 # least-privileged app schema
export ORACLE_PASSWORD='<app-password>'
export ORACLE_WALLET=~/.oci/wallets/mydb     # directory holding tnsnames.ora
export ORACLE_WALLET_PASSWORD='<wallet-pw>'  # if wallet is encrypted

# Embedding side — OCI GenAI on us-chicago-1.
export OCI_PROFILE=<your-profile>
export OCI_REGION=us-chicago-1
export OCI_COMPARTMENT=ocid1.compartment.oc1..…
export OCI_AUTH_TYPE=api_key                 # or security_token
```

If `ORACLE_DSN` / `ORACLE_PASSWORD` / `OCI_COMPARTMENT` aren't set the
tutorial prints the wiring snippet and exits cleanly — no traceback,
no half-initialised state.

## Run

```bash
python examples/tutorial_06_oracle_26ai_rag.py
```

## Schema hygiene

This tutorial uses `auto_create_table=True` so the demo provisions the
table on first run. For production, create the table out-of-band as a
least-privileged app schema owner and set `auto_create_table=False` so
the runtime user is restricted to DML only — see the
[Production setup section in the RAG concepts page](../concepts/rag.md#3-wire-the-retriever)
for the `CREATE USER locus_app` / `CREATE VECTOR INDEX` DDL.

## See also

- [Concepts — RAG (Oracle 26ai walkthrough)](../concepts/rag.md)
- [Tutorial 07 — Cohere Reranker V4 on top of Oracle 26ai (over-fetch + rerank)](tutorial_05_cohere_reranker.md)
- [Oracle AI Database 26ai — AI Vector Search User's Guide](https://docs.oracle.com/en/database/oracle/oracle-database/23/vecse/index.html)

## Source

```python
--8<-- "examples/tutorial_06_oracle_26ai_rag.py"
```
