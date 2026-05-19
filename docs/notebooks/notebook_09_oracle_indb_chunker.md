# Oracle In-DB Chunker

Oracle 23ai / 26ai ships a server-side chunking primitive,
`DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS`. It tokenises and segments text
without ever shipping the content back to Python — the perfect first
stage of an ingest pipeline that already has the source CLOBs in the
database. Locus wraps it as `OracleInDBChunker`.

## What this covers

- `OracleInDBChunker(dsn=..., max_tokens=20, overlap=0, by="words")` —
  same connection envelope as the loader (notebook 08) and the vector
  store (notebook 06).
- `await chunker.chunk_text(long_paragraph)` — single Python string in,
  list of `{chunk_id, offset, length, text}` rows out.
- `async for chunk in chunker.chunk_column(table_name=..., text_column=...)`
  — streams chunks of *every row* in a table, with no Python
  round-trip for the source text. Each chunk carries the `source_id`
  of the row it came from.

## Prerequisites

```bash
# Autonomous Database wallet (TLS) + credentials.
export ORACLE_DSN=mydb_low                   # tnsnames alias in the wallet
export ORACLE_USER=locus_app                 # least-privileged app schema
export ORACLE_PASSWORD='<app-password>'
export ORACLE_WALLET=~/.oci/wallets/mydb     # directory holding tnsnames.ora
export ORACLE_WALLET_PASSWORD='<wallet-pw>'  # if wallet is encrypted
```

One-time SQL prereq (out-of-band, as the schema owner):

```sql
GRANT EXECUTE ON DBMS_VECTOR_CHAIN TO locus_app;
```

If `ORACLE_DSN` / `ORACLE_PASSWORD` / `ORACLE_WALLET` aren't set the
notebook prints the wiring snippet and exits cleanly — no traceback,
no half-initialised state.

## Run

```bash
python examples/notebook_09_oracle_indb_chunker.py
```

## See also

- [Notebook 06 — Oracle 26ai RAG](notebook_06_oracle_26ai_rag.md)
- [Notebook 08 — Oracle ADB document loader](notebook_08_oracle_adb_loader.md)
- [Notebook 10 — Oracle in-DB embeddings](notebook_10_oracle_indb_embeddings.md)
- [Oracle AI Database 26ai — AI Vector Search User's Guide](https://docs.oracle.com/en/database/oracle/oracle-database/23/vecse/index.html)

## Source

```python
--8<-- "examples/notebook_09_oracle_indb_chunker.py"
```
