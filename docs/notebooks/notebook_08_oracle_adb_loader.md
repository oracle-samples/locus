# Oracle ADB Loader

The first link of any Oracle-native RAG pipeline is "get the source
rows out of the database as `Document` objects". Locus ships
`OracleADBLoader` for exactly this: it opens an async `oracledb` pool
against an Autonomous Database wallet, runs a single `SELECT`, and
yields one `Document` per row — the content column to
`Document.content`, an optional id column to `Document.id`, and every
other projected column into `Document.metadata`.

## What this covers

- `OracleADBLoader(dsn=..., user=..., password=..., wallet_location=...,
  sql=..., content_column=..., id_column=..., metadata_columns=[...])`
  — same connection envelope as `OracleVectorStore` and the
  `oracle_checkpointer`, so a single wallet block configures all three.
- `async for doc in loader.lazy_load():` — streaming the cursor row by
  row so memory stays flat on large pulls.
- `await loader.load()` — eager variant, returning `list[Document]`.
- `await loader.close()` — release the pool.

The notebook is self-contained: it creates a disposable demo table
`locus_notebook_64_articles`, populates three rows, walks the loader
through both call shapes, then drops the table.

## Prerequisites

```bash
# Autonomous Database wallet (TLS) + credentials.
export ORACLE_DSN=mydb_low                   # tnsnames alias in the wallet
export ORACLE_USER=locus_app                 # least-privileged app schema
export ORACLE_PASSWORD='<app-password>'
export ORACLE_WALLET=~/.oci/wallets/mydb     # directory holding tnsnames.ora
export ORACLE_WALLET_PASSWORD='<wallet-pw>'  # if wallet is encrypted
```

If `ORACLE_DSN` / `ORACLE_PASSWORD` / `ORACLE_WALLET` aren't set the
tutorial prints the wiring snippet and exits cleanly — no traceback,
no half-initialised state.

## Run

```bash
python examples/notebook_08_oracle_adb_loader.py
```

## See also

- [Tutorial 06 — Oracle 26ai RAG (native VECTOR)](notebook_06_oracle_26ai_rag.md)
- [Notebook 09 — Oracle in-DB chunker](notebook_09_oracle_indb_chunker.md)
- [Tutorial 66 — OracleInDBEmbeddings (DBMS_VECTOR_CHAIN.UTL_TO_EMBEDDING)](notebook_66_oracle_indb_embeddings.md)
- [Oracle AI Database 26ai — AI Vector Search User's Guide](https://docs.oracle.com/en/database/oracle/oracle-database/23/vecse/index.html)

## Source

```python
--8<-- "examples/notebook_08_oracle_adb_loader.py"
```
