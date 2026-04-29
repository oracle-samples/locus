# Persist conversations across restarts

The agent keeps conversation state in `AgentState`. Pass a
`BaseCheckpointer` and the same `thread_id` across invocations to
resume a conversation — even across process restarts.

## 1. Pick a backend

For single-machine development, `FileCheckpointer` (no deps) or
`sqlite_checkpointer()`. For production, pick by infrastructure:

- OCI Object Storage (serverless, lifecycle) → `OCIBucketBackend` (native)
- Redis cluster → `redis_checkpointer(...)`
- Managed Postgres → `postgresql_checkpointer(...)`
- OpenSearch cluster → `opensearch_checkpointer(...)`
- Oracle Database → `oracle_checkpointer(...)`

The first four (`MemoryCheckpointer`, `FileCheckpointer`,
`HTTPCheckpointer`, `OCIBucketBackend`) are native `BaseCheckpointer`
subclasses — pass the instance straight to `Agent`. The other five
expose a simpler dict-shaped storage interface and are wrapped via the
matching `*_checkpointer()` factory (or `StorageBackendAdapter`
directly).

## 2. Instantiate and pass to the Agent

Native checkpointer (no wrapping):

```python
from locus import Agent
from locus.memory.backends import OCIBucketBackend

checkpointer = OCIBucketBackend(
    bucket_name="my-app-checkpoints",
    namespace="my-namespace",
)

agent = Agent(
    model="oci:openai.gpt-5.5",   # any OCI model — see how-to/oci-models.md
    tools=[...],
    checkpointer=checkpointer,
)
```

Storage-backend with the factory:

```python
from locus.memory.backends import postgresql_checkpointer

checkpointer = postgresql_checkpointer(
    dsn="postgresql://locus:locus@db.example.com:5432/locus",
)
agent = Agent(model="oci:openai.gpt-5.5", tools=[...], checkpointer=checkpointer)
```

If you build a storage backend directly (`RedisBackend(...)`,
`PostgreSQLBackend(...)`, etc.) and pass the result to `Agent`, save /
load will fail at runtime — the agent calls
`checkpointer.save(state, thread_id)` and these classes expose
`save(thread_id, dict)`. Use the factory.

## 3. Use a stable thread_id

```python
# First turn — new thread
await agent.run("Plan a trip to Paris.", thread_id="user-42").__anext__()

# Second turn, possibly a different process instance
await agent.run("Now book the flights.", thread_id="user-42").__anext__()
```

The agent calls `checkpointer.load(thread_id)` at the start of every
run. If state exists, the new user turn is appended and the run
continues. If not, a fresh state is created.

## 4. Tune the checkpoint cadence

By default the agent writes a checkpoint at the end of every run. For
long runs with expensive tools, also write every N iterations:

```python
agent = Agent(
    ...,
    checkpointer=checkpointer,
    checkpoint_every_n_iterations=5,
)
```

## Testing it works

A brand-new `Agent` instance on the same `thread_id` should see the
prior conversation:

```python
agent1 = Agent(..., checkpointer=checkpointer)
await agent1.run("I'm Alex.", thread_id="t1").__anext__()
del agent1

# Simulates a process restart / different worker.
agent2 = Agent(..., checkpointer=checkpointer)
await agent2.run("Who am I?", thread_id="t1").__anext__()
# The model sees the earlier user turn.
```

Locus's integration suite has this exact test against a live OCI
bucket. See `tests/integration/test_checkpointer_adapters.py`.
