#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tutorial 54: EventBus consumer patterns.

The bus has three subscribe shapes:

* ``bus.subscribe(run_id)`` — events for one dispatch (with history
  replay on connect, sentinel on close).
* ``bus.subscribe_global()`` — every event from every run, no history
  replay (useful for a monitoring dashboard).
* ``bus._history.get(run_id, ())`` — direct read of the per-run
  history deque (test helper; cap 500 events × 200 runs LRU).

This tutorial covers:

1. Per-run subscriber + history replay.
2. Global subscriber across two concurrent dispatches.
3. Slow consumer / drop accounting (the bus drops an event for one
   slow subscriber instead of blocking the publisher).

Difficulty: intermediate. Prerequisites: tutorial 52 (basics).

Run with:
    python examples/tutorial_54_eventbus_subscribers.py
"""

from __future__ import annotations

import asyncio

from config import get_model

from locus.agent import Agent
from locus.observability import get_event_bus, run_context


# =============================================================================
# Part 1 — per-run + global subscribers running concurrently
# =============================================================================


async def part1_global_vs_per_run() -> None:
    """Two dispatches on different run_ids; one global subscriber
    sees both, one per-run subscriber sees only its own."""
    print("\n--- Part 1: global vs per-run subscribers ---")

    bus = get_event_bus()
    global_kinds: list[str] = []
    run_a_kinds: list[str] = []

    async def global_sub() -> None:
        async for ev in bus.subscribe_global():
            global_kinds.append(f"{ev.run_id[:6]}/{ev.event_type}")
            if ev.event_type == "agent.terminate" and len(global_kinds) >= 4:
                return

    async def run_a_sub(rid: str) -> None:
        async for ev in bus.subscribe(rid):
            run_a_kinds.append(ev.event_type)
            if ev.event_type == "agent.terminate":
                return

    async def dispatch(rid: str, prompt: str) -> None:
        async with run_context(rid):
            agent = Agent(model=get_model(), max_iterations=2)
            await asyncio.to_thread(agent.run_sync, prompt)
            await bus.close_stream(rid)

    g_task = asyncio.create_task(global_sub())
    a_task = asyncio.create_task(run_a_sub("run-A"))
    await asyncio.sleep(0)

    await asyncio.gather(
        dispatch("run-A", "Reply: hi from A"),
        dispatch("run-B", "Reply: hi from B"),
    )
    # Wait for both subscribers to terminate via their sentinels.
    await asyncio.wait_for(asyncio.gather(g_task, a_task), timeout=15.0)

    print(f"global saw {len(global_kinds)} events across both runs:")
    for k in global_kinds[:6]:
        print(f"  - {k}")
    if len(global_kinds) > 6:
        print(f"  ... +{len(global_kinds) - 6} more")

    print(f"run-A subscriber saw {len(run_a_kinds)} events (only its own run):")
    for k in run_a_kinds[:6]:
        print(f"  - {k}")


# =============================================================================
# Part 2 — bus stats endpoint (dropped events, retained runs)
# =============================================================================


async def part2_stats() -> None:
    """The bus exposes ``bus.stats()`` for diagnostics: queue sizes,
    history depth, drop counter, retained-run count. Hook it up to
    your monitoring dashboard."""
    print("\n--- Part 2: bus.stats() ---")

    bus = get_event_bus()
    snapshot = bus.stats()
    for k, v in snapshot.items():
        print(f"  {k}: {v}")


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    await part1_global_vs_per_run()
    await part2_stats()


if __name__ == "__main__":
    asyncio.run(main())
