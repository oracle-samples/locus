# Hooks

Hooks observe and modify agent behavior at lifecycle points. Every
hook inherits `HookProvider` and is registered in a `HookRegistry`.
Events fire at six phases:

1. `on_before_invocation` — before the agent starts
2. `on_after_invocation` — after the agent finishes
3. `on_before_model_call` — before each model request
4. `on_after_model_call` — after each model response
5. `on_before_tool_call` — before each tool runs
6. `on_after_tool_call` — after each tool completes

## Writing a hook

```python
from locus.hooks.provider import HookProvider, HookPriority

class AuditHook(HookProvider):
    name = "audit"
    priority = HookPriority.OBSERVABILITY_MIN

    async def on_before_tool_call(self, event):
        print(f"→ {event.tool_name}({event.arguments})")

    async def on_after_tool_call(self, event):
        print(f"← {event.tool_name} = {event.result}")

agent = Agent(..., hooks=[AuditHook()])
```

## Priorities

Hooks run in priority order (lower number first for `before_*`,
reversed for `after_*` so teardown pairs with setup):

| Range | Intended use |
|---|---|
| 0–99 | Security (guardrails, PII redaction) |
| 100–199 | Observability (logging, telemetry) |
| 200–299 | Business logic |
| 300+ | Cosmetic |

Use the constants in `HookPriority` instead of magic numbers.

## Write-protected events

Event objects are Pydantic models with frozen fields. You cannot
accidentally mutate them from a hook. Methods that exist to let hooks
steer the agent — cancelling a tool, retrying a model call — are
explicit, so the intent is unambiguous.

## Built-in hooks

Locus ships five batteries:

| Hook | What it does |
|---|---|
| `LoggingHook` | Structured logs at every phase |
| `RetryHook` | Exponential backoff on model throttling |
| `GuardrailsHook` | PII detection, SQL/XSS/command-injection checks |
| `SteeringHook` | LLM-powered real-time tool approval |
| `TelemetryHook` | OpenTelemetry spans + metrics |

```python
from locus.hooks.builtin import LoggingHook, GuardrailsHook

agent = Agent(..., hooks=[LoggingHook(), GuardrailsHook()])
```

## See also

- [Tutorial 05 — agent hooks](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_05_agent_hooks.py)
  — the basics, end to end.
- [Tutorial 27 — hooks advanced](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_27_hooks_advanced.py)
  — write-protected events, retry, cancel.
- [Tutorial 31 — plugins](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_31_plugins.py)
  — bundle hooks + tools + lifecycle into a reusable `Plugin`.
- [Retry Strategies](retry.md), [Safety & Guardrails](safety.md),
  [Observability](observability.md) — the user-facing concept pages
  for the built-in hooks.
