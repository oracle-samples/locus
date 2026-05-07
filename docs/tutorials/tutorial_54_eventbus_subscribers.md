# Tutorial 54: EventBus subscriber patterns

The bus has three subscribe shapes, each suited to a different consumer:

* ``bus.subscribe(run_id)`` — events for one dispatch, with history replay
  on connect then live events, terminated by a sentinel on stream close.
* ``bus.subscribe_global()`` — every event from every run, no history
  replay. Use for a monitoring dashboard that spans many concurrent runs.
* ``bus._history.get(run_id, ())`` — direct read of the per-run history
  deque (test helper; capped at 500 events × 200 runs LRU).

Capacity model::

    publisher
       │
       ├──► subscriber queue A  (max_queue_size=1024)
       │       └─ slow? ─► drop event, increment bus._dropped_events
       │
       ├──► subscriber queue B
       │
       └──► global subscriber queues (capped count)

This tutorial covers:

1. Per-run subscriber with history replay.
2. Global subscriber watching two concurrent dispatches on different
   ``run_id``s.
3. Slow consumer and drop accounting — the bus drops an event for one
   slow subscriber after a 1 s timeout instead of blocking the publisher;
   ``bus.stats()`` surfaces the dropped count.

Why this is differentiated:

* Slow subscribers never stall fast ones — the timeout-and-drop model
  means a lagging log writer can't back-pressure a real-time UI.
* History replay makes late-joining subscribers (e.g. a browser tab that
  opens after a run starts) first-class — they see the full context from
  the beginning without re-running the agent.
* ``bus.stats()`` gives a live read on queue saturation, retained runs,
  and total dropped events — production-ready diagnostics in one call.

Run::

    python examples/tutorial_54_eventbus_subscribers.py

Difficulty: Intermediate
Prerequisites: tutorial_52_observability_basics (observability basics)

## Source

```python
--8<-- "examples/tutorial_54_eventbus_subscribers.py"
```
