# Tutorial 47: Procurement approval with tiered human gates

Real procurement workflows have a *threshold-based escalation chain*:

    Request submitted
       │
       ▼
    Justifier  (drafts business justification)
       │
       ▼
    Vendor analyst  (validates vendor + pricing)
       │
       ▼
    Tier router   ── < $1k     ──> auto-approve
                  ── $1k-$10k  ──> manager approval (interrupt)
                  ── $10k-$100k──> manager + finance approval (two interrupts)
                  ── > $100k   ──> manager + finance + CFO approval (three interrupts)
       │
       ▼
    PO generator  (emits structured PurchaseOrder)

Each approval gate is a separate ``interrupt()`` so a real reviewer
can come back to it later. The workflow ends with a typed
``PurchaseOrder`` Pydantic model that can be filed straight into
an ERP without parsing.

Differentiated Locus pieces:

* The tier router is a plain conditional edge — no DSL, no policy file.
* Each gate is *its own node* — easy to add a fourth tier, easy to
  re-order, easy to swap out the human gate for an automated rule.
* ``output_schema=PurchaseOrder`` keeps the workflow's terminal
  artifact typed end-to-end.

Run::

    python examples/tutorial_47_procurement_approval.py

Difficulty: Advanced
Prerequisites: tutorial_45 (HITL multi-agent)

## Source

```python
--8<-- "examples/tutorial_47_procurement_approval.py"
```
