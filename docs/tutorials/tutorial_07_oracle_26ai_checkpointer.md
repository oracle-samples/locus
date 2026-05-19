# Oracle 26ai Checkpointer

In-memory and on-disk checkpointers are fine for local development —
when the process restarts, the conversation is gone. This tutorial
wires Locus's `oracle_checkpointer` adapter against an Oracle Cloud
Infrastructure (OCI) Autonomous Database 26ai so agent threads survive
process restarts, scale out across replicas, and can be picked up from
another machine.

## What this covers

- `oracle_checkpointer(...)` building a `StorageBackendAdapter` wrapped
  around `OracleBackend` — JSON `AgentState` persisted to a CLOB column
  keyed by `thread_id`.
- Two saves under the same thread id, across two function calls
  standing in for separate processes. The second run loads the saved
  `AgentState` and continues from there.
- `list_threads()` enumerating every persisted conversation — the
  primitive admin dashboards use.

## Prerequisites

The checkpointer and the vector store from tutorial 05 can share a
single Autonomous Database:

```bash
export ORACLE_DSN=mydb_low                   # tnsnames alias in the wallet
export ORACLE_USER=locus_app                 # least-privileged app schema
export ORACLE_PASSWORD='<app-password>'
export ORACLE_WALLET=~/.oci/wallets/mydb     # directory holding tnsnames.ora
export ORACLE_WALLET_PASSWORD='<wallet-pw>'  # if wallet is encrypted
```

If `ORACLE_DSN` / `ORACLE_PASSWORD` aren't set the tutorial prints the
wiring snippet and exits cleanly — no traceback, no half-initialised
state.

## Run

```bash
python examples/tutorial_07_oracle_26ai_checkpointer.py
```

## Schema hygiene

This tutorial writes to `locus_tutorial_06` (overridable via
`table_name=`). For production, pre-create the table out-of-band as a
least-privileged app schema owner and run the application user with
`INSERT / SELECT / UPDATE / DELETE` only — see the
[checkpointer concepts page](../concepts/checkpointers.md) for the DDL
and the rotation guidance.

## See also

- [Concepts — Checkpointers & Store](../concepts/checkpointers.md)
- [Tutorial 05 — Oracle 26ai RAG (shares the same wallet)](tutorial_06_oracle_26ai_rag.md)
- [Oracle AI Database 26ai — AI Vector Search User's Guide](https://docs.oracle.com/en/database/oracle/oracle-database/23/vecse/index.html)

## Source

```python
--8<-- "examples/tutorial_07_oracle_26ai_checkpointer.py"
```
