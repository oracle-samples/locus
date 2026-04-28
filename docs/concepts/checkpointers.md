# Checkpointers

`BaseCheckpointer` is the contract for persisting agent state. Pass an
instance to `Agent(checkpointer=...)` and the agent saves state after
every iteration (or every N, via `checkpoint_every_n_iterations`).
Resuming a conversation is as simple as re-running with the same
`thread_id`.

```python
from locus import Agent
from locus.memory.backends import OCIBucketBackend

checkpointer = OCIBucketBackend(
    bucket_name="my-app-checkpoints",
    namespace="my-namespace",
)

agent = Agent(..., checkpointer=checkpointer)

# First turn
await agent.run("Plan a trip to Paris.", thread_id="user-42").__anext__()

# Later, possibly in a different process: same thread_id, state resumes.
await agent.run("Now book the flights.", thread_id="user-42").__anext__()
```

## Shipped backends

| Backend | Persistence | Good for |
|---|---|---|
| `MemoryCheckpointer` | In-process dict | Unit tests, single-process REPL |
| `FileCheckpointer` | Local JSON files | Development, single-machine |
| `HTTPCheckpointer` | Remote HTTP API | You already have a checkpoint service |
| `SQLiteBackend` | SQLite DB | Single-machine durability |
| `RedisBackend` | Redis | Fast, with TTL |
| `PostgreSQLBackend` | PostgreSQL | Traditional DB, metadata queries |
| `OpenSearchBackend` | OpenSearch | Full-text search across runs |
| `OracleBackend` | Oracle Database | Enterprise, with JSON search |
| `OCIBucketBackend` | OCI Object Storage | Serverless, lifecycle policies |

All of them implement `BaseCheckpointer` natively. There is no adapter
layer. You pass the instance directly to `Agent`.

## Capabilities

Every backend advertises its capabilities so you can pick features
conditionally:

```python
if checkpointer.capabilities.search:
    hits = await checkpointer.search("error handling")
if checkpointer.capabilities.branching:
    await checkpointer.copy_thread("main", "experiment")
if checkpointer.capabilities.vacuum:
    await checkpointer.vacuum(older_than_days=30)
```

Capability flags:

- `search` — full-text search across checkpoints
- `metadata_query` — query by metadata fields
- `vacuum` — delete old checkpoints
- `branching` — copy/fork threads
- `ttl` — time-to-live / auto-expiration
- `list_threads` — enumerate thread IDs
- `list_with_metadata` — per-thread latest metadata
- `persistent_checkpoint_ids` — IDs survive restart

## Building your own

See [how-to/custom-checkpointer](../how-to/custom-checkpointer.md)
for a worked example. The short version is: subclass
`BaseCheckpointer`, implement `save`, `load`, `list_checkpoints`,
`delete`. Advertise your capabilities. You can pass the instance
directly to `Agent` — no glue required.
