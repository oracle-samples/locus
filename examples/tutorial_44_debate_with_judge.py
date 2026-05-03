#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tutorial 44: Adversarial debate with structured-output judge.

Two opposing agents argue a question. After ``N`` rounds a Judge agent
reads the transcript and emits a *structured* verdict (not free text)
that callers can pipe into a ticketing system, a database, or an audit
log.

    Round 0:  PRO argues case
    Round 0:  CON rebuts
    Round 1:  PRO responds
    Round 1:  CON responds
    ...
    Judge reads the full transcript, emits Verdict(winner, confidence,
    reasoning, key_points)

What's differentiated about Locus here:

* The transcript is built by appending each turn's output to a state
  list — using the typed reducer for ``list[Turn]`` so messages from
  parallel branches merge cleanly.
* The Judge uses Locus's ``output_schema`` so the verdict is a
  Pydantic ``Verdict`` instance, not a JSON-blob you have to parse.
* The whole debate is one ``StateGraph.execute`` call. Cancel,
  checkpoint, and GSAR judgment attach for free.

Run::

    python examples/tutorial_44_debate_with_judge.py

Difficulty: Advanced
Prerequisites: tutorial_13_structured_output, tutorial_43 (this series)
"""

from __future__ import annotations

import asyncio
from typing import Any

from config import get_model
from pydantic import BaseModel, Field

from locus.agent import Agent, AgentConfig
from locus.core.events import TerminateEvent
from locus.multiagent.graph import END, START, StateGraph


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


class Turn(BaseModel):
    """One turn of the debate."""

    side: str  # "pro" | "con"
    round: int
    text: str


class Verdict(BaseModel):
    """Judge's structured ruling."""

    winner: str = Field(description="'pro', 'con', or 'tie'")
    confidence: float = Field(ge=0.0, le=1.0, description="0..1 confidence in the call")
    key_points: list[str] = Field(description="The 2–4 strongest arguments that drove the decision")
    reasoning: str = Field(description="One-paragraph rationale")


PRO_PROMPT = (
    "You are arguing the FOR side. Be specific, cite reasoning, and "
    "directly rebut the OPPOSITION's most recent point if any. Three "
    "sentences max."
)
CON_PROMPT = (
    "You are arguing the AGAINST side. Be specific, cite reasoning, and "
    "directly rebut the FOR side's most recent point if any. Three "
    "sentences max."
)
JUDGE_PROMPT = (
    "You are an impartial debate judge. Read the full transcript and "
    "emit a Verdict object. Pick a winner only if one side clearly "
    "outargued the other; otherwise return 'tie'."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(role: str, prompt: str, model: Any) -> Agent:
    return Agent(
        config=AgentConfig(
            agent_id=f"debate-{role}",
            model=model,
            system_prompt=prompt,
            max_iterations=2,
            max_tokens=300,
        )
    )


async def _argue(agent: Agent, transcript: list[Turn], topic: str, side: str, rnd: int) -> str:
    history = "\n".join(f"[{t.side.upper()} r{t.round}] {t.text}" for t in transcript)
    prompt = (
        f"Topic: {topic}\n\n"
        f"Transcript so far:\n{history or '(no turns yet)'}\n\n"
        f"You are arguing the {side.upper()} side, round {rnd}. Make your point now."
    )
    final = ""
    async for event in agent.run(prompt):
        if isinstance(event, TerminateEvent):
            final = event.final_message or ""
    return final.strip()


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


async def pro_turn(state: dict[str, Any]) -> dict[str, Any]:
    agent = _make_agent("pro", PRO_PROMPT, state["__model__"])
    rnd = state.get("round", 0)
    text = await _argue(agent, state.get("transcript", []), state["topic"], "pro", rnd)
    return {"transcript": state.get("transcript", []) + [Turn(side="pro", round=rnd, text=text)]}


async def con_turn(state: dict[str, Any]) -> dict[str, Any]:
    agent = _make_agent("con", CON_PROMPT, state["__model__"])
    rnd = state.get("round", 0)
    text = await _argue(agent, state.get("transcript", []), state["topic"], "con", rnd)
    return {
        "transcript": state.get("transcript", []) + [Turn(side="con", round=rnd, text=text)],
        "round": rnd + 1,
    }


async def judge_turn(state: dict[str, Any]) -> dict[str, Any]:
    """Use ``output_schema=Verdict`` so the verdict is a typed Pydantic object.

    With a real model, ``result.parsed`` is a populated ``Verdict``
    instance. With ``MockModel``, the mock can't honor a JSON schema so
    ``result.parsed`` is None and we surface the raw text instead.
    """
    import asyncio as _asyncio

    agent = Agent(
        config=AgentConfig(
            agent_id="judge",
            model=state["__model__"],
            system_prompt=JUDGE_PROMPT,
            output_schema=Verdict,
            max_iterations=2,
            max_tokens=400,
        )
    )
    transcript_text = "\n".join(
        f"[{t.side.upper()} r{t.round}] {t.text}" for t in state["transcript"]
    )
    prompt = f"Topic: {state['topic']}\n\nTranscript:\n{transcript_text}\n\nNow emit your Verdict."
    # Run in a worker thread to avoid nesting an asyncio loop inside this
    # already-async graph node — ``run_sync`` is the entry point that
    # returns the parsed object.
    final = await _asyncio.to_thread(agent.run_sync, prompt)
    return {"verdict": final.parsed, "verdict_raw": final.message}


# ---------------------------------------------------------------------------
# Routing — N rounds of pro/con, then judge
# ---------------------------------------------------------------------------


N_ROUNDS = 2


def route_after_con(state: dict[str, Any]) -> str:
    if state.get("round", 0) >= N_ROUNDS:
        return "judge"
    return "pro"


def build_debate_graph() -> StateGraph:
    graph = StateGraph(name="debate-with-judge")
    graph.add_node("pro", pro_turn)
    graph.add_node("con", con_turn)
    graph.add_node("judge", judge_turn)
    graph.add_edge(START, "pro")
    graph.add_edge("pro", "con")
    graph.add_conditional_edges("con", route_after_con, targets={"pro": "pro", "judge": "judge"})
    graph.add_edge("judge", END)
    return graph


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


async def main() -> None:
    print("Tutorial 44: Debate with structured-output judge")
    print("=" * 60)

    model = get_model()
    graph = build_debate_graph()
    initial = {
        "topic": "Should Python have static typing enabled by default?",
        "transcript": [],
        "round": 0,
        "__model__": model,
    }

    print(f"\nTopic: {initial['topic']!r}\n")
    print(f"Running {N_ROUNDS} rounds of PRO vs CON, then judge…\n")

    result = await graph.execute(initial)
    transcript: list[Turn] = result.final_state.get("transcript", [])
    verdict: Verdict | None = result.final_state.get("verdict")

    print(f"Total turns: {len(transcript)}")
    print()
    for t in transcript:
        print(f"  [{t.side.upper()} r{t.round}] {t.text}")

    print()
    print("Verdict:")
    print("-" * 60)
    if verdict is None:
        print(f"(unparsed) {result.final_state.get('verdict_raw', '')}")
    else:
        print(f"  Winner:     {verdict.winner}")
        print(f"  Confidence: {verdict.confidence:.2f}")
        print(f"  Key points:")
        for p in verdict.key_points:
            print(f"    - {p}")
        print(f"  Reasoning:  {verdict.reasoning}")


if __name__ == "__main__":
    asyncio.run(main())
