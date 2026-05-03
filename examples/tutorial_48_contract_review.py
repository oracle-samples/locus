#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tutorial 48: Contract-review workflow (parallel review + negotiation loop).

Real contract review involves multiple stakeholders working in
parallel, then a back-and-forth negotiation phase, then sign-off:

    Contract intake
       │
       ▼
    Parser  (extracts clauses)
       │
       ▼
    Scatter to 3 parallel reviewers
       ├── Legal    (regulatory risk, indemnity, termination)
       ├── Risk     (financial exposure, liability cap)
       └── Commercial (price, terms, SLAs)
       ▼
    Synthesizer  (consolidated review report)
       │
       ▼
    Negotiation gate ── any blockers? ── yes ──> Negotiate (interrupt; loop)
                                       │            │
                                       │            └── revised terms ──┐
                                       │                                │
                                       └── no ──┐                       │
                                                ▼                       │
                                          Sign-off  <───────────────────┘
                                                ▼
                                          ContractDecision (typed)

Locus primitives:

* ``Send`` — three reviewers run concurrently.
* ``add_conditional_edges`` with cycle support — negotiation can loop
  back to re-review when terms change.
* ``interrupt()`` — negotiation step pauses for the human counsel to
  edit terms.
* ``output_schema=ContractDecision`` — final artifact is typed.

Why this is enterprise-shaped:

* Multi-stakeholder parallel review is the default in legal-ops; the
  ``Send`` primitive expresses it without a TaskGroup.
* The negotiation loop has a hard cap (max 3 rounds) so the workflow
  can never get stuck — graphs in Locus declare cycles explicitly via
  ``GraphConfig(allow_cycles=True)``.

Run::

    python examples/tutorial_48_contract_review.py

Difficulty: Advanced
Prerequisites: tutorial_42 (Send), tutorial_43 (refinement loop), 45 (HITL)
"""

from __future__ import annotations

import asyncio
from typing import Any

from config import get_model
from pydantic import BaseModel, Field

from locus.agent import Agent, AgentConfig
from locus.core import Command, interrupt
from locus.core.events import TerminateEvent
from locus.core.send import Send
from locus.multiagent.graph import END, START, GraphConfig, StateGraph


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


class ReviewerFinding(BaseModel):
    perspective: str  # "legal" | "risk" | "commercial"
    blockers: list[str]
    recommended_changes: list[str]
    risk_score: float = Field(ge=0.0, le=1.0)


class ContractDecision(BaseModel):
    contract_id: str
    counterparty: str
    rounds: int
    blockers_resolved: list[str]
    open_blockers: list[str]
    final_terms_summary: str
    decision: str = Field(description="signed | rejected | abandoned")


# ---------------------------------------------------------------------------
# Specialists
# ---------------------------------------------------------------------------


PROMPTS = {
    "legal": (
        "You are an in-house counsel. Read the contract excerpt and identify "
        "concrete legal blockers (indemnity, jurisdiction, termination, IP, "
        "liability cap). Bullets. End with: BLOCKERS=<count>."
    ),
    "risk": (
        "You are an enterprise-risk analyst. Identify concrete financial "
        "or operational risks. Bullets. End with: BLOCKERS=<count>."
    ),
    "commercial": (
        "You are a commercial-terms reviewer. Identify pricing or SLA "
        "concerns. Bullets. End with: BLOCKERS=<count>."
    ),
}


def _make_agent(role: str, model: Any) -> Agent:
    return Agent(
        config=AgentConfig(
            agent_id=f"contract-{role}",
            model=model,
            system_prompt=PROMPTS[role],
            max_iterations=2,
            max_tokens=400,
        )
    )


async def _run(agent: Agent, prompt: str) -> str:
    final = ""
    async for event in agent.run(prompt):
        if isinstance(event, TerminateEvent):
            final = event.final_message or ""
    return final.strip()


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def parse_contract(state: dict[str, Any]) -> dict[str, Any]:
    """In production this would chunk the PDF; here we just normalise text."""
    return {"clauses": state.get("contract_text", "").strip()}


async def scatter_reviewers(state: dict[str, Any]) -> list[Send]:
    perspectives = ("legal", "risk", "commercial")
    return [
        Send(node="review_one", payload={"perspective": p}, metadata={"perspective": p})
        for p in perspectives
    ]


async def review_one(state: dict[str, Any]) -> dict[str, Any]:
    perspective = state["perspective"]
    agent = _make_agent(perspective, state["__model__"])
    text = await _run(
        agent,
        f"Contract clauses:\n{state.get('clauses', '')}\n\nGive your {perspective} review.",
    )
    # Heuristic: any line starting with "-" or "•" is a finding; treat first
    # half as blockers, rest as recommendations.
    bullets = [
        b.lstrip("- *•").strip() for b in text.splitlines() if b.strip().startswith(("-", "*", "•"))
    ]
    half = max(1, len(bullets) // 2)
    return {
        "finding": ReviewerFinding(
            perspective=perspective,
            blockers=bullets[:half] if bullets else [text or "(no findings)"],
            recommended_changes=bullets[half:],
            risk_score=0.5,
        )
    }


async def synthesize(state: dict[str, Any]) -> dict[str, Any]:
    findings = [v["finding"] for v in state.values() if isinstance(v, dict) and "finding" in v]
    blockers = [b for f in findings for b in f.blockers]
    return {
        "findings": findings,
        "open_blockers": blockers,
        "rounds": state.get("rounds", 0) + 1,
    }


def negotiation_gate(state: dict[str, Any]) -> str:
    """Loop back to re-review if blockers exist and we're under the cap."""
    if not state.get("open_blockers"):
        return "sign_off"
    if state.get("rounds", 0) >= 3:
        return "sign_off"  # cap: 3 rounds; sign-off node decides reject vs sign
    return "negotiate"


async def negotiate(state: dict[str, Any]) -> Any:
    """Pause for human counsel to redline a clause.

    Returns a ``Command`` that explicitly routes to the next node. Three
    outcomes:

    - ``RESOLVED``: counterparty accepted our terms. Skip re-review and
      go straight to sign-off — Command(goto="sign_off").
    - ``WALK``: counterparty refused; abandon. Also goes to sign-off
      (which marks the decision as 'abandoned').
    - Custom redline text: continue the loop — re-parse + re-review.
    """
    from locus.core import goto

    open_blockers = state.get("open_blockers", [])
    response = interrupt(
        {
            "type": "negotiation",
            "round": state.get("rounds"),
            "question": "Counterparty redline the contract — what's the new clause language?",
            "open_blockers": open_blockers,
            "options": [
                "RESOLVED: counterparty agreed to our terms",
                "WALK: counterparty refused; abandon",
                "<custom redline text>",
            ],
        }
    )
    if response.startswith("WALK"):
        return goto(
            "sign_off",
            walk_away=True,
            open_blockers=open_blockers,
        )
    if response.startswith("RESOLVED"):
        return goto(
            "sign_off",
            blockers_resolved=list(state.get("blockers_resolved", [])) + open_blockers,
            open_blockers=[],
            clauses=state.get("clauses", "") + "\n[All blockers resolved per redline.]",
        )
    # Counterparty redlined — feed the new text back through review.
    return {
        "clauses": response,
        "blockers_resolved": list(state.get("blockers_resolved", [])) + open_blockers,
        "open_blockers": [],
    }


async def sign_off(state: dict[str, Any]) -> dict[str, Any]:
    """Emit ``ContractDecision`` via ``Agent.output_schema=ContractDecision``.

    A real-world sign-off step is an LLM-summarised audit record. The
    Agent reads accumulated state and produces the typed Pydantic
    instance. MockModel fallback is deterministic so the demo always
    finishes with a valid decision.
    """
    import asyncio as _asyncio

    if state.get("walk_away"):
        outcome = "abandoned"
    elif state.get("open_blockers"):
        outcome = "rejected"
    else:
        outcome = "signed"

    agent = Agent(
        config=AgentConfig(
            agent_id="contract-signoff",
            model=state["__model__"],
            system_prompt=(
                "You are a contract-ops officer writing the final ContractDecision. "
                "Summarise the negotiation in two sentences. Use the supplied "
                "structured fields verbatim."
            ),
            output_schema=ContractDecision,
            max_iterations=2,
            max_tokens=300,
        )
    )
    prompt = (
        f"Contract: {state.get('contract_id')}\n"
        f"Counterparty: {state.get('counterparty')}\n"
        f"Decision: {outcome}\n"
        f"Rounds: {state.get('rounds', 0)}\n"
        f"Resolved blockers: {state.get('blockers_resolved', [])}\n"
        f"Open blockers: {state.get('open_blockers', [])}\n"
        f"Final terms (first 200 chars): {(state.get('clauses') or '')[:200]}\n\n"
        "Emit the ContractDecision."
    )
    result = await _asyncio.to_thread(agent.run_sync, prompt)
    decision = result.parsed
    if decision is None:
        # MockModel fallback.
        decision = ContractDecision(
            contract_id=state.get("contract_id", "C-0001"),
            counterparty=state.get("counterparty", "(unknown)"),
            rounds=state.get("rounds", 0),
            blockers_resolved=state.get("blockers_resolved", []),
            open_blockers=state.get("open_blockers", []),
            final_terms_summary=(state.get("clauses") or "")[:200],
            decision=outcome,
        )
    return {"decision": decision}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def build_review_graph() -> StateGraph:
    g = StateGraph(
        name="contract-review",
        # The negotiation loop creates a cycle parse → scatter → synthesize
        # → negotiate → parse, so we opt into cycles.
        config=GraphConfig(allow_cycles=True, max_iterations=20),
    )
    g.add_node("parse", parse_contract)
    g.add_node("scatter", scatter_reviewers)
    g.add_node("review_one", review_one)
    g.add_node("synthesize", synthesize)
    g.add_node("negotiate", negotiate)
    g.add_node("sign_off", sign_off)

    g.add_edge(START, "parse")
    g.add_edge("parse", "scatter")
    g.add_edge("scatter", "synthesize")
    g.add_conditional_edges(
        "synthesize",
        negotiation_gate,
        targets={"negotiate": "negotiate", "sign_off": "sign_off"},
    )
    g.add_edge("negotiate", "parse")  # loop back: re-review the new terms
    g.add_edge("sign_off", END)
    return g


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


SAMPLE_CONTRACT = """\
Master Services Agreement (excerpt)

1. Term: 36 months, auto-renew unless cancelled with 90 days notice.
2. Payment: Net-30, 5% late fee per month, no cap.
3. Indemnity: Vendor indemnifies Customer for IP claims; Customer
   indemnifies Vendor for everything else, uncapped.
4. Termination: Vendor may terminate for convenience with 30 days
   notice; Customer may terminate only for material breach.
5. Data: Customer data may be processed in any region. No deletion
   guarantee on termination.
6. Liability cap: 1× annual fees.
"""


def _print_decision(d: ContractDecision | None) -> None:
    print("\nContract decision:")
    print("-" * 60)
    if d is None:
        print("(missing)")
        return
    print(f"  Contract:           {d.contract_id}")
    print(f"  Counterparty:       {d.counterparty}")
    print(f"  Decision:           {d.decision.upper()}")
    print(f"  Negotiation rounds: {d.rounds}")
    print(f"  Resolved blockers:  {len(d.blockers_resolved)}")
    print(f"  Open blockers:      {len(d.open_blockers)}")


async def main() -> None:
    print("Tutorial 48: Contract review workflow")
    print("=" * 60)

    model = get_model()
    graph = build_review_graph()
    initial = {
        "contract_id": "C-2026-0815",
        "counterparty": "MegaCorp Cloud Solutions",
        "contract_text": SAMPLE_CONTRACT,
        "__model__": model,
    }

    print(f"\nReviewing: {initial['counterparty']} ({initial['contract_id']})")

    # Auto-resolve the first negotiation round, walk away on the second
    # (just to demonstrate the abandon path).
    answers = ["RESOLVED: counterparty agreed to our terms"]
    result = await graph.execute(initial)
    answer_idx = 0
    while result.interrupt:
        answer = answers[answer_idx] if answer_idx < len(answers) else "RESOLVED"
        answer_idx += 1
        payload = result.interrupt.interrupt.payload
        print(
            f"\n  ⏸  Round {payload.get('round')}: {len(payload.get('open_blockers', []))} blocker(s)"
        )
        for b in payload.get("open_blockers", [])[:3]:
            print(f"      - {b[:80]}")
        print(f"  ▶  Counsel responds: {answer!r}")
        result = await graph.execute(
            Command(resume=answer, update={**result.final_state, "__model__": model})
        )

    print(f"\nWorkflow finished in {result.duration_ms:.0f} ms")
    _print_decision(result.final_state.get("decision"))


if __name__ == "__main__":
    asyncio.run(main())
