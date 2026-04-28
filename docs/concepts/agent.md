# Agent

The `Agent` class is the primary entry point. You construct one by
passing a model, tools, a system prompt, and optional features
(reflexion, grounding, checkpointing).

```python
from locus import Agent, tool

@tool
def search(query: str) -> str:
    """Search the knowledge base."""
    return "results"

agent = Agent(
    model="openai:gpt-4o",
    tools=[search],
    system_prompt="You are a helpful assistant.",
    max_iterations=20,
)
```

## Running the agent

There are three ways to drive the agent:

```python
# 1. Streaming events (async, fine-grained)
async for event in agent.run("Do the task", thread_id="t1"):
    print(event)

# 2. Sync execution (blocks until done)
result = agent.run_sync("Do the task", thread_id="t1")
print(result.message)

# 3. Alias for sync
result = agent.invoke("Do the task", thread_id="t1")
```

All three drive the same underlying [ReAct loop](#the-react-loop). The
only difference is the surface: `run` yields `LocusEvent` values as the
loop progresses, `run_sync` / `invoke` return an `AgentResult` after
termination.

## The ReAct loop

Each iteration has three phases:

| Phase | What happens |
|---|---|
| **Think** | The model generates reasoning + optional tool calls. A `ThinkEvent` is emitted. |
| **Execute** | Tool calls run (in parallel, concurrently, or sequentially depending on `tool_execution`). `ToolStartEvent` / `ToolCompleteEvent` fire per tool. |
| **Reflect** | Optional: reflexion re-checks the result; grounding verifies factual claims against evidence. |

The loop terminates when:

- The model produces a response with no tool calls (classic ReAct),
- A [termination condition](../concepts/events.md) triggers,
- `max_iterations` is reached,
- The agent is cancelled via the cancel signal.

## Configuration

Everything is held in an `AgentConfig`. You can construct the config
explicitly and pass it, or let the `Agent` constructor build one from
keyword arguments.

```python
from locus import Agent
from locus.agent import AgentConfig

cfg = AgentConfig(
    model="oci:openai.gpt-5.5",   # see how-to/oci-models.md
    tools=[...],
    system_prompt="...",
    max_iterations=50,
    completion_mode="explicit",
    tool_execution="concurrent",
    max_concurrency=8,
    checkpointer=...,
    hooks=[...],
)

agent = Agent(config=cfg)
```

See the [API reference](../api/agent.md) for every field.
