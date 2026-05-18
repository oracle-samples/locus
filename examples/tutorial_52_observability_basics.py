#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tutorial 52: observability basics — opt-in SSE telemetry.

Locus ships an in-process pub/sub ``EventBus`` that publishes typed
``StreamEvent``s for every meaningful step of execution: agent
thinking, tool calls, model completions, token usage, multi-agent
fan-outs, checkpoints — all under one canonical event_type per
component.

Telemetry is **opt-in**. SDK users who never enter a ``run_context``
pay one ``ContextVar.get()`` per emission site — no bus, no events,
no allocations.

This tutorial covers:

1. Running an Agent with no telemetry (the SDK-default path).
2. Wrapping the same call in ``run_context()`` and subscribing to
   the bus to see the full inner cognition.
3. The shape of the canonical events: ``agent.think``,
   ``agent.tool.started/completed``, ``agent.tokens.used``,
   ``agent.terminate``.
4. Reading the per-run history buffer after the fact (replay
   semantics for late subscribers).

Difficulty: beginner. Prerequisites: tutorial 01 (basic Agent).

Run with:
    python examples/tutorial_52_observability_basics.py
"""

from __future__ import annotations

import asyncio

from config import get_model

from locus.agent import Agent
from locus.observability import get_event_bus, run_context


# =============================================================================
# Part 1 — running without telemetry (the no-op path)
# =============================================================================


async def part1_no_telemetry() -> None:
    """No ``run_context``: every emit short-circuits before allocating
    anything. The bus singleton is never instantiated."""
    print("\n--- Part 1: no run_context — bus stays uninstantiated ---")

    agent = Agent(model=get_model(), max_iterations=2)
    result = agent.run_sync("In one sentence, what is locus?")
    print("agent reply:", result.message[:120])

    # Probe the bus internals to prove the singleton was never built.
    from locus.observability import event_bus as _bus_mod

    assert _bus_mod._event_bus is None, (
        "running an Agent without run_context must not construct the bus"
    )
    print("bus singleton is None — zero allocations spent on telemetry")


# =============================================================================
# Part 2 — opt in via run_context, subscribe, see everything
# =============================================================================


async def part2_subscribe() -> None:
    """Same Agent.run, this time inside a ``run_context``. We subscribe
    in parallel and print every event_type that lands."""
    print("\n--- Part 2: run_context active — subscribe to the bus ---")

    agent = Agent(model=get_model(), max_iterations=2)
    seen: list[str] = []

    async with run_context() as rid:
        bus = get_event_bus()

        async def consumer() -> None:
            async for ev in bus.subscribe(rid):
                seen.append(ev.event_type)
                if ev.event_type == "agent.terminate":
                    return

        consumer_task = asyncio.create_task(consumer())
        await asyncio.sleep(0)  # let the subscriber register

        # Drive the agent on the same loop. Because the contextvar
        # was set by run_context(), every yielded LocusEvent is bridged
        # to the bus by the @_bus_bridge decorator on Agent.run.
        result = await asyncio.to_thread(agent.run_sync, "Reply with the single word: hello")
        print("agent reply:", result.message[:120])

        await asyncio.wait_for(consumer_task, timeout=10.0)
        # Closing the stream ends any other subscribers cleanly.
        await bus.close_stream(rid)

    print(f"events seen ({len(seen)}):")
    for e in seen:
        print(f"  - {e}")


# =============================================================================
# Part 3 — late subscribers + history replay
# =============================================================================


async def part3_history_replay() -> None:
    """Subscribe AFTER the run finished. The bus's per-run history
    deque (cap 500 events × 200 retained runs) replays everything to
    the late subscriber, then closes cleanly."""
    print("\n--- Part 3: late subscriber — history replay ---")

    agent = Agent(model=get_model(), max_iterations=2)

    async with run_context() as rid:
        bus = get_event_bus()
        # Run first; subscribe second.
        await asyncio.to_thread(agent.run_sync, "Reply: ok")
        await bus.close_stream(rid)

        replayed: list[str] = []
        async for ev in bus.subscribe(rid):
            replayed.append(ev.event_type)

    print(f"replayed {len(replayed)} events from history (after the run finished)")
    for e in replayed[:10]:
        print(f"  - {e}")
    if len(replayed) > 10:
        print(f"  ... +{len(replayed) - 10} more")


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    await part1_no_telemetry()
    await part2_subscribe()
    await part3_history_replay()


if __name__ == "__main__":
    asyncio.run(main())
