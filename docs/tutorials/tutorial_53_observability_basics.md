# Observability basics — opt-in SSE telemetry

Locus ships an in-process pub/sub `EventBus` that publishes typed
`StreamEvent`s for every meaningful step of execution: agent thinking,
tool calls, model completions, token usage, multi-agent fan-outs,
checkpoints — all under one canonical `event_type` per component.

Telemetry is opt-in. Code that never enters a `run_context` pays one
`ContextVar.get()` per emission site — no bus, no events, no
allocations.

Pipeline::

    with run_context() as rid:        ← activates emission; generates run_id
         │
         │  agent.run_sync(…)
         │      │
         │      ├─ agent.think         ← one per ReAct iteration
         │      ├─ agent.tool.started  ┐ span_id ties the pair
         │      ├─ agent.tool.completed┘
         │      ├─ agent.tokens.used   ← per model call (cost meter)
         │      └─ agent.terminate
         │
         └─ bus.subscribe(rid)         ← history replay + live stream

- Run an Agent with no telemetry (the SDK-default path).
- Wrap the same call in `run_context()` and subscribe to the bus.
- The canonical events: `agent.think`,
  `agent.tool.started/completed`, `agent.tokens.used`,
  `agent.terminate`.
- Read the per-run history buffer after the fact (replay semantics for
  late subscribers).

Run it (OCI Generative AI is the default; auto-detected from `~/.oci/config`):

    python examples/tutorial_53_observability_basics.py

Offline:

    LOCUS_MODEL_PROVIDER=mock python examples/tutorial_53_observability_basics.py

## Source

```python
--8<-- "examples/tutorial_53_observability_basics.py"
```
