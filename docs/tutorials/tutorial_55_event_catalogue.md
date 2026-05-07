# Tutorial 55: Full event catalogue tour

Every component in Locus emits typed events under one stable prefix:
``agent.*``, ``multiagent.*``, ``composition.*``, ``router.*``, ``rag.*``,
``memory.*``, ``a2a.*``, ``skills.*``, ``deepagent.*``. The ``EV_*``
constants in ``locus.observability.emit`` are the canonical registry —
change one name and it propagates to every emission site and every consumer.

Prefix map::

    agent.*          ReAct loop (think, tool, model, tokens, reflect, …)
    multiagent.*     Orchestrator, Specialist, Handoff, StateGraph nodes
    composition.*    SequentialPipeline, ParallelPipeline, LoopAgent
    router.*         PRISM dispatch (frame → protocol → policy → compiled)
    rag.*            Retriever query lifecycle
    memory.*         Checkpointing + conversation management
    a2a.*            Agent-to-Agent protocol (server + client)
    skills.*         Skill activation
    deepagent.*      Research-shaped agent (subagents, fs, todos)

This tutorial covers:

1. Listing every ``EV_*`` constant and its category prefix — useful when
   wiring a renderer or a JSON log adapter.
2. Driving an Orchestrator + Specialist run that surfaces ``multiagent.*``
   events end-to-end, confirming routing, decision, and completion.
3. Running a ``SequentialPipeline`` + ``LoopAgent`` that emits the full
   ``composition.*`` event set.

Why this is differentiated:

* All ``EV_*`` constants are enumerated at import time from
  ``locus.observability.emit`` — the catalogue in this tutorial is always
  in sync with the codebase, not a static doc that can drift.
* Every prefix is exercised by a real run so you can copy the subscriber
  pattern for whichever component you're instrumenting.
* See [SSE event catalogue](../concepts/sse-events.md) for the full
  wire-format reference with payload field descriptions.

Run::

    python examples/tutorial_55_event_catalogue.py

Difficulty: Intermediate
Prerequisites: tutorial_17_orchestrator_pattern (orchestrator),
tutorial_25_composition (composition), tutorial_52_observability_basics
(observability basics)

## Source

```python
--8<-- "examples/tutorial_55_event_catalogue.py"
```
