# Safety, guardrails, and steering

Three layers cooperate:

1. **Validation** — reject malformed input at the boundary.
2. **Guardrails** — content-policy / topic-policy checks on prompts
   and outputs.
3. **Steering** — a second model votes on every tool call before it
   fires.

## Guardrails

```python
from locus.hooks.builtin import GuardrailsHook, TopicPolicy

agent = Agent(
    model=...,
    hooks=[
        GuardrailsHook(
            input_policy=TopicPolicy(deny=["legal advice", "medical advice"]),
            output_policy=TopicPolicy(deny_pattern=r"\bSSN\s*\d"),
            pii_redact=True,
        ),
    ],
)
```

`GuardrailsHook` runs on input (before the model sees it) and on
output (before the user sees it). Block, redact, or rewrite — your
call.

Built-in policies:

- `TopicPolicy(allow=…, deny=…)` — semantic topic match against a
  small classifier or a model.
- `RegexPolicy(deny_pattern=…)` — fast deterministic filter.
- `PIIRedaction()` — names, emails, phone, SSN, account numbers,
  credit cards. Replaces with `[REDACTED]` or a stable hash.
- Custom — implement `Policy.check(text) -> Decision`.

## Steering

Steering is *tool-call-time* approval. Before any tool fires, a second
model judges: *"is this consistent with the system prompt and the
user's stated goal?"*

```python
from locus.hooks.builtin.steering import SteeringHook

agent = Agent(
    model=...,
    tools=[search, send_email, transfer],
    hooks=[
        SteeringHook(
            judge_model="oci:openai.gpt-5.5-mini",
            policy="The user came in to ask about flights. Reject any tool call unrelated to flights.",
        ),
    ],
)
```

If the judge votes "no", the call is rejected; the agent sees the
rejection and re-plans. Useful for high-stakes tools (`send_email`,
`transfer`, `delete_*`) where you want a second opinion.

## Validation

Tool argument validation is automatic — the typed function signature
becomes a JSON schema and locus enforces it before the call. Schema
violations are returned to the model as a tool error so it can retry
with corrected args.

## Tutorials

- [`tutorial_19_guardrails_security.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_19_guardrails_security.py)
- [`tutorial_30_guardrails_advanced.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_30_guardrails_advanced.py)
- [`tutorial_33_steering.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_33_steering.py)

## Source

`src/locus/hooks/guardrails.py`, `src/locus/hooks/steering.py`.
