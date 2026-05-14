# Tutorial 59: emergent routing — the opt-in LLM protocol picker

[Tutorial 51](tutorial_51_cognitive_router.md) covers the default
deterministic router: the LLM fills a typed `GoalFrame`, then
`_rank_key` picks a protocol via a four-element tuple comparison.

This tutorial covers the **opt-in second mode**: a
`LLMProtocolPicker` that delegates the last-mile pick to the model
when more than one protocol survives the filter.

## When to reach for it

The rule-based ranker is the right default — it's reproducible,
auditable, and free of model latency. Use the emergent picker when:

- You have **custom protocols** registered alongside the built-ins
  and the cost/complexity heuristic doesn't capture their actual
  fit.
- You want the model's **rationale** captured as part of the
  audit trail (it lands on the `router.protocol.selected` event's
  `rationale` field).
- The frame's `primary_goal` is one where multiple protocols qualify
  (e.g. `COMPARE` → both `specialist_fanout` and `debate`) and the
  pick depends on something the frame alone doesn't encode.

## What stays rule-based

The picker is **strictly limited to disambiguation**. The compiler
still:

1. **Filters candidates** by `handles`, `risk_max`, and
   `requires_capabilities` before the picker sees anything.
2. **Short-circuits** when only one candidate survives — no LLM call
   at all (saves a token).
3. **Falls back** to `_rank_key` if the picker raises or returns an
   unknown id; emits a `router.protocol.picker_fallback` event so the
   degradation is observable.
4. **Runs PolicyGate** after the pick — same risk/approval gating
   regardless of which mode chose the protocol.

## Setup

```bash
export OCI_PROFILE=<your-profile>
export OCI_REGION=us-chicago-1
export OCI_COMPARTMENT=ocid1.compartment.oc1..…
```

## Run

```bash
python examples/tutorial_59_emergent_routing.py
```

You'll see five prompts dispatched through both routers side-by-side.
Rows marked `≠` are where the two modes disagreed — the picker's
rationale (on the SSE event) explains why.

## See also

- [Tutorial 51 — cognitive router (default rule-based path)](tutorial_51_cognitive_router.md)
- [Concepts: cognitive router](../concepts/router.md) — the
  filter-then-pick invariant + observability schema
- [Tutorial 17 — orchestrator pattern](tutorial_17_orchestrator_pattern.md)
  — for emergent coordination *inside* a protocol

## Source

```python
--8<-- "examples/tutorial_59_emergent_routing.py"
```
