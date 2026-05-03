#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tutorial 42: Map-Reduce code-review crew.

This tutorial covers a multi-agent pattern that's awkward in most
SDKs but native in Locus: **scatter-gather** via the ``Send`` primitive.

The setup:
    Diff splitter      ──>  N Reviewers (parallel)  ──>  Synthesizer
   (one node, fan-out)        (run in parallel via Send)     (one node, reduce)

What's differentiated about Locus here:

- ``Send`` is a first-class graph primitive — the splitter just returns a
  list of ``Send(...)``s and the executor spawns parallel reviewers.
- The synthesizer reads each reviewer's output by name from the merged
  state. No queues, no manual ``asyncio.gather``, no shared mutable state.
- Each reviewer is a separate Locus ``Agent`` with its own role, system
  prompt, and tool set. The graph orchestrates them, not a hand-written
  for-loop.
- Whole pipeline is one ``StateGraph.execute`` call. Streaming, cancel,
  checkpoint, GSAR judgment all attach for free.

Run::

    python examples/tutorial_42_map_reduce_code_review.py

Difficulty: Advanced
Prerequisites: tutorial_06_basic_graph, tutorial_11_swarm_multiagent
"""

from __future__ import annotations

import asyncio
from typing import Any

from config import get_model

from locus.agent import Agent, AgentConfig
from locus.core.send import Send
from locus.multiagent.graph import END, START, StateGraph


# ----------------------------------------------------------------------------
# Sample diff — three independent files we want reviewed in parallel
# ----------------------------------------------------------------------------

SAMPLE_FILES = {
    "auth.py": """
def login(username, password):
    if password == "admin123":
        return {"role": "admin", "token": username}
    return {"role": "user", "token": username}
""",
    "billing.py": """
def calculate_total(items, tax_rate):
    total = 0
    for item in items:
        total = total + item.price
    return total * (1 + tax_rate)
""",
    "search.py": """
def search(query, db):
    sql = f"SELECT * FROM products WHERE name LIKE '%{query}%'"
    return db.execute(sql).fetchall()
""",
}


# ----------------------------------------------------------------------------
# Reviewer roles — each gets its own system prompt and runs as an Agent
# ----------------------------------------------------------------------------

REVIEWER_ROLES = {
    "security": (
        "You are a senior application-security reviewer. Read the code and "
        "list every concrete security issue you can prove with the snippet "
        "(SQL injection, hardcoded credentials, missing auth, unvalidated "
        "input, etc.). Be specific. Do not invent issues. End with a single "
        "line: SEVERITY=<low|medium|high|critical>."
    ),
    "performance": (
        "You are a performance-engineering reviewer. List concrete inefficiencies "
        "in the code (N+1 patterns, accidental quadratic loops, redundant work, "
        "missing batching, blocking I/O, etc.). End with: SEVERITY=<...>."
    ),
    "style": (
        "You are a Python style/idiom reviewer focused on readability, naming, "
        "and modern Python idioms. Be terse. End with: SEVERITY=<...>."
    ),
}


def _make_reviewer(role: str, model: Any) -> Agent:
    return Agent(
        config=AgentConfig(
            agent_id=f"reviewer-{role}",
            model=model,
            system_prompt=REVIEWER_ROLES[role],
            max_iterations=2,  # one model call is enough for static review
            max_tokens=400,
        )
    )


# ----------------------------------------------------------------------------
# Graph nodes
# ----------------------------------------------------------------------------


async def split_files(state: dict[str, Any]) -> list[Send]:
    """Fan out: emit one Send per (file, role) combination.

    With 3 files × 3 roles = 9 reviewers run concurrently. The graph
    executor spawns them in parallel — we don't write any asyncio.
    """
    files: dict[str, str] = state["files"]
    roles = list(REVIEWER_ROLES)
    return [
        Send(
            node="review_one",
            payload={"file_name": fname, "code": code, "role": role},
            metadata={"file": fname, "role": role},
        )
        for fname in files
        for code, _ in [(files[fname], None)]
        for role in roles
    ]


async def review_one(state: dict[str, Any]) -> dict[str, Any]:
    """One reviewer agent runs against one file with one role.

    Uses ``async for event in agent.run(...)`` rather than ``run_sync()``
    so 9 of these run truly in parallel inside the graph's
    ``asyncio.gather`` (instead of serialising on a single thread-pool
    worker each).
    """
    from locus.core.events import TerminateEvent

    role: str = state["role"]
    file_name: str = state["file_name"]
    code: str = state["code"]
    model = state["__model__"]
    agent = _make_reviewer(role, model)
    prompt = (
        f"File: {file_name}\n"
        f"Role: {role}\n\n"
        f"```python\n{code}\n```\n\n"
        f"Review the code as the {role} reviewer."
    )
    final_msg: str = ""
    iterations = 0
    async for event in agent.run(prompt):
        if isinstance(event, TerminateEvent):
            final_msg = event.final_message or ""
            iterations = event.iterations_used
    return {
        "review": {
            "file": file_name,
            "role": role,
            "comments": final_msg.strip(),
            "iterations": iterations,
        }
    }


async def synthesize(state: dict[str, Any]) -> dict[str, Any]:
    """Reduce: collapse all per-(file, role) reviews into one report.

    The graph stored each ``review_one`` output under a Send-id key. We
    walk the state and pull every ``review`` payload out.
    """
    reviews = [v["review"] for v in state.values() if isinstance(v, dict) and "review" in v]
    by_file: dict[str, list[dict[str, Any]]] = {}
    for r in reviews:
        by_file.setdefault(r["file"], []).append(r)

    lines = ["# Code review report", ""]
    for fname in sorted(by_file):
        lines.append(f"## {fname}")
        for r in sorted(by_file[fname], key=lambda x: x["role"]):
            lines.append(f"### {r['role']}")
            lines.append(r["comments"])
            lines.append("")
    return {"report": "\n".join(lines), "review_count": len(reviews)}


# ----------------------------------------------------------------------------
# Build the graph
# ----------------------------------------------------------------------------


def build_review_graph(model: Any) -> StateGraph:
    """Wire the three nodes: split → review_one (parallel) → synthesize → END.

    The model is threaded through state under ``__model__`` so each
    reviewer node can build its agent without a closure over the outer
    scope. (Pydantic-friendly, picklable for checkpointing.)
    """
    graph = StateGraph(name="code-review-crew")
    graph.add_node("split", split_files)
    graph.add_node("review_one", review_one)
    graph.add_node("synthesize", synthesize)

    graph.add_edge(START, "split")
    # No edge ``split → review_one`` — the Sends from ``split`` carry the
    # routing themselves. After every Send completes, control flows back
    # to ``split``'s adjacency, which we point at ``synthesize``.
    graph.add_edge("split", "synthesize")
    graph.add_edge("synthesize", END)
    return graph


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------


async def main() -> None:
    print("Tutorial 42: Map-Reduce code-review crew")
    print("=" * 60)

    model = get_model()
    graph = build_review_graph(model)

    initial = {"files": SAMPLE_FILES, "__model__": model}

    print(
        f"\nFanning out {len(SAMPLE_FILES)} files × {len(REVIEWER_ROLES)} roles "
        f"= {len(SAMPLE_FILES) * len(REVIEWER_ROLES)} reviewer agents in parallel...\n"
    )

    result = await graph.execute(initial)

    print(
        f"Graph completed in {result.duration_ms:.0f} ms across "
        f"{result.iterations} graph iteration(s)"
    )
    print(f"Reviews collected: {result.final_state.get('review_count', 0)}")
    print()
    print(result.final_state.get("report", "(no report)"))


if __name__ == "__main__":
    asyncio.run(main())
