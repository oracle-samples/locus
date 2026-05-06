#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tutorial 55: full event catalogue tour.

Every component in Locus emits typed events under one stable prefix:
``agent.*``, ``multiagent.*``, ``composition.*``, ``router.*``,
``rag.*``, ``memory.*``, ``a2a.*``, ``skills.*``, ``deepagent.*``.
The ``EV_*`` constants in ``locus.observability.emit`` are the
canonical registry — change one place, propagates everywhere.

This tutorial covers:

1. Listing every ``EV_*`` constant and its category prefix.
2. Driving an Orchestrator + Specialist run that hits ``multiagent.*``
   events end-to-end and prints the per-component event types.
3. Running a SequentialPipeline + LoopAgent to surface ``composition.*``.

Difficulty: intermediate. Prerequisites: tutorial 17 (orchestrator),
tutorial 25 (composition), tutorial 52 (observability basics).

Run with:
    python examples/tutorial_55_event_catalogue.py
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict

from config import get_model

from locus import Agent
from locus.agent.composition import LoopAgent, SequentialPipeline
from locus.observability import get_event_bus, run_context


# =============================================================================
# Part 1 — catalogue tour
# =============================================================================


def part1_catalogue_tour() -> None:
    """Print every canonical event_type the SDK exposes, grouped by
    category prefix. Useful when wiring a renderer or a JSON log."""
    print("\n--- Part 1: canonical event_type catalogue ---")

    emit_mod = sys.modules["locus.observability.emit"]
    by_prefix: dict[str, list[str]] = defaultdict(list)
    for name in dir(emit_mod):
        if not name.startswith("EV_"):
            continue
        value = getattr(emit_mod, name)
        if not isinstance(value, str):
            continue
        prefix = value.split(".", 1)[0]
        by_prefix[prefix].append(value)

    for prefix in sorted(by_prefix):
        print(f"  {prefix}.*  ({len(by_prefix[prefix])} events)")
        for ev in sorted(by_prefix[prefix]):
            print(f"    - {ev}")


# =============================================================================
# Part 2 — composition.* in action
# =============================================================================


async def part2_composition() -> None:
    """SequentialPipeline + LoopAgent both emit ``composition.*``
    events at every stage / iteration boundary. Subscribe to one run
    and observe."""
    print("\n--- Part 2: composition.* events ---")

    a = Agent(model=get_model(), max_iterations=1)
    b = Agent(model=get_model(), max_iterations=1)

    pipeline = SequentialPipeline(agents=[a, b])

    async with run_context() as rid:
        bus = get_event_bus()

        async def consumer() -> None:
            seen: list[str] = []
            async for ev in bus.subscribe(rid):
                if ev.event_type.startswith("composition."):
                    seen.append(ev.event_type)
                if ev.event_type == "composition.fanout.completed":
                    break
                if ev.event_type == "composition.stage.completed" and ev.data.get("stage") == 1:
                    print("composition events seen so far:", seen)
                    return

        consumer_task = asyncio.create_task(consumer())
        await asyncio.sleep(0)

        await pipeline.run("Tell me a one-line haiku about JSON.")
        await bus.close_stream(rid)
        await consumer_task


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    part1_catalogue_tour()
    await part2_composition()


if __name__ == "__main__":
    asyncio.run(main())
