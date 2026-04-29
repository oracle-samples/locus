# Observability

What the agent did, how long each step took, and what it cost — two
built-in hooks plus the standard OpenTelemetry stack do all of it.

## Logging

```python
import logging
from locus.hooks.builtin import StructuredLoggingHook

agent = Agent(
    model=...,
    hooks=[StructuredLoggingHook(level=logging.INFO)],
)
```

Every event (`ToolStartEvent`, `ToolCompleteEvent`, `ReflectEvent`,
`TerminateEvent`) is emitted as a structured JSON line:

```json
{"ts": "2026-04-27T20:31:02Z", "thread_id": "th-001",
 "agent": "procurement", "event": "tool_complete",
 "tool": "search_vendors", "elapsed_ms": 412, "result_size": 2148}
```

Pipe to your log aggregator of choice — locus does not own the
transport.

## Metrics + traces

```python
from locus.hooks.builtin import TelemetryHook

agent = Agent(
    model=...,
    hooks=[TelemetryHook(service_name="procurement-agent")],
)
```

Emits OpenTelemetry spans for every invocation, every iteration, and
every tool call. Counters: `locus.invocations`, `locus.iterations`,
`locus.tool_calls`, `locus.tool_errors`. Histograms:
`locus.invocation.duration`, `locus.tool_call.duration`.

The exporter target is configured the standard OpenTelemetry way — set
`OTEL_EXPORTER_OTLP_ENDPOINT` (and friends) before the agent starts.
Honeycomb, Tempo, OCI APM, Grafana Cloud — anything that speaks OTLP
works. locus does not lock you into a vendor-hosted backend.

## Cost

Token totals are accumulated by the agent loop and surfaced on the
`AgentResult` returned by `agent.run_sync(...)`:

```python
result = agent.run_sync("Plan Q3 launch.")
print(f"prompt: {result.metrics.prompt_tokens}")
print(f"completion: {result.metrics.completion_tokens}")
print(f"total: {result.metrics.total_tokens}")
```

Multiply by your provider's per-token rate to get a per-run cost.

## Tutorials

- [`tutorial_05_agent_hooks.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_05_agent_hooks.py)
- [`tutorial_27_hooks_advanced.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_27_hooks_advanced.py)

## Source

`src/locus/hooks/builtin/logging.py`, `src/locus/hooks/builtin/telemetry.py`.
