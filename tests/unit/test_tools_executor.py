# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Unit tests for tools executor module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from locus.core.messages import ToolCall
from locus.tools.executor import (
    CircuitBreakerExecutor,
    ConcurrentExecutor,
    SequentialExecutor,
    ToolContextFactory,
)


class TestToolContextFactory:
    """Tests for ToolContextFactory."""

    def test_create_factory(self):
        """Test creating a context factory."""
        factory = ToolContextFactory(
            run_id="run123",
            agent_id="agent1",
            iteration=5,
        )
        assert factory.run_id == "run123"
        assert factory.agent_id == "agent1"
        assert factory.iteration == 5

    def test_create_context(self):
        """Test creating a context from factory."""
        factory = ToolContextFactory(
            run_id="run123",
            agent_id="agent1",
            iteration=5,
            state={"key": "value"},
            invocation_metadata={"meta": "data"},
        )

        tool_call = ToolCall(
            id="call1",
            name="test_tool",
            arguments={"arg": "value"},
        )

        ctx = factory.create(tool_call, "test_tool")

        assert ctx.tool_call_id == "call1"
        assert ctx.tool_name == "test_tool"
        assert ctx.agent_id == "agent1"
        assert ctx.run_id == "run123"
        assert ctx.iteration == 5
        assert ctx.state == {"key": "value"}
        assert ctx.invocation_metadata == {"meta": "data"}


class TestSequentialExecutor:
    """Tests for SequentialExecutor."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock tool registry."""
        registry = MagicMock()

        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value="result")

        registry.get = MagicMock(return_value=mock_tool)
        return registry, mock_tool

    @pytest.mark.asyncio
    async def test_execute_single_tool(self, mock_registry):
        """Test executing a single tool."""
        registry, mock_tool = mock_registry
        executor = SequentialExecutor()

        tool_calls = [
            ToolCall(id="call1", name="test_tool", arguments={"arg": "value"}),
        ]

        results = await executor.execute(tool_calls, registry)

        assert len(results) == 1
        assert results[0].tool_call_id == "call1"
        assert results[0].name == "test_tool"
        assert results[0].content == "result"
        assert results[0].error is None

    @pytest.mark.asyncio
    async def test_execute_multiple_tools(self, mock_registry):
        """Test executing multiple tools sequentially."""
        registry, mock_tool = mock_registry
        executor = SequentialExecutor()

        tool_calls = [
            ToolCall(id="call1", name="tool1", arguments={}),
            ToolCall(id="call2", name="tool2", arguments={}),
            ToolCall(id="call3", name="tool3", arguments={}),
        ]

        results = await executor.execute(tool_calls, registry)

        assert len(results) == 3
        assert all(r.error is None for r in results)

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, mock_registry):
        """Test executing unknown tool returns error."""
        registry, mock_tool = mock_registry
        registry.get = MagicMock(return_value=None)

        executor = SequentialExecutor()
        tool_calls = [
            ToolCall(id="call1", name="unknown_tool", arguments={}),
        ]

        results = await executor.execute(tool_calls, registry)

        assert len(results) == 1
        assert results[0].error == "Unknown tool: unknown_tool"
        assert results[0].content == ""

    @pytest.mark.asyncio
    async def test_execute_with_exception(self, mock_registry):
        """Test handling tool execution exception."""
        registry, mock_tool = mock_registry
        mock_tool.execute = AsyncMock(side_effect=ValueError("Tool failed"))

        executor = SequentialExecutor()
        tool_calls = [
            ToolCall(id="call1", name="test_tool", arguments={}),
        ]

        results = await executor.execute(tool_calls, registry)

        assert len(results) == 1
        assert results[0].error == "ValueError: Tool failed"
        assert results[0].content == ""

    @pytest.mark.asyncio
    async def test_execute_with_context_factory(self, mock_registry):
        """Test execution with context factory."""
        registry, mock_tool = mock_registry
        executor = SequentialExecutor()

        factory = ToolContextFactory(run_id="run123", agent_id="agent1")
        tool_calls = [
            ToolCall(id="call1", name="test_tool", arguments={"x": 1}),
        ]

        results = await executor.execute(tool_calls, registry, factory)

        assert len(results) == 1
        # Verify tool was called with context
        mock_tool.execute.assert_called_once()
        call_kwargs = mock_tool.execute.call_args.kwargs
        assert "ctx" in call_kwargs
        assert call_kwargs["ctx"] is not None

    @pytest.mark.asyncio
    async def test_execute_duration_tracking(self, mock_registry):
        """Test that execution tracks duration."""
        registry, mock_tool = mock_registry
        executor = SequentialExecutor()

        tool_calls = [
            ToolCall(id="call1", name="test_tool", arguments={}),
        ]

        results = await executor.execute(tool_calls, registry)

        assert results[0].duration_ms is not None
        assert results[0].duration_ms >= 0


class TestConcurrentExecutor:
    """Tests for ConcurrentExecutor."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock tool registry."""
        registry = MagicMock()

        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value="result")

        registry.get = MagicMock(return_value=mock_tool)
        return registry, mock_tool

    def test_default_concurrency(self):
        """Test default max concurrency."""
        executor = ConcurrentExecutor()
        assert executor.max_concurrency == 10

    def test_custom_concurrency(self):
        """Test custom max concurrency."""
        executor = ConcurrentExecutor(max_concurrency=5)
        assert executor.max_concurrency == 5

    @pytest.mark.asyncio
    async def test_execute_concurrent(self, mock_registry):
        """Test concurrent execution."""
        registry, mock_tool = mock_registry
        executor = ConcurrentExecutor(max_concurrency=3)

        tool_calls = [ToolCall(id=f"call{i}", name="test_tool", arguments={}) for i in range(5)]

        results = await executor.execute(tool_calls, registry)

        assert len(results) == 5
        assert all(r.error is None for r in results)

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, mock_registry):
        """Test executing unknown tool returns error."""
        registry, mock_tool = mock_registry
        registry.get = MagicMock(return_value=None)

        executor = ConcurrentExecutor()
        tool_calls = [
            ToolCall(id="call1", name="unknown", arguments={}),
        ]

        results = await executor.execute(tool_calls, registry)

        assert len(results) == 1
        assert "Unknown tool" in results[0].error

    @pytest.mark.asyncio
    async def test_execute_with_exception(self, mock_registry):
        """Test handling concurrent execution exception."""
        registry, mock_tool = mock_registry
        mock_tool.execute = AsyncMock(side_effect=RuntimeError("Failed"))

        executor = ConcurrentExecutor()
        tool_calls = [
            ToolCall(id="call1", name="test_tool", arguments={}),
        ]

        results = await executor.execute(tool_calls, registry)

        assert results[0].error == "RuntimeError: Failed"


class TestCircuitBreakerExecutor:
    """Tests for CircuitBreakerExecutor."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock tool registry."""
        registry = MagicMock()

        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(return_value="result")

        registry.get = MagicMock(return_value=mock_tool)
        return registry, mock_tool

    def test_default_threshold(self):
        """Test default failure threshold."""
        executor = CircuitBreakerExecutor()
        assert executor.failure_threshold == 3

    def test_custom_threshold(self):
        """Test custom failure threshold."""
        executor = CircuitBreakerExecutor(failure_threshold=5)
        assert executor.failure_threshold == 5

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_registry):
        """Test successful execution."""
        registry, mock_tool = mock_registry
        executor = CircuitBreakerExecutor()

        tool_calls = [
            ToolCall(id="call1", name="test_tool", arguments={}),
        ]

        results = await executor.execute(tool_calls, registry)

        assert len(results) == 1
        assert results[0].error is None

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self, mock_registry):
        """Test circuit opens after consecutive failures."""
        registry, mock_tool = mock_registry
        mock_tool.execute = AsyncMock(side_effect=ValueError("Failed"))

        executor = CircuitBreakerExecutor(failure_threshold=2)

        # First two calls fail but circuit stays closed
        tool_calls = [
            ToolCall(id="call1", name="failing_tool", arguments={}),
        ]
        results = await executor.execute(tool_calls, registry)
        assert results[0].error == "ValueError: Failed"

        results = await executor.execute(tool_calls, registry)
        assert results[0].error == "ValueError: Failed"

        # Third call should be blocked by circuit breaker
        tool_calls = [
            ToolCall(id="call3", name="failing_tool", arguments={}),
        ]
        results = await executor.execute(tool_calls, registry)
        assert "Circuit breaker open" in results[0].error

    @pytest.mark.asyncio
    async def test_reset_circuit(self, mock_registry):
        """Test resetting circuit breaker."""
        registry, mock_tool = mock_registry
        mock_tool.execute = AsyncMock(side_effect=ValueError("Failed"))

        executor = CircuitBreakerExecutor(failure_threshold=1)

        # Fail once to open circuit
        tool_calls = [
            ToolCall(id="call1", name="failing_tool", arguments={}),
        ]
        await executor.execute(tool_calls, registry)

        # Reset the circuit
        executor.reset("failing_tool")

        # Now should be able to call again
        mock_tool.execute = AsyncMock(return_value="success")
        results = await executor.execute(tool_calls, registry)
        assert results[0].content == "success"

    @pytest.mark.asyncio
    async def test_reset_all_circuits(self, mock_registry):
        """Test resetting all circuit breakers."""
        registry, mock_tool = mock_registry
        mock_tool.execute = AsyncMock(side_effect=ValueError("Failed"))

        executor = CircuitBreakerExecutor(failure_threshold=1)

        # Fail to open circuit
        tool_calls = [
            ToolCall(id="call1", name="failing_tool", arguments={}),
        ]
        await executor.execute(tool_calls, registry)

        # Reset all circuits
        executor.reset()

        # Should be able to call again
        mock_tool.execute = AsyncMock(return_value="success")
        results = await executor.execute(tool_calls, registry)
        assert results[0].content == "success"

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self, mock_registry):
        """Test that success resets failure count."""
        registry, mock_tool = mock_registry
        executor = CircuitBreakerExecutor(failure_threshold=2)

        tool_calls = [
            ToolCall(id="call1", name="test_tool", arguments={}),
        ]

        # Fail once
        mock_tool.execute = AsyncMock(side_effect=ValueError("Failed"))
        await executor.execute(tool_calls, registry)

        # Succeed - should reset counter
        mock_tool.execute = AsyncMock(return_value="success")
        await executor.execute(tool_calls, registry)

        # Fail once more - should not open circuit
        mock_tool.execute = AsyncMock(side_effect=ValueError("Failed"))
        await executor.execute(tool_calls, registry)

        # Should still be able to call (not open)
        results = await executor.execute(tool_calls, registry)
        assert results[0].error == "ValueError: Failed"
        assert "Circuit breaker" not in results[0].error
