# Swarm

A swarm is a peer-to-peer task pool. Agents pull tasks off a shared
queue, run them, and may post follow-up tasks for any peer to pick up.
Nobody is in charge.

```python
from locus.multiagent import Swarm

swarm = Swarm(
    agents=[researcher, summariser, fact_checker],
    shared_context={"topic": "Q3 launch"},
    max_iterations=8,
)

result = swarm.run_sync("Produce a launch brief on Q3.")
```

Each agent sees the `SharedContext` (a dict of keys any agent can read
or write) and the running task list. When an agent's `run` produces a
`ToolCall(create_task=...)` the new task is enqueued for the next
available peer.

## When to use

- **Open-ended research.** No fixed plan; whatever an agent finds may
  spawn new sub-tasks.
- **Heterogeneous specialists.** Each agent has different tools but
  any of them can pick up the next task they're qualified for.
- **Long-running batch.** A queue depth + a max-iteration budget is the
  natural shape.

## When not to use

- The flow is actually linear → use [Composition](composition.md).
- One agent should decide who runs → use [Orchestrator](orchestrator.md).
- You need the conversation transcript to follow one role to another →
  use [Handoff](handoff.md).

## Source

`src/locus/multiagent/swarm.py` — see also
[`tutorial_11_swarm_multiagent.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_11_swarm_multiagent.py).
