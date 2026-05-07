# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Research workflow — StateGraph-based deep research with post-execution quality loop.

The production pattern for long-horizon research is not a single Agent loop
but a **StateGraph** that separates execution from quality evaluation:

.. code-block:: text

    START
      │
      ▼
    execute          ← Agent(reflexion=True) runs tool loop; collects evidence
      │
      ▼
    summarize        ← lightweight Agent distills findings into a summary
      │
      ▼
    grounding_eval   ← GroundingEvaluator scores summary claims vs evidence
      │
      ├─ score ≥ threshold ──► END  (structured result returned)
      │
      └─ score < threshold ──► replan ──► execute  (up to max_replans)

Key differences from ``create_deepagent``:

- The grounding check is **post-hoc** (on the summary, not per-turn).
- The replan loop operates at the **workflow** level — the whole execute →
  summarize → evaluate cycle reruns with a focused re-plan prompt.
- The summary and grounding phases use separate, cheaper model calls.

Quick start::

    from locus.deepagent.workflow import create_research_workflow, ResearchState
    from pydantic import BaseModel


    class Report(BaseModel):
        summary: str
        confidence: float


    workflow = create_research_workflow(
        model=get_model(),
        tools=[search_kb, inspect_record],
        output_schema=Report,
    )
    result = await workflow.execute(
        {"prompt": "Investigate FUSION.AP_INVOICES_ALL"}
    )
    report: Report = result.final_state["structured_output"]
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class ResearchWorkflowState(TypedDict, total=False):
    """Mutable state threaded through the research workflow."""

    prompt: str
    """The original research prompt."""

    execute_prompt: str
    """The prompt for the current execute phase (may be a focused re-plan)."""

    evidence: list[str]
    """Tool output strings collected during execute."""

    summary: str
    """Distilled summary produced by the summarize node."""

    grounding_score: float
    """GroundingEvaluator score for the current summary (0.0 – 1.0)."""

    ungrounded_claims: list[str]
    """Claims that scored below the grounding threshold."""

    replan_count: int
    """Number of replan iterations consumed so far."""

    structured_output: Any
    """Parsed output_schema instance from the final summary (if any)."""

    stop_reason: str
    """Terminal reason: 'grounded', 'max_replans', 'max_iterations'."""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_research_workflow(
    *,
    model: Any,
    tools: list[Any],
    system_prompt: str = "",
    output_schema: type[BaseModel] | None = None,
    grounding_threshold: float = 0.65,
    max_replans: int = 2,
    max_iterations: int = 20,
    summarization_model: Any | None = None,
    grounding_model: Any | None = None,
    reflexion: bool = True,
    checkpointer: Any | None = None,
) -> Any:
    """Build a StateGraph research workflow with post-execution grounding.

    The workflow mirrors the production pattern used in Optic's specialist
    agents: a ReAct loop that gathers evidence, followed by a summary step
    and an LLM-as-judge grounding evaluation. When the grounding score falls
    below ``grounding_threshold``, the workflow re-plans and re-runs the
    execute phase (up to ``max_replans`` times).

    Args:
        model: Primary model for the execute (ReAct) phase.
        tools: Tools available to the execute agent.
        system_prompt: Identity and domain context for the execute agent.
        output_schema: Optional Pydantic model — the summarize node will
            attempt to extract a structured instance from the summary text.
        grounding_threshold: Minimum grounding score to accept a summary
            (0.0 – 1.0). Default 0.65.
        max_replans: Maximum replan iterations before accepting the best
            summary. Default 2.
        max_iterations: Maximum ReAct iterations per execute phase. Default 20.
        summarization_model: Model for the summarize node. Falls back to
            ``model`` when ``None``.
        grounding_model: Model for LLM-based grounding eval. Falls back to
            ``model`` when ``None``.
        reflexion: Enable reflexion in the execute agent. Default True.
        checkpointer: Optional checkpointer for the StateGraph.

    Returns:
        A compiled ``locus.StateGraph`` ready to ``.execute(initial_state)``.
    """
    from locus.agent.agent import Agent  # noqa: PLC0415
    from locus.multiagent.graph import END, START, StateGraph  # noqa: PLC0415
    from locus.reasoning.grounding import GroundingEvaluator  # noqa: PLC0415

    _summarization_model = summarization_model or model
    _grounding_model = grounding_model or model

    grounding_eval = GroundingEvaluator()

    # ------------------------------------------------------------------
    # Node: execute
    # ------------------------------------------------------------------

    async def execute_node(state: ResearchWorkflowState) -> dict[str, Any]:
        """Run the ReAct agent loop and collect evidence from tool results."""
        prompt = state.get("execute_prompt") or state.get("prompt", "")

        base_prompt = system_prompt or (
            "You are a research agent. Use tools to investigate the given topic. "
            "Gather as much evidence as possible before concluding."
        )

        agent = Agent(
            model=model,
            tools=tools,
            system_prompt=base_prompt,
            reflexion=reflexion,
            max_iterations=max_iterations,
        )

        from locus.core.events import TerminateEvent, ToolCompleteEvent  # noqa: PLC0415

        evidence: list[str] = []
        async for event in agent.run(prompt):
            if isinstance(event, ToolCompleteEvent) and event.result:
                evidence.append(str(event.result)[:2000])
            elif isinstance(event, TerminateEvent) and event.final_message:
                evidence.append(f"[conclusion] {event.final_message[:2000]}")

        return {"evidence": evidence}

    # ------------------------------------------------------------------
    # Node: summarize
    # ------------------------------------------------------------------

    async def summarize_node(state: ResearchWorkflowState) -> dict[str, Any]:
        """Distill evidence into a summary, optionally parsing output_schema."""
        evidence = state.get("evidence", [])
        prompt = state.get("prompt", "")

        evidence_block = "\n\n".join(f"[{i + 1}] {e}" for i, e in enumerate(evidence))

        if output_schema:
            schema_hint = (
                f"\n\nReturn your answer as a JSON object matching this schema:\n"
                f"{json.dumps(output_schema.model_json_schema(), indent=2)}"
            )
        else:
            schema_hint = ""

        summarize_prompt = (
            f"Original research goal: {prompt}\n\n"
            f"Evidence gathered:\n{evidence_block}\n\n"
            f"Write a concise, factually grounded summary of your findings."
            f"{schema_hint}"
        )

        summarizer = Agent(
            model=_summarization_model,
            system_prompt="You are a precise summarizer. Only assert what the evidence supports.",
            output_schema=output_schema,
        )
        result = summarizer.run_sync(summarize_prompt)

        update: dict[str, Any] = {"summary": result.message or ""}
        if output_schema and result.parsed:
            update["structured_output"] = result.parsed

        return update

    # ------------------------------------------------------------------
    # Node: grounding_eval
    # ------------------------------------------------------------------

    async def grounding_eval_node(state: ResearchWorkflowState) -> dict[str, Any]:
        """Score the summary against gathered evidence with LLM-as-judge."""
        summary = state.get("summary", "")
        evidence = state.get("evidence", [])

        if not summary or not evidence:
            return {"grounding_score": 0.0, "ungrounded_claims": []}

        # Split summary into sentences as claims
        claims = [s.strip() for s in summary.replace("\n", " ").split(".") if len(s.strip()) > 10]

        grounding_result = await grounding_eval.evaluate_with_llm(
            claims=claims,
            evidence=evidence,
            model=_grounding_model,
        )

        return {
            "grounding_score": grounding_result.score,
            "ungrounded_claims": grounding_result.ungrounded_claims,
        }

    # ------------------------------------------------------------------
    # Node: replan
    # ------------------------------------------------------------------

    async def replan_node(state: ResearchWorkflowState) -> dict[str, Any]:
        """Generate a focused re-plan prompt targeting ungrounded claims."""
        ungrounded = state.get("ungrounded_claims", [])
        prompt = state.get("prompt", "")
        replan_count = state.get("replan_count", 0)

        if ungrounded:
            focused = "\n".join(f"- {c}" for c in ungrounded[:5])
            execute_prompt = (
                f"Previous investigation of '{prompt}' left these claims unverified:\n"
                f"{focused}\n\n"
                f"Gather specific evidence to verify or refute each claim above."
            )
        else:
            execute_prompt = (
                f"Repeat the investigation of '{prompt}' with a focus on "
                f"gathering stronger, more specific evidence."
            )

        return {
            "execute_prompt": execute_prompt,
            "replan_count": replan_count + 1,
        }

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route_after_grounding(state: dict[str, Any]) -> str:
        score = state.get("grounding_score", 0.0)
        replans = state.get("replan_count", 0)

        if score >= grounding_threshold:
            return END
        if replans >= max_replans:
            return END
        return "replan"

    # ------------------------------------------------------------------
    # Graph assembly
    # ------------------------------------------------------------------

    graph = StateGraph()
    graph.add_node("execute", execute_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("grounding_eval", grounding_eval_node)
    graph.add_node("replan", replan_node)

    graph.add_edge(START, "execute")
    graph.add_edge("execute", "summarize")
    graph.add_edge("summarize", "grounding_eval")
    graph.add_conditional_edges(
        "grounding_eval",
        route_after_grounding,
        {"replan": "replan", END: END},
    )
    graph.add_edge("replan", "execute")

    config = {}
    if checkpointer:
        config["checkpointer"] = checkpointer

    return graph.compile(**config)
