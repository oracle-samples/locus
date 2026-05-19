# Oracle In-DB Embeddings

Oracle 23ai / 26ai can host ONNX embedding models *inside* the
database via `DBMS_VECTOR.LOAD_ONNX_MODEL`. When the model lives in
the DB the embedding generation happens DB-side: the application ships
text over the wire, the database produces the vector locally, and the
caller gets back a serialized `VECTOR` ready to write into a `VECTOR`
column. The canonical pattern when data residency rules forbid sending
text to a remote inference service, or when the latency budget can't
absorb a remote round-trip.

Locus wraps `DBMS_VECTOR_CHAIN.UTL_TO_EMBEDDING` /
`UTL_TO_EMBEDDINGS` as `OracleInDBEmbeddings`.

## What this covers

- `OracleInDBEmbeddings(model_name="ALL_MINILM_L12_V2", dimension=384,
  dsn=..., user=..., password=..., wallet_location=...)` — binds the
  embedder to an in-DB ONNX model. Same connection envelope as the
  loader (tutorial 64), chunker (tutorial 65), and vector store
  (tutorial 06).
- `await emb.embed(text)` — single text → `EmbeddingResult`
  (`.embedding` is `list[float]` of length `dimension`).
- `await emb.embed_batch([t1, t2, …])` — uses `UTL_TO_EMBEDDINGS` when
  available, with a per-text fallback for older patch levels.

## Prerequisites

```bash
# Autonomous Database wallet (TLS) + credentials.
export ORACLE_DSN=mydb_low                   # tnsnames alias in the wallet
export ORACLE_USER=locus_app                 # least-privileged app schema
export ORACLE_PASSWORD='<app-password>'
export ORACLE_WALLET=~/.oci/wallets/mydb     # directory holding tnsnames.ora
export ORACLE_WALLET_PASSWORD='<wallet-pw>'  # if wallet is encrypted
export OCI_INDB_MODEL=ALL_MINILM_L12_V2      # optional, defaults to this
```

The ONNX model must be loaded into the DB once, out-of-band:

```sql
BEGIN
    DBMS_VECTOR.LOAD_ONNX_MODEL(
        directory  => 'DM_DUMP',
        file_name  => 'all_MiniLM_L12_v2.onnx',
        model_name => 'ALL_MINILM_L12_V2');
END;
/

GRANT EXECUTE ON DBMS_VECTOR_CHAIN TO locus_app;
GRANT MINING MODEL SELECT ON ALL_MINILM_L12_V2 TO locus_app;
```

If `ORACLE_DSN` / `ORACLE_PASSWORD` / `ORACLE_WALLET` aren't set the
tutorial prints the wiring snippet and exits cleanly. If the model
isn't loaded the tutorial catches `ORA-29024` / `ORA-20100` / similar
from the SQL call and prints a friendly skip — no traceback in either
case.

## Run

```bash
python examples/notebook_10_oracle_indb_embeddings.py
```

## See also

- [Notebook 06 — Oracle 26ai RAG](notebook_06_oracle_26ai_rag.md)
- [Notebook 08 — Oracle ADB document loader](notebook_08_oracle_adb_loader.md)
- [Notebook 09 — Oracle in-DB chunker](notebook_09_oracle_indb_chunker.md)
- [Oracle AI Database 26ai — AI Vector Search User's Guide](https://docs.oracle.com/en/database/oracle/oracle-database/23/vecse/index.html)

## Source

```python
--8<-- "examples/notebook_10_oracle_indb_embeddings.py"
```
