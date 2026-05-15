# Checkpointers

A checkpointer is the contract for **persisting agent state** between
runs. Pass one to `Agent(checkpointer=...)` and the agent saves
`AgentState` after every iteration; resume a conversation by re-running
with the same `thread_id`. Same code, same context, different process,
different day.

This is the durability story for production agents. Without a
checkpointer your agent forgets every conversation when the process
exits. With one, the same `thread_id` round-trips through restarts,
across containers, and across regions.

```python
from locus import Agent
from locus.memory.backends import oci_bucket_checkpointer

agent = Agent(
    model="oci:openai.gpt-5.5",
    tools=[search, summarise],
    checkpointer=oci_bucket_checkpointer(
        bucket_name="my-app-checkpoints",
        namespace="my-tenancy-namespace",
    ),
)

# Day 1
agent.run_sync("I'm planning a trip to Tokyo.", thread_id="user-c42")

# Day 2 — different process, same thread_id, conversation continues
agent.run_sync("What were we discussing?", thread_id="user-c42")
```

## Picking a backend

| Situation | Backend |
|---|---|
| Unit tests, single-process REPL | `MemoryCheckpointer` |
| Local development, single machine | `FileCheckpointer` |
| Single-process durability with file overhead | `sqlite_checkpointer` |
| Multi-worker deployment, fast access, TTLs | `redis_checkpointer` |
| Postgres shop, want SQL queries on metadata | `postgresql_checkpointer` |
| Need full-text search across past runs | `opensearch_checkpointer` |
| Oracle Database shop, want JSON queries | `oracle_checkpointer` |
| **OCI-native, serverless, lifecycle policies** | `oci_bucket_checkpointer` — the day-1 OCI path |
| Already have a checkpoint service over HTTP | `HTTPCheckpointer` |

Default recommendation on OCI: `oci_bucket_checkpointer`. No DB to run,
no Redis to scale, lifecycle policies handle retention, IAM handles
auth.

## Getting started

### Local: `FileCheckpointer`

```python
from locus.memory.backends.file import FileCheckpointer

agent = Agent(
    model=...,
    tools=[...],
    checkpointer=FileCheckpointer(directory="./threads"),
)
```

One JSON file per `thread_id` in the directory. Zero dependencies,
plays well with `git stash` for "save my agent state" workflows.

### Production: `oci_bucket_checkpointer`

```python
from locus.memory.backends import oci_bucket_checkpointer

agent = Agent(
    model=...,
    tools=[...],
    checkpointer=oci_bucket_checkpointer(
        bucket_name="my-app-checkpoints",
        namespace="my-tenancy-namespace",
        compartment_id="ocid1.compartment...",
        prefix="prod/",
    ),
)
```

OCI Object Storage with bucket-level lifecycle rules ("delete threads
older than 90 days"), region replication, and IAM-controlled access.
Workers across processes / pods see the same threads.

### Postgres: `postgresql_checkpointer`

```python
from locus.memory.backends import postgresql_checkpointer

agent = Agent(
    model=...,
    tools=[...],
    checkpointer=postgresql_checkpointer(
        dsn="postgresql://user:pass@host:5432/locus",
        schema="locus_threads",
    ),
)
```

Tables auto-created on first save. Index on `thread_id` plus a JSONB
column for ad-hoc metadata queries.

### Redis: `redis_checkpointer`

```python
from locus.memory.backends import redis_checkpointer

agent = Agent(
    model=...,
    tools=[...],
    checkpointer=redis_checkpointer(
        url="redis://host:6379/0",
        ttl_seconds=86_400,        # auto-expire after 24h
    ),
)
```

Fastest reads, optional TTL for ephemeral conversations.

## Two checkpointer shapes — the gotcha to know

locus has **two** kinds of checkpointer implementations and you need
to wire them differently:

1. **Native checkpointers** implement `BaseCheckpointer` directly and
   accept `AgentState`:
   - `MemoryCheckpointer`, `FileCheckpointer`, `HTTPCheckpointer`,
     `OCIBucketBackend`.
   - Pass straight to `Agent(checkpointer=...)`.

2. **Storage backends** expose a simpler dict-shaped interface and
   need adapter wrapping:
   - `SQLiteBackend`, `RedisBackend`, `PostgreSQLBackend`,
     `OpenSearchBackend`, `OracleBackend`.
   - Use the factory function: `redis_checkpointer(...)`,
     `postgresql_checkpointer(...)`, etc.

```python
# WRONG — passing a storage backend directly will fail at save time
from locus.memory.backends.redis import RedisBackend
agent = Agent(..., checkpointer=RedisBackend(url="..."))   # ✗

# RIGHT — use the factory
from locus.memory.backends import redis_checkpointer
agent = Agent(..., checkpointer=redis_checkpointer(url="..."))  # ✓
```

The `*_checkpointer()` factory wraps the storage backend in a
`StorageBackendAdapter` that translates the agent's `save(state,
thread_id)` calls into the backend's `save(thread_id, dict)` shape.

## Capabilities — feature detection

Each backend advertises which optional operations it supports, so
your code can do the right thing at runtime:

```python
caps = checkpointer.capabilities

if caps.search:
    hits = await checkpointer.search("error handling")

if caps.branching:
    await checkpointer.copy_thread("main", "experiment")

if caps.vacuum:
    await checkpointer.vacuum(older_than_days=30)

if caps.list_threads:
    threads = await checkpointer.list_threads()
```

| Capability | What it adds |
|---|---|
| `search` | Full-text search across all stored checkpoints. |
| `metadata_query` | Query by metadata fields (tags, agent_id, etc). |
| `vacuum` | Delete checkpoints older than a threshold. |
| `branching` | Copy / fork a thread (great for "what-if" experiments). |
| `ttl` | Time-to-live / auto-expiration. |
| `list_threads` | Enumerate stored thread IDs. |
| `list_with_metadata` | List threads with their latest metadata. |
| `persistent_checkpoint_ids` | Checkpoint IDs survive restart. |

## Building your own

Subclass `BaseCheckpointer`, implement `save`, `load`,
`list_checkpoints`, `exists`, `delete`. Advertise your capabilities.
Pass the instance directly to `Agent(checkpointer=...)` — no glue
needed.

See [how-to/custom-checkpointer](../how-to/custom-checkpointer.md)
for a worked example.

## Cross-thread store

Checkpointers persist *one thread's* state. The companion abstraction —
`BaseStore` — persists key-value data **across** threads: a per-user
profile, long-term memory, anything that should outlive a single
conversation.

```python
from locus.memory.store import InMemoryStore   # tests / REPL
# or: SQLiteBackend, RedisBackend, PostgreSQLBackend, OracleBackend —
# every storage-backed checkpointer backend also implements BaseStore.

store = InMemoryStore()
store.put(("locus_memory", "user"), "role", {"content": "Senior Python engineer"})
hit = store.get(("locus_memory", "user"), "role")
```

The interface is `put / get / list / delete` keyed on a `(namespace,
key)` pair. The [`LLMMemoryManager`](memory-manager.md) builds on this
to give an agent a long-term memory layer; you can also use the store
directly for anything cross-thread that doesn't need LLM extraction
(API tokens, user preferences, rate-limit counters).

## Common gotchas

| Symptom | Likely cause |
|---|---|
| `AttributeError: 'RedisBackend' has no attribute 'save'` (with `state` arg) | Storage backend passed without the adapter. Use `redis_checkpointer(...)` factory instead. |
| Threads forgotten between deployments | `FileCheckpointer` directory inside an ephemeral container. Mount a volume, or move to `oci_bucket_checkpointer`. |
| Two replicas show different conversation state for the same thread | The checkpointer isn't shared between replicas. `FileCheckpointer` is per-host; switch to a centralised backend (Redis, Postgres, OCI bucket). |
| Slow first save | Some backends auto-create schema on first call. Pre-create in your deployment script if startup latency matters. |

## Source

- [`locus.memory.backends`](https://github.com/oracle-samples/locus/tree/main/src/locus/memory/backends) — every backend, plus `StorageBackendAdapter` and the `*_checkpointer()` factories.

## See also

- [State](state.md) — what `AgentState` actually contains.
- [Conversation management](conversation-management.md) — higher-level patterns built on checkpointers.
- [Idempotency](idempotency.md) — replay-safe side effects when a checkpoint resume re-issues a tool call.
- [How-to: custom checkpointer](../how-to/custom-checkpointer.md) — write your own backend.

### Oracle reference docs

- [OCI Object Storage — overview](https://docs.oracle.com/iaas/Content/Object/Concepts/objectstorageoverview.htm)
  — buckets, namespaces, IAM policies. Backs the `oci_bucket_checkpointer()` factory.
- [Oracle AI Database 26ai — AI Vector Search User's Guide](https://docs.oracle.com/en/database/oracle/oracle-database/23/vecse/index.html)
  — referenced by the Oracle 26ai checkpointer + vector store.
