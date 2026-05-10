# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 21: SSE Streaming

This tutorial demonstrates Server-Sent Events (SSE) streaming
for real-time web applications.

Topics covered:
1. SSE message format
2. SSEHandler for buffered output
3. AsyncSSEHandler for streaming
4. Event serialization
5. Integration with web frameworks

Run with:
    python examples/tutorial_21_sse_streaming.py
"""

import asyncio
from datetime import UTC, datetime

from locus.core.events import (
    LocusEvent,
    ThinkEvent,
    ToolCompleteEvent,
    ToolStartEvent,
)
from locus.streaming.sse import (
    AsyncSSEHandler,
    SSEHandler,
    SSEMessage,
    create_sse_response_headers,
)


async def main():
    print("=" * 60)
    print("Tutorial 21: SSE Streaming")
    print("=" * 60)

    # =========================================================================
    # Part 1: SSE Message Format
    # =========================================================================
    print("
=== Part 1: SSE Message Format ===
")

    # SSE messages follow a specific wire format
    message = SSEMessage(
        event="thinking",
        data='{"content": "Analyzing the request..."}',
        id="1",
    )

    print("SSE Message components:")
    print(f"  event: {message.event}")
    print(f"  data: {message.data}")
    print(f"  id: {message.id}")

    # Format for HTTP transmission
    wire_format = message.format()
    print("
Wire format:")
    print("-" * 30)
    print(wire_format)
    print("-" * 30)

    # =========================================================================
    # Part 2: Creating SSE Messages
    # =========================================================================
    print("
=== Part 2: Creating SSE Messages ===
")

    # Different types of SSE messages
    messages = [
        SSEMessage(event="start", data='{"session_id": "abc123"}'),
        SSEMessage(event="chunk", data="Hello"),
        SSEMessage(event="chunk", data=" World!"),
        SSEMessage(event="done", data='{"status": "complete"}'),
    ]

    print("Message sequence:")
    for msg in messages:
        print(f"  [{msg.event}] {msg.data}")

    # Multi-line data
    multiline_msg = SSEMessage(
        event="code",
        data="def hello():
    print('Hello!')
    return True",
    )
    print("
Multi-line message format:")
    print(multiline_msg.format())

    # =========================================================================
    # Part 3: SSE Handler (Buffered)
    # =========================================================================
    print("
=== Part 3: SSE Handler (Buffered) ===
")

    # Create handler for collecting events
    handler = SSEHandler(
        include_timestamp=True,
        include_id=True,
        id_prefix="evt_",
    )

    print("Handler config:")
    print(f"  Include timestamp: {handler.include_timestamp}")
    print(f"  Include ID: {handler.include_id}")
    print(f"  ID prefix: {handler.id_prefix}")

    # Simulate events
    events = [
        ThinkEvent(iteration=1, reasoning="Analyzing user request"),
        ToolStartEvent(tool_name="search", tool_call_id="call_001", arguments={"query": "test"}),
        ToolCompleteEvent(tool_name="search", tool_call_id="call_001", result="Found 5 results"),
    ]

    for event in events:
        await handler.on_event(event)

    # Mark complete
    await handler.on_complete()

    print(f"
Buffered messages: {len(handler.get_messages())}")
    print(f"Is complete: {handler.is_complete}")

    # Get all messages
    for msg in handler.get_messages():
        print(f"  [{msg.event}] id={msg.id}")

    # =========================================================================
    # Part 4: Formatted Output
    # =========================================================================
    print("
=== Part 4: Formatted Output ===
")

    # Get all formatted output
    full_output = handler.format_all()
    print("Full SSE output (first 500 chars):")
    print("-" * 40)
    print(full_output[:500] + "..." if len(full_output) > 500 else full_output)
    print("-" * 40)

    # Pop messages (get and clear)
    handler.clear()
    await handler.on_event(ThinkEvent(iteration=1, reasoning="New thought"))
    popped = handler.pop_messages()
    remaining = handler.get_messages()
    print(f"
After pop: got {len(popped)}, remaining {len(remaining)}")

    # =========================================================================
    # Part 5: Error Handling
    # =========================================================================
    print("
=== Part 5: Error Handling ===
")

    handler.clear()

    # Simulate an error
    await handler.on_event(ThinkEvent(iteration=1, reasoning="Starting..."))
    await handler.on_error(ValueError("Something went wrong"))

    print(f"Has error: {handler.has_error}")
    print(f"Is complete: {handler.is_complete}")

    for msg in handler.get_messages():
        print(f"  [{msg.event}] {msg.data[:50]}...")

    # =========================================================================
    # Part 6: Async SSE Handler
    # =========================================================================
    print("
=== Part 6: Async SSE Handler ===
")

    # AsyncSSEHandler uses a queue for streaming
    async_handler = AsyncSSEHandler(
        include_timestamp=True,
        include_id=True,
    )

    # Simulate producer
    async def produce_events():
        """Simulate event production."""
        await async_handler.on_event(ThinkEvent(iteration=1, reasoning="Processing..."))
        await asyncio.sleep(0.1)
        await async_handler.on_event(
            ToolStartEvent(tool_name="analyze", tool_call_id="call_002", arguments={})
        )
        await asyncio.sleep(0.1)
        await async_handler.on_complete()

    # Simulate consumer
    async def consume_events():
        """Consume and print events."""
        count = 0
        async for sse_text in async_handler.stream():
            count += 1
            # Just count in demo, real app would send to client
        return count

    # Run both
    producer = asyncio.create_task(produce_events())
    count = await consume_events()
    await producer

    print(f"Streamed {count} SSE messages")

    # =========================================================================
    # Part 7: HTTP Response Headers
    # =========================================================================
    print("
=== Part 7: HTTP Response Headers ===
")

    headers = create_sse_response_headers()

    print("SSE Response Headers:")
    for name, value in headers.items():
        print(f"  {name}: {value}")

    # =========================================================================
    # Part 8: Custom Event Serialization
    # =========================================================================
    print("
=== Part 8: Custom Serialization ===
")

    def custom_serializer(event: LocusEvent) -> dict:
        """Custom event serializer with minimal data."""
        return {
            "type": event.event_type,
            "time": datetime.now(UTC).isoformat(),
            # Add only essential fields
            "data": getattr(event, "reasoning", None) or getattr(event, "result", None),
        }

    custom_handler = SSEHandler(custom_serializer=custom_serializer)

    await custom_handler.on_event(ThinkEvent(iteration=1, reasoning="Custom serialization"))
    msg = custom_handler.get_messages()[0]

    print("Custom serialized event:")
    print(f"  {msg.data}")

    # =========================================================================
    # Part 9: Web Framework Integration
    # =========================================================================
    print("
=== Part 9: Web Framework Integration ===
")

    print("FastAPI Example:")
    print("-" * 40)
    print("""
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from locus.streaming.sse import AsyncSSEHandler, create_sse_response_headers

app = FastAPI()

@app.get("/stream")
async def stream_events():
    handler = AsyncSSEHandler()

    async def generate():
        # Start agent in background
        task = asyncio.create_task(run_agent(handler))

        # Stream events
        async for sse_text in handler.stream():
            yield sse_text

        await task

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers=create_sse_response_headers(),
    )

async def run_agent(handler):
    # Your agent logic
    await handler.on_event(ThinkEvent(iteration=1, reasoning="Working..."))
    await handler.on_complete()
""")
    print("-" * 40)

    # =========================================================================
    # Part 10: Supported Event Types
    # =========================================================================
    print("
=== Part 10: Supported Event Types ===
")

    supported_events = [
        # Loop events
        ("think", "Agent thinking/reasoning"),
        ("tool_start", "Tool execution started"),
        ("tool_complete", "Tool execution completed"),
        ("reflect", "Self-reflection result"),
        ("grounding", "Grounding evaluation"),
        ("terminate", "Agent terminated"),
        # Model events
        ("model_chunk", "Streaming model output"),
        ("model_complete", "Model generation complete"),
        # Multi-agent events
        ("specialist_start", "Specialist started"),
        ("specialist_complete", "Specialist completed"),
        ("orchestrator_decision", "Orchestrator routing decision"),
        # Hook events
        ("before_invocation", "Before agent invocation"),
        ("after_invocation", "After agent invocation"),
    ]

    print("Event types for SSE streaming:")
    for event_type, description in supported_events:
        print(f"  {event_type}: {description}")

    # =========================================================================
    # Part 11: Best Practices
    # =========================================================================
    print("
=== Part 11: Best Practices ===
")

    print("1. Always set proper SSE headers")
    print("2. Include event IDs for client reconnection")
    print("3. Send 'done' event on completion")
    print("4. Handle errors gracefully with error events")
    print("5. Use async handler for true streaming")
    print("6. Keep event data small (< 65KB)")
    print("7. Implement client-side reconnection logic")
    print("8. Add heartbeat events for long-running ops")

    # Heartbeat example
    heartbeat = SSEMessage(event="heartbeat", data='{"status": "alive"}')
    print(f"
Heartbeat message:
{heartbeat.format()}")

    # =========================================================================
    print("
" + "=" * 60)
    print("Congratulations! You've completed tutorials 13-21.")
    print("=" * 60)
    print()
    print("New tutorials covered:")
    print("  13: Structured Output")
    print("  14: Reasoning Patterns")
    print("  15: Playbooks")
    print("  16: Agent Handoff")
    print("  17: Orchestrator Pattern")
    print("  18: Specialist Agents")
    print("  19: Guardrails & Security")
    print("  20: Checkpoint Backends")
    print("  21: SSE Streaming")


if __name__ == "__main__":
    asyncio.run(main())
