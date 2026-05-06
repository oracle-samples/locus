#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tutorial 53: agent yield bridge + token usage.

Every Locus ``Agent.run`` is decorated with ``@_bus_bridge`` so the
typed events it yields (``ThinkEvent``, ``ToolStartEvent``,
``ToolCompleteEvent``, ``ReflectEvent``, ``GroundingEvent``,
``ModelChunkEvent``, ``ModelCompleteEvent``, ``InterruptEvent``,
``TerminateEvent``) get republished on the bus as ``agent.*`` events
when a ``run_context`` is open. ``ModelCompleteEvent`` produces an
extra ``agent.tokens.used`` so cost dashboards can subscribe without
parsing the completion payload.

This tutorial covers:

1. How nine yielded ``LocusEvent`` types map to ``agent.*`` bus
   events (one row of the catalogue).
2. Tool-call telemetry with ``span_id`` pairing
   (``agent.tool.started`` and ``agent.tool.completed`` share an id).
3. Token usage as a first-class event — what ``agent.tokens.used``
   carries and how to plug it into a cost meter.

Difficulty: intermediate. Prerequisites: tutorial 02 (tools), 52
(observability basics).

Run with:
    python examples/tutorial_53_agent_yield_bridge.py
"""

from __future__ import annotations

import asyncio

from config import get_model

from locus import Agent, tool
from locus.observability import get_event_bus, run_context


@tool
def add_numbers(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b


@tool
def multiply_numbers(a: int, b: int) -> int:
    """Return the product of two integers."""
    return a * b


# =============================================================================
# Part 1 — the full ``agent.*`` lifecycle for one tool-using run
# =============================================================================


async def part1_full_lifecycle() -> None:
    """Run an Agent that has to plan, call two tools, then conclude.
    Subscribe to the bus and print every ``agent.*`` event with its
    span_id (where applicable) so you can see the lifecycle pairing."""
    print("\n--- Part 1: full agent.* lifecycle ---")

    agent = Agent(
        model=get_model(),
        tools=[add_numbers, multiply_numbers],
        max_iterations=4,
        system_prompt=(
            "You answer with one tool call at a time. After all tool calls, give the final answer."
        ),
    )

    async with run_context() as rid:
        bus = get_event_bus()

        async def consumer() -> None:
            async for ev in bus.subscribe(rid):
                # Highlight span_id for tool pairing.
                span = ev.data.get("span_id", "")
                tag = f" span={span[:8]}" if span else ""
                # Print only ``agent.*`` events to keep noise down.
                if ev.event_type.startswith("agent."):
                    print(f"  {ev.event_type}{tag}")
                if ev.event_type == "agent.terminate":
                    return

        consumer_task = asyncio.create_task(consumer())
        await asyncio.sleep(0)

        result = await asyncio.to_thread(
            agent.run_sync, "Compute (3 + 4) and then (5 * 7), and tell me both."
        )
        print(f"agent reply: {result.message[:160]}")
        await asyncio.wait_for(consumer_task, timeout=20.0)
        await bus.close_stream(rid)


# =============================================================================
# Part 2 — token usage as a cost meter
# =============================================================================


async def part2_token_meter() -> None:
    """A real-world pattern: a global token counter that subscribes to
    every run and sums ``agent.tokens.used`` payloads. Plug this into
    a cost dashboard or budget enforcer."""
    print("\n--- Part 2: token meter ---")

    totals = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}

    async def meter(rid: str) -> None:
        bus = get_event_bus()
        async for ev in bus.subscribe(rid):
            if ev.event_type == "agent.tokens.used":
                totals["prompt"] += ev.data.get("prompt_tokens", 0)
                totals["completion"] += ev.data.get("completion_tokens", 0)
                totals["total"] += ev.data.get("total_tokens", 0)
                totals["calls"] += 1
            if ev.event_type == "agent.terminate":
                return

    agent = Agent(model=get_model(), max_iterations=2)

    async with run_context() as rid:
        meter_task = asyncio.create_task(meter(rid))
        await asyncio.sleep(0)
        await asyncio.to_thread(agent.run_sync, "In one sentence: what is JSON?")
        await asyncio.wait_for(meter_task, timeout=10.0)
        await get_event_bus().close_stream(rid)

    print(
        f"  total LLM calls: {totals['calls']}  "
        f"prompt={totals['prompt']}  completion={totals['completion']}  "
        f"total={totals['total']}"
    )


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    await part1_full_lifecycle()
    await part2_token_meter()


if __name__ == "__main__":
    asyncio.run(main())
