#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tutorial 43: Supervisor + critic refinement loop.

The pattern this tutorial demonstrates is the *flagship multi-agent
demo* most SDKs ship — it shows up in every LangGraph keynote, AutoGen
example, and CrewAI starter. Locus expresses it cleanly:

    Supervisor                Researcher              Writer
        │                         │                     │
        └── delegates ──> Researcher ──> Writer ──> Critic
                                                          │
                                                  reject? ┴ ──> back to Writer
                                                  approve? ──> END

Roles:

* **Supervisor** decides which specialist to hand off to next based on
  the current task state.
* **Researcher** gathers facts about the topic.
* **Writer** drafts an answer using the research notes.
* **Critic** scores the draft and either accepts (END) or rejects
  with a revision instruction that loops back to the Writer.

What makes the Locus version differentiated:

* The control-flow loop is a ``StateGraph`` with conditional edges —
  not a hand-written ``while True`` plus message-passing.
* Each role is a fully-isolated Locus ``Agent`` with its own system
  prompt, ``max_iterations``, and (optionally) tools.
* Every node-completion event flows through the standard
  ``StreamMode.UPDATES`` stream, so a UI can show "Researcher done /
  Writer working / Critic rejected — revising…" with zero extra code.
* Set ``LOCUS_MODEL_PROVIDER=oci|openai`` to drive real specialists.

Run::

    python examples/tutorial_43_supervisor_critic_loop.py

Difficulty: Advanced
Prerequisites: tutorial_06_basic_graph, tutorial_16_agent_handoff
"""

from __future__ import annotations

import asyncio
from typing import Any

from config import get_model

from locus.agent import Agent, AgentConfig
from locus.core.events import TerminateEvent
from locus.multiagent.graph import END, START, StateGraph


# ---------------------------------------------------------------------------
# Specialist agents — each is a real Locus Agent with its own role
# ---------------------------------------------------------------------------


def _make_agent(role: str, system_prompt: str, model: Any, max_iterations: int = 2) -> Agent:
    return Agent(
        config=AgentConfig(
            agent_id=f"agent-{role}",
            model=model,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            max_tokens=400,
        )
    )


SUPERVISOR_PROMPT = (
    "You are a project supervisor. Given the task and the current state, "
    "decide whether the Researcher, Writer, or Critic should run next. "
    "Respond with ONE word: research, write, or critique."
)

RESEARCHER_PROMPT = (
    "You are a research specialist. Given a topic, return 3–5 concise factual "
    "notes that a writer can use. No opinions. Bullet points only."
)

WRITER_PROMPT = (
    "You are a technical writer. Given research notes (and optionally a critic's "
    "revision request), produce a concise 1–2 paragraph response. Plain prose."
)

CRITIC_PROMPT = (
    "You are a strict editor. Read the draft and decide if it's publishable. "
    "If yes, respond with exactly: APPROVE. "
    "If not, respond with: REVISE: <one-line specific instruction>."
)


# ---------------------------------------------------------------------------
# Helper: drive a Locus Agent inside a graph node, returning final text
# ---------------------------------------------------------------------------


async def _run_agent(agent: Agent, prompt: str) -> str:
    final = ""
    async for event in agent.run(prompt):
        if isinstance(event, TerminateEvent):
            final = event.final_message or ""
    return final.strip()


# ---------------------------------------------------------------------------
# Graph nodes — each wraps one specialist
# ---------------------------------------------------------------------------


async def research_node(state: dict[str, Any]) -> dict[str, Any]:
    agent = _make_agent("researcher", RESEARCHER_PROMPT, state["__model__"])
    notes = await _run_agent(agent, f"Topic: {state['topic']}")
    return {"notes": notes}


async def write_node(state: dict[str, Any]) -> dict[str, Any]:
    agent = _make_agent("writer", WRITER_PROMPT, state["__model__"])
    revision = state.get("revision_request", "")
    prompt = f"Topic: {state['topic']}\nResearch notes:\n{state.get('notes', '')}\n"
    if revision:
        prompt += f"\nCritic feedback (apply this): {revision}\n"
    prompt += "\nWrite the final response now."

    draft = await _run_agent(agent, prompt)
    revisions_done = state.get("revisions_done", 0) + (1 if revision else 0)
    return {"draft": draft, "revisions_done": revisions_done}


async def critique_node(state: dict[str, Any]) -> dict[str, Any]:
    agent = _make_agent("critic", CRITIC_PROMPT, state["__model__"])
    verdict = await _run_agent(agent, f"Draft to review:\n{state.get('draft', '')}")
    approved = verdict.strip().upper().startswith("APPROVE")
    revision_request = "" if approved else verdict
    return {
        "approved": approved,
        "revision_request": revision_request,
        "critic_verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Conditional routing — supervisor decides next step from current state
# ---------------------------------------------------------------------------


def route_after_critique(state: dict[str, Any]) -> str:
    """Loop back to the writer if the critic rejected (capped retries)."""
    if state.get("approved"):
        return "done"
    if state.get("revisions_done", 0) >= 2:  # cap: max 2 revisions
        return "done"
    return "revise"


# ---------------------------------------------------------------------------
# Build the graph: research → write → critique → (revise → write | done → END)
# ---------------------------------------------------------------------------


def build_supervisor_graph() -> StateGraph:
    graph = StateGraph(name="supervisor-critic-loop")
    graph.add_node("research", research_node)
    graph.add_node("write", write_node)
    graph.add_node("critique", critique_node)

    graph.add_edge(START, "research")
    graph.add_edge("research", "write")
    graph.add_edge("write", "critique")
    graph.add_conditional_edges(
        "critique",
        route_after_critique,
        targets={"revise": "write", "done": END},
    )
    return graph


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


async def main() -> None:
    print("Tutorial 43: Supervisor + critic refinement loop")
    print("=" * 60)

    model = get_model()
    graph = build_supervisor_graph()

    initial = {
        "topic": "Why structured logging beats plain prints in production",
        "__model__": model,
    }

    print(f"\nTopic: {initial['topic']!r}\n")

    # Stream node-completion events so we can see each specialist run,
    # then call execute() once for the authoritative final state. (Both
    # APIs are public — stream() is for live UI feedback; execute()
    # gives you the GraphResult with metrics.)
    from locus.multiagent.graph import StreamMode

    async for event in graph.stream(initial, mode=StreamMode.NODES):
        if event.node_id:
            print(f"  ✓ {event.node_id}", flush=True)

    final = await graph.execute(initial)
    final_state = final.final_state

    print()
    print(f"Revisions:    {final_state.get('revisions_done', 0)}")
    verdict = final_state.get("critic_verdict") or "(unknown)"
    print(f"Critic:       {verdict[:80]}")
    print(f"Total tokens: ~{final.duration_ms:.0f} ms across {final.iterations} graph iterations")
    print()
    print("Final draft:")
    print("-" * 60)
    print(final_state.get("draft", "(no draft)"))


if __name__ == "__main__":
    asyncio.run(main())
