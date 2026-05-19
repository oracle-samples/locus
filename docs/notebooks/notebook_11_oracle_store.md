# Oracle 26ai Store (long-term memory)

Where the [Oracle 26ai checkpointer](notebook_07_oracle_26ai_checkpointer.md)
persists *per-thread* agent state, `OracleStore` persists *cross-thread*
facts: the namespaced key/value store the long-term-memory layer
reaches for when something needs to outlive any single conversation.
It is the locus-native equivalent of `langgraph-oracledb.OracleStore`
/ `AsyncOracleStore` — same schema shape, same surface area — but with
**zero** langchain / langgraph imports.

## What this covers

- Plain K/V mode: `put(namespace, key, value)` / `get(namespace, key)`
  against a CLOB JSON column, keyed on `(namespace, key)`.
- `list_namespaces(prefix=...)` enumerating every namespace beneath a
  parent — namespaces are `tuple[str, ...]` and flatten to `/`-joined
  strings inside the table.
- Vector mode: pass `dimension=N` and the store provisions a
  `VECTOR(N, FLOAT32)` column; `put_with_embedding` /
  `search_by_embedding` use the same `VECTOR_DISTANCE` SQL function
  the RAG store uses, but scoped to a namespace.

The notebook uses a tiny 4-dim fake embedding so the vector demo can
run without an embedding model. Real workloads hand in 1024-dim Cohere
V3 or 1536-dim Cohere V4 vectors.

## Prerequisites

The store, the [checkpointer](notebook_07_oracle_26ai_checkpointer.md),
the [versioned saver](notebook_12_oracle_versioned_saver.md), and the
[vector store](notebook_06_oracle_26ai_rag.md) can all share a single
Autonomous Database:

```bash
export ORACLE_DSN=mydb_low                   # tnsnames alias in the wallet
export ORACLE_USER=locus_app                 # least-privileged app schema
export ORACLE_PASSWORD='<app-password>'
export ORACLE_WALLET=~/.oci/wallets/mydb     # directory holding tnsnames.ora
export ORACLE_WALLET_PASSWORD='<wallet-pw>'  # if wallet is encrypted
```

If `ORACLE_DSN` / `ORACLE_PASSWORD` aren't set the notebook prints the
wiring snippet and exits cleanly — no traceback, no half-initialised
state.

## Run

```bash
python examples/notebook_11_oracle_store.py
```

## Schema hygiene

The notebook writes to `locus_notebook_11_store` (overridable via
`table_name=`) and drops the table at the end so the demo is
re-runnable. For production, pre-create the table out-of-band as a
least-privileged app schema owner and pass `auto_create_table=False`
so the runtime user runs with `INSERT / SELECT / UPDATE / DELETE`
only.

## See also

- [Notebook 07 — Oracle 26ai checkpointer](notebook_07_oracle_26ai_checkpointer.md)
- [Notebook 12 — Oracle 26ai versioned checkpoint saver](notebook_12_oracle_versioned_saver.md)
- [Oracle AI Database 26ai — AI Vector Search User's Guide](https://docs.oracle.com/en/database/oracle/oracle-database/23/vecse/index.html)

## Source

```python
--8<-- "examples/notebook_11_oracle_store.py"
```
