#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tutorial 45: Multi-agent workflows with human-in-the-loop.

Tutorial 09 covered HITL with a single agent. Real production agentic
systems rarely look like that — most of them have:

    1. A triage agent that classifies incoming work.
    2. Specialist agents that do the work.
    3. A *human approval gate* before any irreversible action.
    4. An *escalation path* when the agents can't decide.

This tutorial walks three patterns that combine multi-agent workflows
with human input. All three use the ``interrupt()`` primitive so the
graph **pauses, returns control to the caller, then resumes** when the
human responds — no busy-waiting, no callback hell.

Patterns covered:

* **Pattern A — Approval gate**: a Triage agent classifies a refund
  request, a Specialist drafts the response, a human approves before
  it ships.
* **Pattern B — Human-as-tool**: when the Triage agent isn't confident,
  it asks the human a structured question rather than guessing. The
  human's answer becomes part of state for downstream specialists.
* **Pattern C — Multi-step interrupt + checkpoint**: the graph saves
  state across an interrupt boundary so a human can come back hours
  later (different process / different caller) and the workflow
  picks up where it left off.

What's differentiated about Locus here:

* ``interrupt()`` is a function-level primitive — no need to wire a
  separate "wait-for-human" node type. Any node can pause.
* The graph executor returns an ``InterruptState`` that carries the
  full workflow state. Resume by calling ``graph.execute(Command(
  resume=...))``. State doesn't have to live in a global anywhere.
* Combine with a ``checkpointer`` and the workflow can pause for
  hours/days while preserving every specialist's context.
* Set ``LOCUS_MODEL_PROVIDER=oci|openai`` to drive real specialists.

Run::

    python examples/tutorial_45_multiagent_human_in_loop.py

Difficulty: Advanced
Prerequisites: tutorial_09_human_in_the_loop, tutorial_43 (this series)
"""

from __future__ import annotations

import asyncio
from typing import Any

from config import get_model

from locus.agent import Agent, AgentConfig
from locus.core import Command, interrupt
from locus.core.events import TerminateEvent
from locus.multiagent.graph import END, START, StateGraph


# ---------------------------------------------------------------------------
# Specialists
# ---------------------------------------------------------------------------


def _make_agent(role: str, system_prompt: str, model: Any) -> Agent:
    return Agent(
        config=AgentConfig(
            agent_id=f"agent-{role}",
            model=model,
            system_prompt=system_prompt,
            max_iterations=2,
            max_tokens=300,
        )
    )


TRIAGE_PROMPT = (
    "You are a customer-support triage agent. Read the request and "
    "respond with EXACTLY ONE of: refund, billing, technical, escalate. "
    "Use 'escalate' only when the request is ambiguous or requires "
    "manager judgment."
)
REFUND_PROMPT = (
    "You are a refund specialist. Draft a polite, concise reply confirming "
    "the refund will be processed. Two sentences max."
)


async def _run_agent(agent: Agent, prompt: str) -> str:
    final = ""
    async for event in agent.run(prompt):
        if isinstance(event, TerminateEvent):
            final = event.final_message or ""
    return final.strip()


# ---------------------------------------------------------------------------
# Pattern A — Approval gate
# ---------------------------------------------------------------------------


async def triage_node(state: dict[str, Any]) -> dict[str, Any]:
    agent = _make_agent("triage", TRIAGE_PROMPT, state["__model__"])
    category = await _run_agent(agent, f"Customer request: {state['request']!r}")
    return {"category": category.strip().lower().split()[0] if category else "escalate"}


async def draft_refund_node(state: dict[str, Any]) -> dict[str, Any]:
    agent = _make_agent("refund", REFUND_PROMPT, state["__model__"])
    draft = await _run_agent(
        agent, f"Customer request: {state['request']!r}\nDraft the refund response."
    )
    return {"draft": draft}


async def human_approval_node(state: dict[str, Any]) -> dict[str, Any]:
    """Pause the graph until a human approves or rejects the draft.

    ``interrupt()`` raises ``InterruptException`` here, the graph
    catches it, snapshots state, and returns an ``InterruptState`` to
    the caller. When the caller calls ``graph.execute(Command(resume=
    'yes'|'no'))`` we land back in this node, and ``interrupt()``
    returns the resume value.
    """
    response = interrupt(
        {
            "type": "approval",
            "question": "Approve this refund response?",
            "draft": state.get("draft", ""),
            "options": ["yes", "no"],
        }
    )
    return {"approved": response == "yes", "human_response": response}


async def send_or_cancel_node(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("approved"):
        return {"result": "✓ Sent to customer", "outcome": "sent"}
    return {"result": "✗ Cancelled by human reviewer", "outcome": "cancelled"}


def build_approval_graph() -> StateGraph:
    g = StateGraph(name="hitl-approval-gate")
    g.add_node("triage", triage_node)
    g.add_node("draft", draft_refund_node)
    g.add_node("approve", human_approval_node)
    g.add_node("send", send_or_cancel_node)
    g.add_edge(START, "triage")
    g.add_edge("triage", "draft")
    g.add_edge("draft", "approve")
    g.add_edge("approve", "send")
    g.add_edge("send", END)
    return g


async def demo_pattern_a(model: Any) -> None:
    print("\n=== Pattern A: Approval gate ===\n")
    graph = build_approval_graph()
    initial = {"request": "I want a refund for order #42 — it never shipped.", "__model__": model}

    # First execute — runs triage, draft, then pauses at approve.
    result = await graph.execute(initial)
    if not result.interrupt:
        print(f"  ✗ unexpected: graph completed without interrupt: {result.final_state}")
        return
    payload = result.interrupt.interrupt.payload
    print(f"  ⏸  Paused at: {result.interrupt.node_id}")
    print(f"     Question:  {payload.get('question')}")
    print(f"     Draft:     {payload.get('draft')}")

    # Simulate the human approving.
    print("  ▶  Human responds: 'yes'")
    final = await graph.execute(
        Command(resume="yes", update=result.final_state),
    )
    print(f"  ✓ Final outcome: {final.final_state.get('result')}")


# ---------------------------------------------------------------------------
# Pattern B — Human-as-tool (escalation when triage isn't confident)
# ---------------------------------------------------------------------------


async def smart_triage_node(state: dict[str, Any]) -> dict[str, Any]:
    """Triage with an *escalate* fallback that asks the human directly."""
    valid = {"refund", "billing", "technical"}
    agent = _make_agent("triage", TRIAGE_PROMPT, state["__model__"])
    raw = await _run_agent(agent, f"Customer request: {state['request']!r}")
    first = (raw.lower().split() or ["escalate"])[0]
    # Treat anything that isn't one of the explicit categories — including
    # the mock model's filler text — as 'escalate'. That's what we want
    # in production too: never run a specialist with a bogus category.
    category = first if first in valid else "escalate"

    if category == "escalate":
        # Human-as-tool: the agent admits it doesn't know; ask the person.
        category = interrupt(
            {
                "type": "escalation",
                "question": (
                    f"Triage agent is not confident. Pick a category for: {state['request']!r}"
                ),
                "options": ["refund", "billing", "technical", "drop"],
            }
        )
    return {"category": category}


async def route_node(state: dict[str, Any]) -> dict[str, Any]:
    return {"final_category": state.get("category", "drop")}


def build_escalation_graph() -> StateGraph:
    g = StateGraph(name="hitl-escalation")
    g.add_node("triage", smart_triage_node)
    g.add_node("route", route_node)
    g.add_edge(START, "triage")
    g.add_edge("triage", "route")
    g.add_edge("route", END)
    return g


async def demo_pattern_b(model: Any) -> None:
    print("\n=== Pattern B: Human-as-tool (escalation) ===\n")
    graph = build_escalation_graph()
    initial = {
        "request": "weird flickering on the dashboard but only on Tuesdays?",
        "__model__": model,
    }

    result = await graph.execute(initial)
    if result.interrupt:
        payload = result.interrupt.interrupt.payload
        print(f"  ⏸  Triage escalated. Asking human:")
        print(f"     {payload.get('question')}")
        print("  ▶  Human responds: 'technical'")
        final = await graph.execute(Command(resume="technical", update=result.final_state))
        print(f"  ✓ Routed to: {final.final_state.get('final_category')}")
    else:
        # Triage was confident — no human needed.
        print(f"  ✓ Triage confident ({result.final_state.get('category')}) — no escalation")


# ---------------------------------------------------------------------------
# Pattern C — Long-pause workflow with checkpointing
# ---------------------------------------------------------------------------


async def demo_pattern_c(model: Any) -> None:
    """Long-pause workflow: save the workflow state, resume later.

    The simple in-memory case is just "hold the ``InterruptState`` from
    the first ``execute`` call somewhere durable, then call ``execute``
    again with ``Command(resume=...)`` when the human responds." The
    ``InterruptState`` includes a ``state_snapshot`` that has every
    upstream node's output, so the resumed call has full context.

    For multi-process / multi-day workflows you'd swap the in-memory
    snapshot for a checkpointer (Redis / Postgres / Oracle / OCI Bucket).
    The graph's built-in checkpointer hook expects an AgentState — for
    pure-graph workflows like this one, persisting the
    ``InterruptState`` to your own store is the simpler path.
    """
    print("\n=== Pattern C: Long-pause workflow (snapshot + resume) ===\n")

    graph = build_approval_graph()
    initial = {"request": "Refund for order #42 — never arrived.", "__model__": model}

    paused = await graph.execute(initial)
    if not paused.interrupt:
        print("  ✗ unexpected: workflow completed without pause")
        return
    snapshot_state = paused.final_state
    print(f"  ⏸  Paused at {paused.interrupt.node_id}")
    print(
        f"     Snapshot has {len(snapshot_state)} state keys — persist these "
        "to Redis / Postgres / a queue / etc."
    )

    # ... time passes; reviewer comes back ...
    print("  ▶  Hours later: load snapshot, resume with the human's answer")
    # Re-attach the model object — the snapshot has the JSON-able parts
    # only. Real production code would rebuild the model from config too.
    resumed = await graph.execute(
        Command(resume="yes", update={**snapshot_state, "__model__": model}),
    )
    print(f"  ✓ Resumed and finished: {resumed.final_state.get('result')}")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


async def main() -> None:
    print("Tutorial 45: Multi-agent + human-in-the-loop")
    print("=" * 60)

    model = get_model()
    await demo_pattern_a(model)
    await demo_pattern_b(model)
    await demo_pattern_c(model)


if __name__ == "__main__":
    asyncio.run(main())
