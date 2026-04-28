# Events & streaming

Every observable step of a run is a typed Pydantic event, not a
callback. `agent.run(...)` is an `AsyncIterator[LocusEvent]`.

```python
from locus import Agent
from locus.core.events import (
    ThinkEvent, ToolStartEvent, ToolCompleteEvent, TerminateEvent,
)

async for event in agent.run("Plan a trip"):
    match event:
        case ThinkEvent(thought=t):
            print("thinking:", t)
        case ToolStartEvent(tool_name=n, arguments=a):
            print(f"calling {n}({a})")
        case ToolCompleteEvent(tool_name=n, result=r, error=e):
            print(f"done {n}: {e or r}")
        case TerminateEvent(reason=r, final_message=m):
            print(f"[{r}] {m}")
```

## Event types

| Event | When |
|---|---|
| `ThinkEvent` | Model produced reasoning (+ optional tool calls) |
| `ToolStartEvent` | About to invoke a tool |
| `ToolCompleteEvent` | Tool returned (or errored) |
| `ReflectEvent` | Reflexion cycle finished with new confidence |
| `GroundingEvent` | Grounding verified / disputed a claim |
| `ModelChunkEvent` | Streaming token from the LLM provider |
| `InterruptEvent` | A hook requested human-in-the-loop |
| `TerminateEvent` | Run ended (with `reason` and `final_message`) |

## SSE

For HTTP deployments, the FastAPI wrapper emits the event stream as
Server-Sent Events. Each event becomes one SSE frame with its JSON
payload.

## Termination conditions

Termination is also typed and composable. `|` is OR, `&` is AND:

```python
from locus.core.termination import (
    MaxIterations, TokenLimit, TextMention, TimeLimit, ToolCalled,
)

# Stop after 10 iterations OR when the model says "DONE".
condition = MaxIterations(10) | TextMention("DONE")

# Stop when BOTH: the confidence is high AND a specific tool was called.
condition = ConfidenceMet(0.9) & ToolCalled("send_summary")

agent = Agent(..., termination=condition)
```

Built-in conditions: `MaxIterations`, `TokenLimit`, `TextMention`,
`TimeLimit`, `ToolCalled`, `ConfidenceMet`, `NoToolCalls`,
`CustomCondition`.
