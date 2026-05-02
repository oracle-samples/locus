# Observability

What the agent did, how long each step took, and what it cost — two
built-in hooks plus the standard OpenTelemetry stack cover every
piece you need. No vendor lock-in: locus emits OTLP, you point it at
whatever backend you run.

## When to wire what

| Need | Add |
|---|---|
| Structured per-event lines for log aggregators (Loki, Splunk, OCI Logging) | `StructuredLoggingHook` |
| OTLP traces and metrics for dashboards (Grafana, Honeycomb, OCI APM) | `TelemetryHook` |
| Per-run token totals on every result | nothing — `AgentResult.metrics` already has it |
| Per-run trace ID surfaced to the user (for support tickets) | telemetry hook + log the active span's trace ID |

## Getting started

### Structured logs

```python
import logging
from locus import Agent
from locus.hooks.builtin import StructuredLoggingHook

agent = Agent(
    model="oci:openai.gpt-5",
    tools=[search, summarise],
    hooks=[StructuredLoggingHook(level=logging.INFO)],
)
```

Every event in the run is emitted as a structured JSON line.
Sample (`ToolCompleteEvent`):

```json
{
  "ts": "2026-05-02T01:31:02Z",
  "thread_id": "th-001",
  "run_id": "run-9c14b1",
  "agent_id": "procurement",
  "event": "tool_complete",
  "tool": "search_vendors",
  "duration_ms": 412,
  "result_size": 2148
}
```

Pipe stdout to your log aggregator. locus doesn't own the transport —
you choose between stdlib `logging`, `structlog`, or
`opentelemetry-logs`.

### Traces and metrics over OTLP

```python
from locus.hooks.builtin import TelemetryHook

agent = Agent(
    model="oci:openai.gpt-5",
    tools=[search, summarise],
    hooks=[
        TelemetryHook(
            service_name="procurement-agent",
            record_arguments=False,    # set True to attach tool args to spans
            record_results=False,      # set True for results (watch PII)
        ),
    ],
)
```

Spans are emitted for every agent invocation, every ReAct iteration,
every tool call, and every model call. Metrics include:

| Counter | What it counts |
|---|---|
| `locus.invocations` | Calls to `agent.run(...)` |
| `locus.iterations` | ReAct iterations across all runs |
| `locus.tool_calls` | Tool invocations |
| `locus.tool_errors` | Tool calls that raised |

| Histogram | What it measures |
|---|---|
| `locus.invocation.duration` | Wall-clock per `agent.run(...)` |
| `locus.tool_call.duration` | Wall-clock per tool body |

Configure the exporter the standard OpenTelemetry way — set
`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_RESOURCE_ATTRIBUTES`, etc.
before constructing the agent. Anything OTLP works: Honeycomb, Tempo,
Grafana Cloud, OCI APM.

Install the optional extra:

```bash
pip install "locus[telemetry]"
```

### Token cost — already on every result

```python
result = agent.run_sync("Plan Q3 launch.")
print(f"prompt:     {result.metrics.prompt_tokens}")
print(f"completion: {result.metrics.completion_tokens}")
print(f"total:      {result.metrics.total_tokens}")
print(f"iterations: {result.metrics.iterations}")
```

Multiply by your provider's per-token rate to get a per-run cost.
For dashboards, key on `agent_id` plus the same metrics the
`TelemetryHook` already emits — no glue code needed.

## PII and tool arguments

`record_arguments=True` and `record_results=True` are off by default
because tool args and results often contain user input — emails,
account numbers, free-text. Turn them on selectively, and only after
you've verified your tracing backend has appropriate retention and
access controls. For PII redaction *inside* the agent before
anything leaves, see [Safety](safety.md).

## Common gotchas

| Symptom | Likely cause |
|---|---|
| `TelemetryHook` raises `ImportError` | `pip install "locus[telemetry]"` to get the OpenTelemetry SDK. |
| No spans show up in your backend | Exporter not configured. Set `OTEL_EXPORTER_OTLP_ENDPOINT` (and `OTEL_EXPORTER_OTLP_HEADERS` if your backend needs auth) *before* creating the agent. |
| Spans land but metrics don't | Some OTLP receivers reject metrics on the trace endpoint. Set `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` separately if needed. |
| Token totals are zero | The provider isn't returning usage in the response (older Ollama builds, some self-hosted endpoints). The locus loop can't make up the numbers. |
| Tool args land in your logs unintentionally | Either `record_arguments=True` or your structured logger is dumping the full event dict. Configure either explicitly. |

## Source and tutorials

- [`tutorial_05_agent_hooks.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_05_agent_hooks.py) — first hook, including logging.
- [`tutorial_27_hooks_advanced.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_27_hooks_advanced.py) — telemetry pipelines.
- [`locus.hooks.builtin.logging`](https://github.com/oracle-samples/locus/blob/main/src/locus/hooks/builtin/logging.py) — `LoggingHook`, `StructuredLoggingHook`.
- [`locus.hooks.builtin.telemetry`](https://github.com/oracle-samples/locus/blob/main/src/locus/hooks/builtin/telemetry.py) — `TelemetryHook`, `NoOpTelemetryHook`.

## See also

- [Hooks](hooks.md) — both observability hooks plug into the same lifecycle as guardrails / steering / retry.
- [Events](events.md) — what gets emitted before any hook runs.
- [Safety](safety.md) — PII redaction *before* logs leave the box.
