# Tutorial 52: Observability basics — opt-in SSE telemetry

Locus ships an in-process pub/sub ``EventBus`` that publishes typed
``StreamEvent``s for every meaningful step of execution: agent thinking,
tool calls, model completions, token usage, multi-agent fan-outs,
checkpoints — all under one canonical ``event_type`` per component.

Telemetry is **opt-in**. SDK users who never enter a ``run_context`` pay one
``ContextVar.get()`` per emission site — no bus, no events, no allocations.

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

This tutorial covers:

1. Running an Agent with no telemetry (the SDK-default path).
2. Wrapping the same call in ``run_context()`` and subscribing to the bus
   to see the full inner cognition.
3. The shape of the canonical events: ``agent.think``,
   ``agent.tool.started/completed``, ``agent.tokens.used``,
   ``agent.terminate``.
4. Reading the per-run history buffer after the fact (replay semantics
   for late subscribers).

Why this is differentiated:

* Zero cost when unused — the bus singleton is never instantiated unless
  a ``run_context`` is active, so production agents carry no telemetry
  overhead until you opt in.
* History replay: ``bus.subscribe(run_id)`` delivers the last 500 events
  for the run before switching to live mode, so a subscriber that joins
  mid-run doesn't miss the beginning.
* One import, one context manager — no hooks to register, no config
  to thread through the agent constructor.

Run::

    python examples/tutorial_52_observability_basics.py

Difficulty: Beginner
Prerequisites: tutorial_01_basic_agent (basic Agent)

## Source

```python
--8<-- "examples/tutorial_52_observability_basics.py"
```
