# Tutorial 53: Agent yield bridge + token usage

Every ``Agent.run`` is decorated with ``@_bus_bridge`` so the nine typed
events it yields get republished on the bus as ``agent.*`` events when a
``run_context`` is open. No hook registration, no config flag — the bridge
is always there; it only fires when telemetry is active.

Event mapping::

    LocusEvent (inner stream)       →  bus event_type
    ─────────────────────────────────────────────────
    ThinkEvent                      →  agent.think
    ToolStartEvent                  →  agent.tool.started   ┐ share span_id
    ToolCompleteEvent               →  agent.tool.completed ┘
    ReflectEvent                    →  agent.reflect
    GroundingEvent                  →  agent.grounding
    ModelChunkEvent                 →  agent.model.chunk      (streaming)
    ModelCompleteEvent              →  agent.model.completed
                                    +  agent.tokens.used      (extra event)
    InterruptEvent                  →  agent.interrupt
    TerminateEvent                  →  agent.terminate

This tutorial covers:

1. How nine yielded ``LocusEvent`` types map to ``agent.*`` bus events.
2. Tool-call telemetry with ``span_id`` pairing —
   ``agent.tool.started`` and ``agent.tool.completed`` share an id so
   consumers can compute durations without subtracting timestamps.
3. Token usage as a first-class event — what ``agent.tokens.used``
   carries and how to plug it into a cost meter.

Why this is differentiated:

* ``span_id`` pairing survives interleaved events from concurrent runs —
  match on ``span_id``, not on order.
* Text previews are capped at 240 characters so the bus stays cheap; full
  payloads live on the underlying ``LocusEvent`` stream if you need them.
* ``agent.tokens.used`` fires even on providers that embed usage in the
  completion body — one canonical place for a cost dashboard to subscribe.

Run::

    python examples/tutorial_53_agent_yield_bridge.py

Difficulty: Intermediate
Prerequisites: tutorial_02_agent_with_tools (tools), tutorial_52_observability_basics
(observability basics)

## Source

```python
--8<-- "examples/tutorial_53_agent_yield_bridge.py"
```
