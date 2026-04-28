# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Unit tests for telemetry hook."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from locus.hooks.builtin.telemetry import (
    OTEL_AVAILABLE,
    NoOpTelemetryHook,
    TelemetryHook,
    create_telemetry_hook,
)
from locus.hooks.provider import HookPriority


class TestNoOpTelemetryHook:
    """Tests for NoOpTelemetryHook."""

    def test_create_with_default_priority(self):
        """Test creating hook with default priority."""
        hook = NoOpTelemetryHook()
        assert hook.priority == HookPriority.OBSERVABILITY_MIN + 10

    def test_create_with_custom_priority(self):
        """Test creating hook with custom priority."""
        hook = NoOpTelemetryHook(priority=100)
        assert hook.priority == 100

    def test_name(self):
        """Test hook name."""
        hook = NoOpTelemetryHook()
        assert hook.name == "NoOpTelemetryHook"


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestTelemetryHook:
    """Tests for TelemetryHook (requires OpenTelemetry)."""

    @pytest.fixture
    def hook(self):
        """Create a telemetry hook."""
        return TelemetryHook(
            service_name="test-service",
            record_arguments=True,
            record_results=True,
        )

    @pytest.fixture
    def mock_state(self):
        """Create a mock agent state."""
        state = MagicMock()
        state.run_id = "test-run-123"
        state.agent_id = "test-agent"
        state.max_iterations = 10
        state.iteration = 3
        state.confidence = 0.85
        state.tool_executions = []
        state.errors = []
        state.messages = []
        state.started_at = datetime.now(UTC)
        state.updated_at = datetime.now(UTC) + timedelta(seconds=5)
        return state

    def test_create_hook(self):
        """Test creating telemetry hook."""
        hook = TelemetryHook()
        assert hook._service_name == "locus-agent"
        assert hook._record_arguments is False
        assert hook._record_results is False

    def test_create_hook_custom(self):
        """Test creating telemetry hook with custom settings."""
        hook = TelemetryHook(
            service_name="custom-service",
            tracer_name="custom.tracer",
            meter_name="custom.meter",
            record_arguments=True,
            record_results=True,
            priority=50,
        )
        assert hook._service_name == "custom-service"
        assert hook._record_arguments is True
        assert hook._record_results is True
        assert hook.priority == 50

    def test_hook_name(self, hook):
        """Test hook name."""
        assert hook.name == "TelemetryHook"

    def test_hook_priority(self, hook):
        """Test hook priority."""
        assert hook.priority == HookPriority.OBSERVABILITY_MIN + 10

    @pytest.mark.asyncio
    async def test_on_before_invocation(self, hook, mock_state):
        """Test on_before_invocation starts span."""
        result = await hook.on_before_invocation("Test prompt", mock_state)

        assert result is mock_state
        assert hook._invocation_span is not None

    @pytest.mark.asyncio
    async def test_on_after_invocation_success(self, hook, mock_state):
        """Test on_after_invocation with success."""
        # Start the span first
        await hook.on_before_invocation("Test prompt", mock_state)

        # End the span
        await hook.on_after_invocation(mock_state, success=True)

        assert hook._invocation_span is None

    @pytest.mark.asyncio
    async def test_on_after_invocation_failure(self, hook, mock_state):
        """Test on_after_invocation with failure."""
        await hook.on_before_invocation("Test prompt", mock_state)
        await hook.on_after_invocation(mock_state, success=False)

        assert hook._invocation_span is None

    @pytest.mark.asyncio
    async def test_on_after_invocation_no_span(self, hook, mock_state):
        """Test on_after_invocation when no span exists."""
        # Call without starting span first
        await hook.on_after_invocation(mock_state, success=True)
        # Should not raise

    @pytest.mark.asyncio
    async def test_on_before_tool_call(self, hook):
        """Test on_before_tool_call starts span."""
        args = {"query": "test", "limit": 10}
        result = await hook.on_before_tool_call("search", args)

        assert result == args
        assert "search" in hook._tool_spans

    @pytest.mark.asyncio
    async def test_on_before_tool_call_no_record_args(self):
        """Test on_before_tool_call without recording arguments."""
        hook = TelemetryHook(record_arguments=False)
        args = {"query": "test"}
        result = await hook.on_before_tool_call("search", args)

        assert result == args
        assert "search" in hook._tool_spans

    @pytest.mark.asyncio
    async def test_on_after_tool_call_success(self, hook):
        """Test on_after_tool_call with success."""
        # Start tool span
        await hook.on_before_tool_call("search", {})

        # End tool span
        await hook.on_after_tool_call("search", result="Found 5 items", error=None)

        assert "search" not in hook._tool_spans

    @pytest.mark.asyncio
    async def test_on_after_tool_call_with_error(self, hook):
        """Test on_after_tool_call with error."""
        await hook.on_before_tool_call("search", {})
        await hook.on_after_tool_call("search", result=None, error="Connection failed")

        assert "search" not in hook._tool_spans

    @pytest.mark.asyncio
    async def test_on_after_tool_call_no_span(self, hook):
        """Test on_after_tool_call when no span exists."""
        # Call without starting span
        await hook.on_after_tool_call("missing_tool", result="data", error=None)
        # Should not raise

    @pytest.mark.asyncio
    async def test_on_after_tool_call_no_record_results(self):
        """Test on_after_tool_call without recording results."""
        hook = TelemetryHook(record_results=False)
        await hook.on_before_tool_call("search", {})
        await hook.on_after_tool_call("search", result="Result data", error=None)

        assert "search" not in hook._tool_spans

    @pytest.mark.asyncio
    async def test_on_iteration_start(self, hook, mock_state):
        """Test on_iteration_start creates span."""
        await hook.on_iteration_start(1, mock_state)

        assert 1 in hook._iteration_spans

    @pytest.mark.asyncio
    async def test_on_iteration_end(self, hook, mock_state):
        """Test on_iteration_end closes span."""
        await hook.on_iteration_start(1, mock_state)
        await hook.on_iteration_end(1, mock_state)

        assert 1 not in hook._iteration_spans

    @pytest.mark.asyncio
    async def test_on_iteration_end_no_span(self, hook, mock_state):
        """Test on_iteration_end when no span exists."""
        # Call without starting span
        await hook.on_iteration_end(999, mock_state)
        # Should not raise

    def test_span_context_manager(self, hook):
        """Test _span context manager."""
        with hook._span("test.span", {"key": "value"}) as span:
            assert span is not None

    @pytest.mark.asyncio
    async def test_tool_call_with_non_serializable_arg(self, hook):
        """Test tool call with non-serializable argument."""

        class NonSerializable:
            def __str__(self):
                raise ValueError("Cannot serialize")

        args = {"obj": NonSerializable()}
        # Should not raise
        result = await hook.on_before_tool_call("test_tool", args)
        assert result == args


class TestCreateTelemetryHook:
    """Tests for create_telemetry_hook factory."""

    def test_create_disabled(self):
        """Test creating disabled telemetry hook."""
        hook = create_telemetry_hook(enabled=False)
        assert isinstance(hook, NoOpTelemetryHook)

    @pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
    def test_create_enabled(self):
        """Test creating enabled telemetry hook."""
        hook = create_telemetry_hook(enabled=True)
        assert isinstance(hook, TelemetryHook)

    @pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
    def test_create_with_kwargs(self):
        """Test creating hook with custom kwargs."""
        hook = create_telemetry_hook(
            enabled=True,
            service_name="custom",
            record_arguments=True,
        )
        assert isinstance(hook, TelemetryHook)
        assert hook._service_name == "custom"
        assert hook._record_arguments is True

    def test_create_otel_not_available(self):
        """Test creating hook when OpenTelemetry is not available."""
        with patch("locus.hooks.builtin.telemetry.OTEL_AVAILABLE", False):
            # Reimport to get patched behavior
            from locus.hooks.builtin import telemetry

            original_otel = telemetry.OTEL_AVAILABLE
            telemetry.OTEL_AVAILABLE = False

            try:
                hook = telemetry.create_telemetry_hook(enabled=True)
                assert isinstance(hook, NoOpTelemetryHook)
            finally:
                telemetry.OTEL_AVAILABLE = original_otel


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestTelemetryHookMetrics:
    """Tests for telemetry hook metrics."""

    @pytest.fixture
    def hook(self):
        """Create telemetry hook."""
        return TelemetryHook()

    def test_metrics_created(self, hook):
        """Test that metrics are created."""
        assert hook._invocation_counter is not None
        assert hook._invocation_duration is not None
        assert hook._iteration_counter is not None
        assert hook._tool_call_counter is not None
        assert hook._tool_call_duration is not None
        assert hook._tool_error_counter is not None


class TestOtelNotAvailable:
    """Tests for when OpenTelemetry is not available."""

    def test_telemetry_hook_raises_import_error(self):
        """Test TelemetryHook raises ImportError when OTEL not available."""
        with patch("locus.hooks.builtin.telemetry.OTEL_AVAILABLE", False):
            from locus.hooks.builtin import telemetry

            original_otel = telemetry.OTEL_AVAILABLE
            telemetry.OTEL_AVAILABLE = False

            try:
                with pytest.raises(ImportError, match="OpenTelemetry is not installed"):
                    telemetry.TelemetryHook()
            finally:
                telemetry.OTEL_AVAILABLE = original_otel
