# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Lightweight emit helpers — single line per instrumentation site.

The contract for every emission site in the SDK:

* **Sync call sites** use :func:`emit_sync`. It schedules a publish on
  the running event loop *if there is one*; otherwise drops. Never
  blocks, never raises.
* **Async call sites** use :func:`emit`. Awaits the bus publish so
  events appear in deterministic order on the consumer side.

Both check :func:`current_run_id` first. When the contextvar is unset
they return immediately — no bus singleton instantiation, no event
construction, no allocation. SDK users who don't use telemetry pay
exactly one ``ContextVar.get()`` per emission site.

Module-level event-name constants pin the canonical wire types so
changes are greppable and consumers (the workbench, third-party
monitors) can rely on them.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from locus.observability.context import current_run_id


logger = logging.getLogger(__name__)

# ``loop.create_task`` returns a Task that the GC may collect before it
# runs unless someone holds a strong reference. We pin every fire-and-
# forget telemetry task on this set and remove it on completion, which
# is the recipe Python's docs recommend for long-lived emit-only tasks.
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


# Canonical event-type names — change here, propagates to every
# instrumentation site. Listed verbatim in the workbench's renderer
# so a typo here breaks one place, not many.

# --- Multi-agent ---
EV_ORCHESTRATOR_ROUTING = "multiagent.orchestrator.routing"
EV_ORCHESTRATOR_DECISION = "multiagent.orchestrator.decision"
EV_ORCHESTRATOR_SPECIALISTS_INVOKED = "multiagent.orchestrator.specialists_invoked"
EV_ORCHESTRATOR_SUMMARY = "multiagent.orchestrator.summary"
EV_SPECIALIST_STARTED = "multiagent.specialist.started"
EV_SPECIALIST_COMPLETED = "multiagent.specialist.completed"
EV_HANDOFF_INITIATED = "multiagent.handoff.initiated"
EV_HANDOFF_COMPLETED = "multiagent.handoff.completed"

# --- Composition pipelines ---
EV_PIPELINE_STAGE_STARTED = "composition.stage.started"
EV_PIPELINE_STAGE_COMPLETED = "composition.stage.completed"
EV_PIPELINE_FANOUT_STARTED = "composition.fanout.started"
EV_PIPELINE_FANOUT_COMPLETED = "composition.fanout.completed"
EV_LOOP_ITERATION_STARTED = "composition.loop.iteration.started"
EV_LOOP_ITERATION_COMPLETED = "composition.loop.iteration.completed"
EV_LOOP_TERMINATED = "composition.loop.terminated"

# --- Skills ---
EV_SKILL_ACTIVATED = "skills.activated"

# --- Memory / checkpointing ---
EV_CHECKPOINT_SAVED = "memory.checkpoint.saved"
EV_CHECKPOINT_LOADED = "memory.checkpoint.loaded"


async def emit(event_type: str, /, **data: Any) -> None:
    """Publish a :class:`StreamEvent` if a run_id is in the current
    context. No-op otherwise.

    Use from any ``async def`` instrumentation site. Awaits the bus
    publish so events appear in the order they were emitted on the
    consumer side.

    The bus singleton is imported lazily here so simply importing
    this module doesn't construct it.
    """
    rid = current_run_id()
    if rid is None:
        return
    # Lazy import — keeps the bus singleton from being constructed
    # until the first real emission.
    from locus.observability.event_bus import StreamEvent, get_event_bus  # noqa: PLC0415

    try:
        await get_event_bus().publish(
            StreamEvent(run_id=rid, event_type=event_type, data=data),
        )
    except Exception:  # noqa: BLE001 — telemetry must never break the SDK
        logger.debug("emit failed for %s", event_type, exc_info=True)


def emit_sync(event_type: str, /, **data: Any) -> None:
    """Sync-call equivalent of :func:`emit`.

    Schedules a publish on the running event loop. If there isn't one
    (sync code outside any asyncio context), the event is dropped — we
    don't bring up a loop just to publish telemetry. Use :func:`emit`
    from coroutines whenever possible.
    """
    rid = current_run_id()
    if rid is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Sync code with no running loop — dropping is the right call.
        # Spinning up a fresh loop here would fight the rest of the
        # process for control of asyncio singletons.
        return
    from locus.observability.event_bus import StreamEvent, get_event_bus  # noqa: PLC0415

    bus = get_event_bus()
    coro = bus.publish(StreamEvent(run_id=rid, event_type=event_type, data=data))
    # Fire-and-forget. We deliberately don't await the task — that
    # would defeat the "telemetry never blocks" contract. We anchor
    # the task on the event loop's pending set so the GC can't reap
    # the coroutine mid-flight.
    task = loop.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
