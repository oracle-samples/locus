# Oracle 26ai versioned checkpoint saver

Locus's native LangGraph-shape saver — versioned checkpoints plus
pending writes, two tables, one row per `(thread_id, checkpoint_ns,
checkpoint_id)`. Equivalent surface to
`langgraph-oracledb.OracleSaver` with **zero** langchain or langgraph
dependency.

Contrast with the simpler `oracle_checkpointer` from notebook 07:
that one MERGEs a single row per thread (latest wins). Reach for
`OracleCheckpointSaver` when you need history (time-travel, fork) or
intra-step durability (`put_writes` / `get_writes`).

## Prerequisites

```bash
export ORACLE_DSN=mydb_low
export ORACLE_USER=locus_app
export ORACLE_PASSWORD='<app-password>'
export ORACLE_WALLET=~/.oci/wallets/mydb
export ORACLE_WALLET_PASSWORD='<wallet-pw>'   # if encrypted
```

If those env vars aren't set the notebook prints a skip-banner and
exits cleanly — no traceback.

## Run

```bash
python examples/notebook_12_oracle_versioned_saver.py
```

## See also

- [Oracle 26ai checkpointer (single-row)](notebook_07_oracle_26ai_checkpointer.md)
- [Concepts → Checkpointers & Store](../concepts/checkpointers.md)

## Source

```python
--8<-- "examples/notebook_12_oracle_versioned_saver.py"
```
