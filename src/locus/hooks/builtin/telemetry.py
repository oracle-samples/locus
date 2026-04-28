# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Telemetry hook provider for OpenTelemetry integration."""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from locus.hooks.provider import HookPriority, HookProvider


if TYPE_CHECKING:
    from locus.core.state import AgentState

# Optional OpenTelemetry imports
try:
    from opentelemetry import metrics, trace
    from opentelemetry.trace import Span, Status, StatusCode

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None  # type: ignore[assignment]
    metrics = None  # type: ignore[assignment]
    Span = None  # type: ignore[assignment,misc]
    Status = None  # type: ignore[assignment]
    StatusCode = None  # type: ignore[assignment]


class TelemetryHook(HookProvider):
    """Hook provider for OpenTelemetry tracing and metrics.

    Provides automatic instrumentation for:
    - Trace spans for agent invocations and iterations
    - Trace spans for tool calls
    - Metrics for invocation duration, tool call counts, etc.

    Requires the `telemetry` extra: `pip install locus[telemetry]`

    Example:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor

        # Configure OpenTelemetry
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)

        # Add telemetry hook
        registry.add_provider(TelemetryHook())
    """

    def __init__(
        self,
        service_name: str = "locus-agent",
        tracer_name: str = "locus.hooks.telemetry",
        meter_name: str = "locus.hooks.telemetry",
        record_arguments: bool = False,
        record_results: bool = False,
        priority: int = HookPriority.OBSERVABILITY_MIN + 10,
    ) -> None:
        """Initialize telemetry hook.

        Args:
            service_name: Service name for telemetry
            tracer_name: Name for the OpenTelemetry tracer
            meter_name: Name for the OpenTelemetry meter
            record_arguments: Whether to record tool arguments as span attributes
            record_results: Whether to record tool results as span attributes
            priority: Hook priority (default: early in observability range)

        Raises:
            ImportError: If OpenTelemetry is not installed
        """
        if not OTEL_AVAILABLE:
            msg = "OpenTelemetry is not installed. Install with: pip install locus[telemetry]"
            raise ImportError(msg)

        self._service_name = service_name
        self._tracer = trace.get_tracer(tracer_name)
        self._meter = metrics.get_meter(meter_name)
        self._record_arguments = record_arguments
        self._record_results = record_results
        self._priority = priority

        # Active spans tracking
        self._invocation_span: Span | None = None
        self._iteration_spans: dict[int, Span] = {}
        self._tool_spans: dict[str, tuple[Span, float]] = {}

        # Metrics
        self._invocation_counter = self._meter.create_counter(
            "locus.invocations",
            description="Number of agent invocations",
            unit="1",
        )
        self._invocation_duration = self._meter.create_histogram(
            "locus.invocation.duration",
            description="Duration of agent invocations",
            unit="ms",
        )
        self._iteration_counter = self._meter.create_counter(
            "locus.iterations",
            description="Number of agent iterations",
            unit="1",
        )
        self._tool_call_counter = self._meter.create_counter(
            "locus.tool_calls",
            description="Number of tool calls",
            unit="1",
        )
        self._tool_call_duration = self._meter.create_histogram(
            "locus.tool_call.duration",
            description="Duration of tool calls",
            unit="ms",
        )
        self._tool_error_counter = self._meter.create_counter(
            "locus.tool_errors",
            description="Number of tool call errors",
            unit="1",
        )

    @property
    def priority(self) -> int:
        """Return hook priority."""
        return self._priority

    @property
    def name(self) -> str:
        """Return hook name."""
        return "TelemetryHook"

    @contextmanager
    def _span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[Span, None, None]:
        """Create a span context manager.

        Args:
            name: Span name
            attributes: Span attributes

        Yields:
            The active span
        """
        with self._tracer.start_as_current_span(name, attributes=attributes) as span:
            yield span

    async def on_before_invocation(
        self,
        prompt: str,
        state: AgentState,
    ) -> AgentState:
        """Start invocation span.

        Args:
            prompt: User prompt
            state: Agent state

        Returns:
            Unchanged state
        """
        self._invocation_span = self._tracer.start_span(
            "agent.invocation",
            attributes={
                "locus.run_id": state.run_id,
                "locus.agent_id": state.agent_id or "",
                "locus.prompt_length": len(prompt),
                "locus.max_iterations": state.max_iterations,
                "service.name": self._service_name,
            },
        )
        self._invocation_counter.add(1, {"agent_id": state.agent_id or "default"})
        return state

    async def on_after_invocation(
        self,
        state: AgentState,
        success: bool,
    ) -> None:
        """End invocation span.

        Args:
            state: Final agent state
            success: Whether execution succeeded
        """
        if self._invocation_span:
            duration_ms = (state.updated_at - state.started_at).total_seconds() * 1000

            self._invocation_span.set_attributes(
                {
                    "locus.success": success,
                    "locus.iterations": state.iteration,
                    "locus.confidence": state.confidence,
                    "locus.tool_calls": len(state.tool_executions),
                    "locus.errors": len(state.errors),
                    "locus.duration_ms": duration_ms,
                }
            )

            if success:
                self._invocation_span.set_status(Status(StatusCode.OK))
            else:
                self._invocation_span.set_status(
                    Status(StatusCode.ERROR, "Agent invocation failed")
                )

            self._invocation_span.end()
            self._invocation_span = None

            # Record duration metric
            self._invocation_duration.record(
                duration_ms,
                {
                    "agent_id": state.agent_id or "default",
                    "success": str(success),
                },
            )

    async def on_before_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Start tool call span.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Unchanged arguments
        """
        span_attrs: dict[str, Any] = {
            "locus.tool_name": tool_name,
        }

        if self._record_arguments:
            # Sanitize arguments for span attributes
            for key, value in arguments.items():
                attr_key = f"locus.tool.arg.{key}"
                try:
                    span_attrs[attr_key] = str(value)[:1000]  # Limit length
                except Exception:  # noqa: BLE001 — arbitrary user values; fall back to placeholder
                    span_attrs[attr_key] = "<non-serializable>"

        span = self._tracer.start_span(f"tool.{tool_name}", attributes=span_attrs)
        self._tool_spans[tool_name] = (span, time.perf_counter())

        self._tool_call_counter.add(1, {"tool_name": tool_name})
        return arguments

    async def on_after_tool_call(
        self,
        tool_name: str,
        result: Any,
        error: str | None,
    ) -> None:
        """End tool call span.

        Args:
            tool_name: Name of the tool
            result: Tool result
            error: Error message if failed
        """
        if tool_name in self._tool_spans:
            span, start_time = self._tool_spans.pop(tool_name)
            duration_ms = (time.perf_counter() - start_time) * 1000

            span.set_attribute("locus.duration_ms", duration_ms)

            if error:
                span.set_status(Status(StatusCode.ERROR, error))
                span.set_attribute("locus.error", error[:1000])
                self._tool_error_counter.add(1, {"tool_name": tool_name})
            else:
                span.set_status(Status(StatusCode.OK))
                if self._record_results and result is not None:
                    result_str = str(result)
                    span.set_attribute("locus.result_preview", result_str[:500])

            span.end()

            self._tool_call_duration.record(
                duration_ms,
                {
                    "tool_name": tool_name,
                    "success": str(error is None),
                },
            )

    async def on_iteration_start(
        self,
        iteration: int,
        state: AgentState,
    ) -> None:
        """Start iteration span.

        Args:
            iteration: Iteration number
            state: Current state
        """
        span = self._tracer.start_span(
            f"agent.iteration.{iteration}",
            attributes={
                "locus.iteration": iteration,
                "locus.confidence": state.confidence,
                "locus.messages": len(state.messages),
            },
        )
        self._iteration_spans[iteration] = span
        self._iteration_counter.add(1, {"agent_id": state.agent_id or "default"})

    async def on_iteration_end(
        self,
        iteration: int,
        state: AgentState,
    ) -> None:
        """End iteration span.

        Args:
            iteration: Iteration number
            state: Current state
        """
        if iteration in self._iteration_spans:
            span = self._iteration_spans.pop(iteration)
            span.set_attributes(
                {
                    "locus.confidence_after": state.confidence,
                    "locus.messages_after": len(state.messages),
                }
            )
            span.set_status(Status(StatusCode.OK))
            span.end()


class NoOpTelemetryHook(HookProvider):
    """No-op telemetry hook for when OpenTelemetry is not available.

    This hook does nothing but can be used as a drop-in replacement
    for TelemetryHook when telemetry is disabled.
    """

    def __init__(self, priority: int = HookPriority.OBSERVABILITY_MIN + 10) -> None:
        """Initialize no-op hook.

        Args:
            priority: Hook priority
        """
        self._priority = priority

    @property
    def priority(self) -> int:
        """Return hook priority."""
        return self._priority

    @property
    def name(self) -> str:
        """Return hook name."""
        return "NoOpTelemetryHook"


def create_telemetry_hook(
    enabled: bool = True,
    **kwargs: Any,
) -> HookProvider:
    """Factory to create a telemetry hook.

    Creates TelemetryHook if enabled and OpenTelemetry is available,
    otherwise creates NoOpTelemetryHook.

    Args:
        enabled: Whether telemetry should be enabled
        **kwargs: Arguments to pass to TelemetryHook

    Returns:
        TelemetryHook or NoOpTelemetryHook
    """
    if not enabled:
        return NoOpTelemetryHook()

    if not OTEL_AVAILABLE:
        import logging

        logging.getLogger(__name__).warning(
            "OpenTelemetry not available, using no-op telemetry hook"
        )
        return NoOpTelemetryHook()

    return TelemetryHook(**kwargs)
