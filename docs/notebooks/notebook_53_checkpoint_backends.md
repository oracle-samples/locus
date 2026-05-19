# Checkpoint Backends

The checkpointer contract is backend-agnostic, but the production
recommendation on OCI is Oracle 26ai — native JSON columns, vector and
text indexes in one schema, and the full capability set
(`list_threads`, `search`, `vacuum`) over a single durable store.
Tutorial 06 covers the checkpointer contract itself; this tutorial
drives it against a real ADB.

- Save and load `AgentState` via `oracle_checkpointer`.
- Inspect the reported capabilities.
- Walk thread history with `list_threads` / `list_checkpoints`.
- Vacuum old checkpoints with `OracleBackend.vacuum`.
- Full-text search across stored conversations.

Run it (requires a running Autonomous Database with its wallet on disk):

    export ORACLE_DSN=mydb_low                   # tnsnames alias
    export ORACLE_USER=locus_app                 # least-privileged
    export ORACLE_PASSWORD='<app-password>'
    export ORACLE_WALLET=~/.oci/wallets/mydb
    export ORACLE_WALLET_PASSWORD='<wallet-pw>'  # if encrypted
    python examples/notebook_53_checkpoint_backends.py

Without the env vars the tutorial prints what's missing and exits
cleanly so CI stays green. The in-memory checkpointer covered in
[tutorial 10](notebook_15_agent_memory.md) is the developer default;
the [Oracle Database 26ai checkpointer](notebook_07_oracle_26ai_checkpointer.md)
covered in tutorial 06 is the production recommendation.

## Source

```python
--8<-- "examples/notebook_53_checkpoint_backends.py"
```
