# Tutorial 39: GSAR — typed grounding for hallucination detection and recovery

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

## Source

```python
--8<-- "examples/tutorial_39_gsar_typed_grounding.py"
```
