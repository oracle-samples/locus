# Persist conversations across restarts

The agent keeps conversation state in `AgentState`. Pass a
`BaseCheckpointer` and the same `thread_id` across invocations to
resume a conversation — even across process restarts.

## 1. Pick a backend

For single-machine development, `FileCheckpointer` or
`SQLiteBackend`. For production, pick by infrastructure:

- Redis cluster → `RedisBackend`
- Managed Postgres → `PostgreSQLBackend`
- OpenSearch cluster → `OpenSearchBackend`
- OCI Object Storage (serverless, lifecycle) → `OCIBucketBackend`

## 2. Instantiate and pass to the Agent

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

No adapter wrapping. The backend *is* a checkpointer.

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
