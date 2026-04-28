# Playbooks

A playbook is a declarative plan: numbered steps, each with a
condition, a tool, and an expected outcome. The agent has to follow
them — a `PlaybookEnforcer` checks step-by-step that the agent did
what the step prescribed.

```yaml
# refund.yaml
name: refund-flow
description: Issue a refund only after verifying the customer and order.

steps:
  - id: verify_customer
    action: lookup_customer
    args: { customer_id: "{{ ctx.customer_id }}" }
    expect: "customer.status == 'active'"

  - id: verify_order
    action: lookup_order
    args: { order_id: "{{ ctx.order_id }}" }
    expect: "order.customer_id == ctx.customer_id"

  - id: issue_refund
    action: refund
    args: { order_id: "{{ ctx.order_id }}", amount: "{{ ctx.amount }}" }
    requires: ["verify_customer", "verify_order"]
```

```python
from locus.playbooks import Playbook, PlaybookEnforcer

playbook = Playbook.from_file("refund.yaml")
agent = Agent(
    model=...,
    tools=[lookup_customer, lookup_order, refund],
    enforcer=PlaybookEnforcer(playbook),
)
```

The enforcer rejects out-of-order or missing steps. The agent can
still phrase its turns in natural language, but the *side-effects*
follow the playbook.

## Why this shape

- **Auditability.** Every refund follows the same sequence; the audit
  trail is the playbook execution log.
- **Compliance.** "We always check identity before issuing money" —
  the enforcer makes that mechanical instead of aspirational.
- **Fewer surprises.** The model can't skip a verification step
  because it was confident.

## YAML or Python

Playbooks load from YAML, JSON, or a Python `Playbook(...)` builder.
YAML is the default; Python is for dynamic playbooks generated at
runtime.

## When to use

- Regulated workflows (KYC, refunds, account changes).
- Multi-step processes where order matters.
- Any step that has a "must precede" relationship to another.

## Tutorial

[`tutorial_15_playbooks.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_15_playbooks.py).

## Source

`src/locus/playbooks/`.
