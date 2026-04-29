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

Locus ships these out of the box:

| Hook | What it does |
|---|---|
| `LoggingHook` / `StructuredLoggingHook` | Plain or JSON-structured logs at every phase |
| `TelemetryHook` / `NoOpTelemetryHook` | OpenTelemetry spans + counters + histograms |
| `ModelRetryHook` | Backoff retries on empty / rate-limited model responses |
| `GuardrailsHook` / `ContentFilterHook` | PII / SQL / XSS / command-injection regex policies |
| `SteeringHook` | LLM-as-judge tool approval (a second model votes before each tool call) |

```python
from locus.hooks.builtin import (
    GuardrailsHook,
    LoggingHook,
    ModelRetryHook,
    SteeringHook,
    TelemetryHook,
)

agent = Agent(
    ...,
    hooks=[
        LoggingHook(),
        ModelRetryHook(max_retries=3),
        GuardrailsHook(),
    ],
)
```
