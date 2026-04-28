# Streaming

Every locus agent emits typed events as it runs. They are real
classes, not strings — drop them into `match` statements and let the
type checker verify your handler is exhaustive.

```python
from locus.core.events import (
    ThinkEvent, ToolStartEvent, ToolCompleteEvent,
    ModelChunkEvent, ReflectEvent, TerminateEvent,
)

async for event in agent.run("Plan a trip to Paris."):
    match event:
        case ThinkEvent(reasoning=r) if r:
            print(f"💭 {r}")
        case ToolStartEvent(tool_name=n, args=a):
            print(f"🔧 {n}({a})")
        case ToolCompleteEvent(tool_name=n, result=r):
            print(f"   ↳ {r}")
        case ModelChunkEvent(text=t):
            print(t, end="", flush=True)        # token-level streaming
        case ReflectEvent(judgment=j):
            print(f"🪞 {j}")
        case TerminateEvent(final_message=m):
            print(f"\n✅ {m}")
```

## Event taxonomy

| Event | When |
|---|---|
| `ThinkEvent` | Model emits reasoning (extended-thinking models). |
| `ModelChunkEvent` | Each streamed text chunk. Pipe straight to a UI. |
| `ToolStartEvent` | Agent decided to call a tool. |
| `ToolCompleteEvent` | Tool returned (or raised). |
| `ReflectEvent` | Reflexion loop emitted a self-evaluation. |
| `IterationEvent` | A new ReAct iteration began (count + budget left). |
| `TerminateEvent` | The run is done — terminal condition met. |

Every event carries `agent_name`, `thread_id`, and a monotonic
sequence number — useful for multi-agent UIs that interleave streams
from several agents.

## Write-protected

Events are write-protected value objects. A hook *cannot* mutate one;
the type system enforces it. If a hook needs to influence the run, it
returns a control directive (e.g. `Cancel`, `Retry`).

## Sync wrapper

If you don't want to consume events, `agent.run_sync(prompt)` returns
the final `RunResult` directly.

## SSE over HTTP

The reference [AgentServer](server.md) maps the same events onto
Server-Sent Events for browser consumption — same shape, different
transport.

## Tutorials

- [`tutorial_04_agent_streaming.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_04_agent_streaming.py)
- [`tutorial_21_sse_streaming.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_21_sse_streaming.py)

## Source

`src/locus/streaming/` and `src/locus/core/events.py`.
