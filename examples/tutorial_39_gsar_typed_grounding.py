"""
Tutorial 39: GSAR — typed grounding for hallucination detection and recovery

This tutorial covers the GSAR layer from `arXiv:2604.23366` (Kamelhar 2026):

- The four-way claim partition (grounded / ungrounded / contradicted /
  complementary) as a Pydantic type.
- Equation (2) — the evidence-typed weighted grounding score `S`.
- Equation (3) — the three-tier `{proceed, regenerate, replan}`
  decision function with the Appendix-B reference thresholds
  (τ_proceed=0.80, τ_regenerate=0.65).
- Algorithm 1 — the bounded outer loop with `K_max` replan budget,
  driven by an `LLM-as-judge` and two side-effect callables.

Prerequisites:
- Configure model via environment variables (see examples/config.py).
- Optional: `OPENAI_API_KEY` to drive the live LLM judge in Part 4.

Difficulty: Advanced
"""

from __future__ import annotations

import asyncio
import time

from config import get_model

from locus.agent import Agent
from locus.reasoning.gsar import (
    DEFAULT_WEIGHT_MAP,
    Claim,
    Decision,
    EvidenceType,
    GSARThresholds,
    Partition,
    decide,
    gsar_score,
)


def _llm_call(
    prompt: str, *, system: str = "Reply in one short sentence.", max_tokens: int = 80
) -> str:
    """Helper: real model call with timing/token banner — used by every Part."""
    agent = Agent(model=get_model(max_tokens=max_tokens), system_prompt=system)
    t0 = time.perf_counter()
    res = agent.run_sync(prompt)
    dt = time.perf_counter() - t0
    print(
        f"  [model call: {dt:.2f}s · {res.metrics.prompt_tokens}→{res.metrics.completion_tokens} tokens]"
    )
    return res.message.strip()


# =============================================================================
# Part 1: The four-way partition + the Appendix-B weight table
# =============================================================================


def example_partition_and_weights() -> None:
    """Build a Partition by hand and read the reference weights."""
    print("=== Part 1: Partition + Appendix-B weights ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, why does GSAR partition claims into grounded/ungrounded/contradicted/complementary?')}"
    )

    partition = Partition(
        grounded=[
            Claim(text="CPU at 97% on db-prod-1", type=EvidenceType.TOOL_MATCH),
            Claim(text="Request rate dropped to 12 RPS", type=EvidenceType.SPECIFIC_DATA),
        ],
        ungrounded=[
            Claim(text="A runaway query is the cause", type=EvidenceType.INFERENCE),
        ],
        complementary=[
            Claim(
                text="Region-wide network event also plausible",
                type=EvidenceType.COMPLEMENTARY_FINDING,
            ),
        ],
        contradicted=[
            Claim(text="The saturation was transient", type=EvidenceType.INFERENCE),
        ],
    )
    print(
        f"Partition: |G|={len(partition.grounded)}, "
        f"|U|={len(partition.ungrounded)}, "
        f"|X|={len(partition.contradicted)}, "
        f"|K|={len(partition.complementary)}, "
        f"total={partition.total_claims}"
    )
    print()
    print("Reference weights (Appendix B):")
    for etype, weight in sorted(DEFAULT_WEIGHT_MAP.items(), key=lambda kv: -kv[1]):
        print(f"  {etype.value:24s} {weight:.2f}")


# =============================================================================
# Part 2: Score (Equation 2) and decision (Equation 3)
# =============================================================================


def example_score_and_decision() -> None:
    """Reproduce the worked example from Appendix E."""
    print("\n=== Part 2: Score and decision ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, what does the GSAR S-score (Eq. 2) measure?')}"
    )

    partition = Partition(
        grounded=[
            Claim(text="c1", type=EvidenceType.TOOL_MATCH),
            Claim(text="c2", type=EvidenceType.SPECIFIC_DATA),
        ],
        ungrounded=[Claim(text="c3", type=EvidenceType.INFERENCE)],
        complementary=[Claim(text="c4", type=EvidenceType.COMPLEMENTARY_FINDING)],
        contradicted=[Claim(text="c5", type=EvidenceType.INFERENCE)],
    )
    s = gsar_score(partition, contradiction_penalty=0.5)
    d = decide(s)

    print(f"S = {s:.4f}  (paper Appendix E: ≈0.757)")
    print(f"δ(S) = {d.value}  (paper Appendix E under reference thresholds)")
    print()
    print("Score breakdown:")
    print(f"  W(G) + W(K) = numerator = 1.00 + 0.95 + 0.85 = 2.80")
    print(f"  W(U) + ρ·W(X) = 0.60 + 0.5·0.60 = 0.90")
    print(f"  S = 2.80 / (2.80 + 0.90) = 2.80 / 3.70 = {2.80 / 3.70:.4f}")


# =============================================================================
# Part 3: Threshold sensitivity — what changes when you re-calibrate
# =============================================================================


def example_threshold_sensitivity() -> None:
    """Show how decision boundaries shift with custom thresholds."""
    print("\n=== Part 3: Threshold sensitivity ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, why might production tighten GSAR thresholds vs research defaults?')}"
    )

    base = Partition(
        grounded=[Claim(text="g", type=EvidenceType.TOOL_MATCH)],
        ungrounded=[Claim(text="u", type=EvidenceType.INFERENCE)],
    )
    s = gsar_score(base)
    print(f"Score: {s:.4f}\n")

    profiles = {
        "default (0.80 / 0.65)": GSARThresholds(),
        "lenient (0.70 / 0.50)": GSARThresholds(proceed=0.70, regenerate=0.50),
        "strict (0.95 / 0.85)": GSARThresholds(proceed=0.95, regenerate=0.85),
    }
    for name, th in profiles.items():
        print(f"  {name:30s} → δ = {decide(s, thresholds=th).value}")


# =============================================================================
# Part 4: The full outer loop (Algorithm 1) — with a live judge if available
# =============================================================================


async def example_outer_loop() -> None:
    """Run the bounded replan loop end-to-end against the configured model."""
    print("\n=== Part 4: Algorithm-1 outer loop ===\n")

    from locus.reasoning.gsar_evaluator import GSAREvaluator
    from locus.reasoning.gsar_judge import JudgeOutput, StructuredOutputGSARJudge

    judge = StructuredOutputGSARJudge(model=get_model(max_tokens=2048))

    report = (
        "CPU utilisation on db-prod-1 reached 97% at 14:02 UTC. "
        "The request rate dropped to 12 RPS at the same time. "
        "Both observations are consistent with the alert that fired."
    )
    evidence = (
        "[tool=query_metrics row=14:02:01] host=db-prod-1 cpu_pct=97.2\n"
        "[tool=query_metrics row=14:02:01] host=db-prod-1 rps=12.4\n"
        "[signal] alert_id=A-9912 fired_at=14:02:00 metric=cpu_pct severity=high\n"
    )

    async def regen(syn: str, jo: JudgeOutput) -> str:  # pragma: no cover
        return syn  # not exercised on the grounded report

    async def replan(syn: str, ev: str, jo: JudgeOutput) -> tuple[str, str]:
        return syn, ev  # not exercised on the grounded report

    evaluator = GSAREvaluator(judge=judge, regenerate_fn=regen, replan_fn=replan)
    result = await evaluator.evaluate(report_synthesis=report, evidence_corpus=evidence)

    print(f"final_decision: {result.final_decision.value}")
    print(f"final_score:    {result.final_score:.4f}")
    print(f"replans_used:   {result.replans_used}")
    print(f"degraded:       {result.degraded}")
    print()
    print("Trajectory:")
    for entry in result.trajectory:
        print(f"  iter={entry.iteration}  score={entry.score:.4f}  decision={entry.decision.value}")


# =============================================================================
# Main
# =============================================================================


if __name__ == "__main__":
    example_partition_and_weights()
    example_score_and_decision()
    example_threshold_sensitivity()
    asyncio.run(example_outer_loop())
