#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tutorial 41: DeepAgent — research-shaped agent factory.

``create_deepagent`` bundles the standard deep-research configuration into
one call: reflexion + grounding on by default, typed termination algebra,
optional filesystem scratchspace, optional todo tracking, and optional
subagent spawning — all as a plain ``locus.Agent``.

This tutorial covers:

1. A basic ``create_deepagent`` with a typed submit tool: the agent loops
   with tools, self-corrects via reflexion, grounds claims against its own
   tool results, then submits a structured ``ResearchResult``.
2. Filesystem-as-memory: the agent writes scratchpad notes mid-run and
   reads them back — useful for multi-step research that exceeds context.
3. Todo tracking: attaching ``write_todos`` / ``read_todos`` so the agent
   maintains a structured task list across reasoning steps.
4. Subagent dispatch: spawning a one-shot ``task()`` subagent mid-run
   for deeper sub-investigation without bloating the parent's context.
5. Observability: ``deepagent.*`` events surfaced on the SSE bus
   (subagent spawned/completed, fs.read/write, todo.added/completed).

Difficulty: intermediate. Prerequisites: tutorial_01_basic_agent (Agent),
tutorial_37_termination (typed termination).

Run with:
    python examples/tutorial_41_deepagent.py
"""

from __future__ import annotations

import asyncio

from config import get_model
from pydantic import BaseModel, Field

from locus import tool
from locus.deepagent import (
    SubAgentDef,
    TodoState,
    create_deepagent,
    make_todo_tools,
)
from locus.observability import get_event_bus, run_context


# =============================================================================
# Shared domain: a tiny "module catalogue" the agent can query
# =============================================================================

_MODULE_CATALOGUE = {
    "locus.router": {
        "description": "Meta-orchestration layer — GoalFrame extraction, protocol registry, policy gate, cognitive compiler.",
        "public_api": [
            "Router",
            "GoalFrame",
            "TaskType",
            "ProtocolRegistry",
            "PolicyGate",
            "CognitiveCompiler",
        ],
        "since": "0.2.0",
    },
    "locus.observability": {
        "description": "In-process SSE pub/sub bus — EventBus, run_context, canonical EV_* constants.",
        "public_api": [
            "EventBus",
            "EventBusHook",
            "run_context",
            "get_event_bus",
            "emit",
            "emit_sync",
        ],
        "since": "0.2.0",
    },
    "locus.deepagent": {
        "description": "Research-shaped agent factory: create_deepagent, filesystem tools, todos, subagents.",
        "public_api": [
            "create_deepagent",
            "SubAgentDef",
            "TodoState",
            "make_filesystem_tools",
            "make_todo_tools",
        ],
        "since": "0.2.0",
    },
}


@tool
def list_modules() -> list[str]:
    """List all modules available in the locus catalogue."""
    return list(_MODULE_CATALOGUE.keys())


@tool
def inspect_module(name: str) -> dict:
    """Return description, public API, and version for a module.

    Args:
        name: Module dotted name, e.g. ``locus.router``.

    Returns:
        Dict with ``description``, ``public_api``, and ``since``.
    """
    if name not in _MODULE_CATALOGUE:
        return {"error": f"module '{name}' not found"}
    return _MODULE_CATALOGUE[name]


@tool
def count_public_symbols(name: str) -> int:
    """Return the number of public symbols exported by a module.

    Args:
        name: Module dotted name.
    """
    entry = _MODULE_CATALOGUE.get(name)
    if not entry:
        return 0
    return len(entry["public_api"])


# =============================================================================
# Typed output
# =============================================================================


class ModuleReport(BaseModel):
    module: str = Field(description="Dotted module name researched.")
    summary: str = Field(description="2-3 sentence summary of what the module does.")
    public_symbols: list[str] = Field(description="All public symbols in the module.")
    available_since: str = Field(description="Version the module was introduced.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the report (0–1).")


@tool
def submit_research(report: ModuleReport) -> str:
    """Submit the completed research report. Call when confidence ≥ 0.85.

    Args:
        report: The completed ``ModuleReport``.
    """
    return f"submitted: {report.module} ({report.confidence:.0%} confidence)"


# =============================================================================
# Part 1 — basic create_deepagent
# =============================================================================


async def part1_basic() -> None:
    """Minimal usage: reflexion + grounding on, typed termination, no extras."""
    print("\n--- Part 1: basic create_deepagent ---")

    agent = create_deepagent(
        model=get_model(),
        tools=[list_modules, inspect_module, count_public_symbols, submit_research],
        system_prompt=(
            "You are a locus module researcher. "
            "Use list_modules, inspect_module, and count_public_symbols to gather facts. "
            "Submit a complete ModuleReport via submit_research once you reach ≥ 0.85 confidence."
        ),
        output_schema=ModuleReport,
        submit_tool="submit_research",
        min_confidence=0.85,
        max_iterations=12,
    )

    result = agent.run_sync("Research the locus.observability module.")
    print("protocol terminated:", result.stop_reason)
    if result.parsed:
        rpt: ModuleReport = result.parsed  # type: ignore[assignment]
        print(f"module:    {rpt.module}")
        print(f"symbols:   {', '.join(rpt.public_symbols[:4])} …")
        print(f"confidence:{rpt.confidence:.0%}")


# =============================================================================
# Part 2 — filesystem scratchspace + todos
# =============================================================================


async def part2_filesystem_and_todos() -> None:
    """Enable filesystem tools so the agent writes scratchpad notes mid-run,
    and todo tools so it tracks sub-tasks in a structured list."""
    print("\n--- Part 2: filesystem scratchspace + todos ---")

    todo_state = TodoState()

    agent = create_deepagent(
        model=get_model(),
        tools=[list_modules, inspect_module, count_public_symbols, submit_research],
        system_prompt=(
            "You are a locus module researcher. "
            "Use write_file to take scratchpad notes as you gather facts. "
            "Use write_todos to track which modules you've checked. "
            "Submit when you have a complete report with ≥ 0.85 confidence."
        ),
        output_schema=ModuleReport,
        submit_tool="submit_research",
        min_confidence=0.85,
        max_iterations=16,
        enable_filesystem=True,
        enable_todos=True,
        todo_state=todo_state,
    )

    result = agent.run_sync("Research all three modules in the catalogue.")
    print("terminated:", result.stop_reason)
    print("todos after run:")
    for todo in todo_state.snapshot():
        print(f"  [{todo.status}] {todo.content[:60]}")


# =============================================================================
# Part 3 — subagent dispatch
# =============================================================================


async def part3_subagents() -> None:
    """A parent agent dispatches a one-shot subagent for deep symbol analysis
    without bloating the parent's context window."""
    print("\n--- Part 3: subagent dispatch ---")

    # The subagent only has the inspect tool — focused, cheap.
    symbol_analyst = SubAgentDef(
        name="symbol_analyst",
        description="Deep-dives on a single module's public API.",
        system_prompt="Inspect the given module and return a plain list of its public symbols.",
        tools=[inspect_module],
        max_iterations=4,
    )

    agent = create_deepagent(
        model=get_model(),
        tools=[list_modules, submit_research],
        system_prompt=(
            "Use list_modules to discover modules, then delegate symbol analysis "
            "to the symbol_analyst subagent via the task() tool. "
            "Submit a ModuleReport for locus.router once you have the symbol list."
        ),
        output_schema=ModuleReport,
        submit_tool="submit_research",
        min_confidence=0.8,
        max_iterations=12,
        subagents=[symbol_analyst],
    )

    result = agent.run_sync("Research locus.router using the symbol_analyst subagent.")
    print("terminated:", result.stop_reason)
    if result.parsed:
        rpt: ModuleReport = result.parsed  # type: ignore[assignment]
        print(f"symbols from subagent: {rpt.public_symbols}")


# =============================================================================
# Part 4 — deepagent.* SSE events
# =============================================================================


async def part4_observability() -> None:
    """Observe deepagent.* events on the bus: subagent.spawned/completed,
    fs.read/write, todo.added/completed."""
    print("\n--- Part 4: deepagent.* SSE events ---")

    todo_state = TodoState()
    symbol_analyst = SubAgentDef(
        name="symbol_analyst",
        description="Inspect one module.",
        system_prompt="Inspect the given module and list its public symbols.",
        tools=[inspect_module],
        max_iterations=4,
    )

    agent = create_deepagent(
        model=get_model(),
        tools=[list_modules, submit_research],
        system_prompt=(
            "Use list_modules, delegate symbol analysis via task(), "
            "write scratchpad notes, track progress with todos. "
            "Submit a report for locus.deepagent."
        ),
        output_schema=ModuleReport,
        submit_tool="submit_research",
        min_confidence=0.8,
        max_iterations=14,
        enable_filesystem=True,
        enable_todos=True,
        todo_state=todo_state,
        subagents=[symbol_analyst],
    )

    deepagent_events: list[str] = []

    async def _collect(rid: str) -> None:
        async for ev in get_event_bus().subscribe(rid):
            if ev.event_type.startswith("deepagent."):
                deepagent_events.append(ev.event_type)

    async with run_context() as rid:
        collector = asyncio.create_task(_collect(rid))
        result = agent.run_sync("Research locus.deepagent module.")
        await asyncio.sleep(0.1)
        collector.cancel()

    print("deepagent.* events seen:")
    for ev_type in sorted(set(deepagent_events)):
        count = deepagent_events.count(ev_type)
        print(f"  {ev_type} × {count}")

    print("terminated:", result.stop_reason)


# =============================================================================
# Main
# =============================================================================


async def main() -> None:
    await part1_basic()
    await part2_filesystem_and_todos()
    await part3_subagents()
    await part4_observability()


if __name__ == "__main__":
    asyncio.run(main())
