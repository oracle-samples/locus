# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Live integration tests for the GSAR layer.

These hit a real LLM judge and exercise the full Algorithm-1 outer
loop end-to-end:

- A clearly-grounded report should land at ``δ = proceed`` on the
  first iteration. Asserts the judge correctly recognises tool-typed
  evidence and the score function clears ``τ_proceed = 0.80``.
- A clearly-ungrounded / contradicted report should not land at
  ``proceed`` on the first iteration; the loop should escalate to
  ``replan`` (or, with a generous threshold, ``regenerate``).
- The trajectory log must be monotonically non-decreasing in
  ``iteration`` and present the right number of entries.

Activation: ``OPENAI_API_KEY`` (uses ``gpt-4o-mini`` as the judge).
Skipped automatically when the key isn't set.
"""

from __future__ import annotations

import pytest

from tests.integration.conftest import skip_without_openai


@skip_without_openai
@pytest.mark.asyncio
async def test_gsar_grounded_report_proceeds() -> None:
    from locus.models.native.openai import OpenAIModel
    from locus.reasoning.gsar import Decision
    from locus.reasoning.gsar_evaluator import GSAREvaluator
    from locus.reasoning.gsar_judge import JudgeOutput, StructuredOutputGSARJudge

    judge = StructuredOutputGSARJudge(
        model=OpenAIModel(model="gpt-4o-mini", max_tokens=2048),
    )

    report = (
        "CPU utilisation on host db-prod-1 reached 97% at 14:02 UTC. "
        "Request rate dropped to 12 RPS at the same time. "
        "These two observations indicate the spike is real."
    )
    evidence = (
        "[tool=query_metrics row=14:02:01] host=db-prod-1 cpu_pct=97.2\n"
        "[tool=query_metrics row=14:02:01] host=db-prod-1 rps=12.4\n"
        "[signal] alert_id=A-9912 fired_at=14:02:00 metric=cpu_pct severity=high\n"
    )

    async def regen(syn: str, jo: JudgeOutput) -> str:  # pragma: no cover
        raise AssertionError(
            f"unexpected regenerate on grounded report; jo={jo.model_dump_json()[:300]}"
        )

    async def replan(  # pragma: no cover
        syn: str, ev: str, jo: JudgeOutput
    ) -> tuple[str, str]:
        raise AssertionError(
            f"unexpected replan on grounded report; jo={jo.model_dump_json()[:300]}"
        )

    evaluator = GSAREvaluator(judge=judge, regenerate_fn=regen, replan_fn=replan)
    result = await evaluator.evaluate(report_synthesis=report, evidence_corpus=evidence)

    assert result.final_decision == Decision.PROCEED, (
        f"final={result.final_decision}, score={result.final_score:.3f}, "
        f"trajectory={[t.decision for t in result.trajectory]}"
    )
    assert result.final_score >= 0.80
    assert result.replans_used == 0
    assert result.regenerations_used == 0
    assert not result.degraded
    assert len(result.trajectory) == 1


@skip_without_openai
@pytest.mark.asyncio
async def test_gsar_ungrounded_report_does_not_proceed_first_iteration() -> None:
    from locus.models.native.openai import OpenAIModel
    from locus.reasoning.gsar import Decision
    from locus.reasoning.gsar_evaluator import GSAREvaluator
    from locus.reasoning.gsar_judge import JudgeOutput, StructuredOutputGSARJudge

    judge = StructuredOutputGSARJudge(
        model=OpenAIModel(model="gpt-4o-mini", max_tokens=2048),
    )

    # Report makes specific factual claims that the evidence does not
    # support. A well-functioning judge should partition the unsupported
    # claims into ungrounded (or contradicted), driving S below τ_proceed.
    report = (
        "The outage was caused by a failed power supply unit in rack 7B. "
        "The replacement was completed at 03:15 UTC. "
        "Customer-facing latency returned to baseline within 8 minutes."
    )
    evidence = (
        "[tool=query_metrics row=02:50:00] cluster=us-west-2a request_rate=0\n"
        "[signal] alert_id=A-1042 fired_at=02:48:12 metric=availability severity=critical\n"
    )

    # Cap replan to 1 so the test exits deterministically without
    # depending on whether the judge ever recovers.
    seen_decisions: list[Decision] = []

    async def regen(syn: str, jo: JudgeOutput) -> str:
        seen_decisions.append(Decision.REGENERATE)
        # Echo back unchanged — we want the loop to escalate.
        return syn

    async def replan(syn: str, ev: str, jo: JudgeOutput) -> tuple[str, str]:
        seen_decisions.append(Decision.REPLAN)
        return syn, ev

    evaluator = GSAREvaluator(
        judge=judge,
        regenerate_fn=regen,
        replan_fn=replan,
        k_max=1,
    )
    result = await evaluator.evaluate(report_synthesis=report, evidence_corpus=evidence)

    # The first-iteration decision must NOT be proceed for this report.
    assert result.trajectory[0].decision != Decision.PROCEED, (
        f"judge wrongly accepted ungrounded report at first iteration: "
        f"score={result.trajectory[0].score:.3f}"
    )
    # The loop should have spent at least one recovery action.
    assert len(seen_decisions) >= 1
    # Iteration counter must be sequential.
    assert [t.iteration for t in result.trajectory] == list(range(len(result.trajectory)))


@skip_without_openai
@pytest.mark.asyncio
async def test_gsar_judge_emits_partition_with_evidence_types() -> None:
    """Verify the live judge populates the partition with ``EvidenceType``s.

    Targets the most regression-prone part of the §6 contract: the
    judge has to map natural-language claims onto the eight-element
    evidence taxonomy, not just emit a binary verdict.
    """
    from locus.models.native.openai import OpenAIModel
    from locus.reasoning.gsar import EvidenceType
    from locus.reasoning.gsar_judge import StructuredOutputGSARJudge

    judge = StructuredOutputGSARJudge(
        model=OpenAIModel(model="gpt-4o-mini", max_tokens=2048),
    )

    out = await judge.judge(
        report_synthesis=(
            "CPU utilisation on host db-prod-1 reached 97% at 14:02 UTC. "
            "This likely indicates a runaway query."
        ),
        evidence_corpus=("[tool=query_metrics row=14:02:01] host=db-prod-1 cpu_pct=97.2\n"),
    )

    # Judge resolved (didn't abstain).
    assert not out.abstained, f"unexpected abstain: {out.abstain_reason}"
    # At least one claim landed in some bucket.
    partition = out.to_partition()
    assert partition.total_claims >= 1
    # Every emitted claim has a typed EvidenceType.
    for claim in partition.all_claims():
        assert isinstance(claim.type, EvidenceType)
    # The grounded "97%" claim should attract a tool-flavoured type.
    grounded_types = {c.type for c in partition.grounded}
    tool_flavoured = {
        EvidenceType.TOOL_MATCH,
        EvidenceType.SPECIFIC_DATA,
        EvidenceType.SIGNAL_MATCH,
    }
    assert grounded_types & tool_flavoured, (
        f"expected at least one grounded claim with tool-flavoured type, "
        f"got grounded={[(c.text, c.type) for c in partition.grounded]}"
    )
