# Observability

What the agent did, how long each step took, and what it cost — three
hooks and the standard OpenTelemetry stack do all of it.

## Logging

```python
from locus.hooks.builtin import StructuredLoggingHook

agent = Agent(
    model=...,
    hooks=[StructuredLoggingHook(level="INFO")],
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
    hooks=[TelemetryHook(otel_exporter="grpc://otel-collector:4317")],
)
```

Emits OpenTelemetry spans for every iteration, every tool call, and
every model call. Counters: `agent.iterations`, `agent.tool_calls`,
`agent.tokens.{prompt,completion}`. Histograms: `agent.tool.duration`,
`agent.model.ttft`.

The exporter target is up to you — Honeycomb, Tempo, OCI APM, Grafana
Cloud, anything that speaks OTLP. locus does not lock you into a
vendor-hosted backend.

## Cost

`TelemetryHook` records token usage on every model call (input,
completion, and reasoning tokens where the provider exposes them).
Read the totals off the `RunResult` returned by `agent.run_sync(...)`:

```python
result = agent.run_sync("Plan Q3 launch.")
print(f"prompt: {result.token_usage.prompt}")
print(f"completion: {result.token_usage.completion}")
```

Multiply by your provider's per-token rate to get a per-run cost.

## Tutorials

- [`tutorial_05_agent_hooks.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_05_agent_hooks.py)
- [`tutorial_27_hooks_advanced.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_27_hooks_advanced.py)

## Source

`src/locus/hooks/logging.py`, `src/locus/hooks/telemetry.py`.
