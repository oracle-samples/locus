# Tutorial 48: Contract-review workflow (parallel review + negotiation loop)

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

## Source

```python
--8<-- "examples/tutorial_48_contract_review.py"
```
