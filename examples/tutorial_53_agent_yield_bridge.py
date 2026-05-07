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

        result = None
        async for event in agent.run("Compute (3 + 4) and then (5 * 7), and tell me both."):
            from locus.core.events import TerminateEvent

            if isinstance(event, TerminateEvent):
                result = event
        print(f"agent reply: {result.final_message[:160] if result else '(no reply)'}")
        await asyncio.wait_for(consumer_task, timeout=20.0)
        await bus.close_stream(rid)


# =============================================================================
# Part 2 — token usage as a cost meter
# =============================================================================


async def part2_token_meter() -> None:
    """Token usage — the authoritative source is ``result.metrics``.

    Every ``AgentResult`` carries a ``metrics`` object with the
    accumulated token counts for the entire run, regardless of how
    many iterations or tool calls were made.  This is the recommended
    pattern for cost dashboards and budget enforcers.

    ``agent.tokens.used`` SSE events (fired when ``ModelCompleteEvent``
    is yielded) are supported by the bridge for custom streaming
    consumers — use ``result.metrics`` when you only need the final
    total.
    """
    print("\n--- Part 2: token meter via result.metrics ---")

    running_prompt = running_completion = running_total = 0

    # Simulate a multi-run session and accumulate token totals.
    prompts = [
        "In one sentence: what is JSON?",
        "In one sentence: what is a REST API?",
    ]

    for prompt in prompts:
        agent = Agent(model=get_model(), max_iterations=2)
        result = agent.run_sync(prompt)
        m = result.metrics
        running_prompt += m.prompt_tokens
        running_completion += m.completion_tokens
        running_total += m.total_tokens
        print(
            f"  run: prompt={m.prompt_tokens:4d}  "
            f"completion={m.completion_tokens:3d}  "
            f"total={m.total_tokens:4d}  | '{prompt[:40]}'"
        )

    print(
        f"  ─── session total: prompt={running_prompt}  "
        f"completion={running_completion}  total={running_total}"
    )


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    await part1_full_lifecycle()
    await part2_token_meter()


if __name__ == "__main__":
    asyncio.run(main())
