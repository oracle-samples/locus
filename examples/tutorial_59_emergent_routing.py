#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tutorial 59: opt-in LLM protocol picker — emergent routing.

Tutorial 51 covers the default deterministic router: the LLM fills a
:class:`GoalFrame`, then :func:`_rank_key` picks a protocol via a
tuple comparison. Auditable, reproducible, and rule-based.

This tutorial covers the **opt-in** second mode: a
:class:`LLMProtocolPicker` that lets the model make the *last-mile*
pick when multiple protocols pass the filter. Filtering, policy
gating, capability binding and builder dispatch all stay rule-based —
only the disambiguation between equally-eligible protocols moves to
the model.

What you'll see:

1. The same router built two ways — once with the default
   rule-based ranker, once with ``protocol_picker=LLMProtocolPicker(...)``.
2. Five prompts dispatched through both routers side-by-side.
3. A deliberately ambiguous prompt (``COMPARE`` task type) where the
   two modes pick *different* protocols, and the picker's rationale
   field surfaces *why*.

Difficulty: intermediate. Prerequisites: tutorial 51 (cognitive
router) and tutorial 13 (structured output).

Run with:
    python examples/tutorial_59_emergent_routing.py
"""

from __future__ import annotations

import asyncio

from config import get_model

from locus import Agent, tool
from locus.router import (
    CapabilityIndex,
    CognitiveCompiler,
    GoalFrame,
    LLMProtocolPicker,
    PolicyGate,
    ProtocolRegistry,
    Router,
    builtin_protocols,
)
from locus.tools.registry import create_registry


# ---------------------------------------------------------------------------
# Capabilities — three small tools shared by both routers.
# ---------------------------------------------------------------------------


@tool
def kb_search(query: str) -> str:
    """Search the knowledge base for a topic."""
    canned = {
        "swarm": "Swarm = self-organizing pool claiming tasks from a shared queue.",
        "orchestrator": "Orchestrator = one coordinator picks specialists per sub-task.",
    }
    return canned.get(query.lower(), f"No KB entry for {query!r}.")


@tool
def get_metric(name: str) -> str:
    """Return the latest value of a named metric."""
    return {
        "latency_p99": "latency_p99=420ms (slo 300ms — breach)",
        "cpu": "cpu=87% (warn 80%)",
    }.get(name.lower(), f"no metric {name!r}")


@tool
def list_alerts(window_minutes: int = 30) -> str:
    """List recent alerts."""
    return (
        "alert_id=A-101 sev=high svc=checkout latency_p99 breach\n"
        "alert_id=A-102 sev=medium svc=catalog cpu_warn"
    )


def _build_compiler(model, capabilities, protocols, picker=None) -> CognitiveCompiler:
    return CognitiveCompiler(
        protocols=protocols,
        capabilities=capabilities,
        policy=PolicyGate(),
        model=model,
        protocol_picker=picker,
    )


def _build_extractor(model) -> Agent:
    return Agent(
        model=model,
        system_prompt=(
            "Fill the GoalFrame schema based on the user's verb and intent. "
            "required_capabilities may include: kb_search, metric_probe, alert_list."
        ),
        output_schema=GoalFrame,
    )


def build_routers() -> tuple[Router, Router]:
    """Return (default_router, emergent_router) — same registry, two modes."""
    model = get_model()

    tools = create_registry(kb_search, get_metric, list_alerts)
    capabilities = CapabilityIndex(tools)
    capabilities.annotate(
        "kb_search",
        tool_name="kb_search",
        description="Knowledge-base lookup.",
        domain="research",
    )
    capabilities.annotate(
        "metric_probe",
        tool_name="get_metric",
        description="Latest value of a named metric.",
        domain="observability",
    )
    capabilities.annotate(
        "alert_list",
        tool_name="list_alerts",
        description="Recent alerts in a window.",
        domain="observability",
    )

    protocols = ProtocolRegistry()
    protocols.register_many(builtin_protocols())

    default = Router(
        extractor=_build_extractor(model),
        compiler=_build_compiler(model, capabilities, protocols),
    )
    emergent = Router(
        extractor=_build_extractor(model),
        compiler=_build_compiler(
            model,
            capabilities,
            protocols,
            picker=LLMProtocolPicker(model=model),
        ),
    )
    return default, emergent


# ---------------------------------------------------------------------------
# Five prompts. Most route the same way under both modes. The ambiguous
# one (COMPARE) is where the picker earns its keep — debate vs
# specialist_fanout both qualify, and the picker can choose with
# intent-level reasoning that _rank_key can't.
# ---------------------------------------------------------------------------


PROMPTS = [
    "What does the locus router do in the context of this SDK?",
    "Diagnose the checkout API latency spike: pull metrics, list alerts, correlate findings.",
    "Outline a three-step refactor plan for our agent test suite. Read-only — no production changes.",
    "Compare swarm vs orchestrator patterns for open-ended research.",
    "Generate a Python function that returns the nth Fibonacci number, with tests.",
]


async def main() -> None:
    default, emergent = build_routers()

    print(f"{'─' * 90}")
    print(f"  PROMPT                                          | DEFAULT             | EMERGENT")
    print(f"{'─' * 90}")

    for prompt in PROMPTS:
        try:
            d_res = await default.dispatch(prompt)
            d_pid = d_res.protocol_id
        except Exception as exc:  # noqa: BLE001
            d_pid = f"ERR: {type(exc).__name__}"

        try:
            e_res = await emergent.dispatch(prompt)
            e_pid = e_res.protocol_id
        except Exception as exc:  # noqa: BLE001
            e_pid = f"ERR: {type(exc).__name__}"

        marker = "  " if d_pid == e_pid else "≠ "
        print(f"{marker}{prompt[:48]:<48} | {d_pid:<19} | {e_pid}")

    print(f"{'─' * 90}")
    print(
        "Read each row left-to-right: prompt → default protocol → emergent protocol.\n"
        "When the two columns differ (≠), the picker's rationale field on the\n"
        "router.protocol.selected event tells you why it chose differently. The\n"
        "filter, policy gate, and builder dispatch are identical in both modes —\n"
        "only the disambiguation step changed."
    )


if __name__ == "__main__":
    asyncio.run(main())
