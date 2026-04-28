"""
Tutorial 31: Plugins — Composable Agent Extensions

This tutorial covers:
- Plugin base class: bundle hooks + tools
- @hook decorator: auto-discovery of hook methods
- Callback handler: plain function receives events
- Cancel signal: stop agent from external thread

Prerequisites:
- Configure model via environment variables

Difficulty: Intermediate
"""

import threading
import time

from config import get_model

from locus.agent import Agent, AgentConfig
from locus.hooks.plugin import Plugin, hook
from locus.tools.decorator import tool


# =============================================================================
# Part 1: Create a Plugin
# =============================================================================


def example_plugin():
    """Bundle hooks into a reusable plugin."""
    print("=== Part 1: Plugin System ===\n")

    model = get_model()

    class AuditPlugin(Plugin):
        """Tracks all model and tool calls."""

        name = "audit"

        def __init__(self):
            self.log = []

        @hook
        async def on_before_model_call(self, event):
            self.log.append(f"model: {len(event.messages)} msgs")

        @hook
        async def on_before_tool_call(self, event):
            self.log.append(f"tool: {event.tool_name}")

    @tool
    def search(query: str) -> str:
        """Search for information."""
        return f"Results for: {query}"

    plugin = AuditPlugin()
    agent = Agent(
        config=AgentConfig(
            system_prompt="Use the search tool to answer questions.",
            max_iterations=5,
            model=model,
            tools=[search],
            plugins=[plugin],
        )
    )

    result = agent.run_sync("Search for Python best practices")
    print(f"Response: {result.message[:100]}...")
    print(f"Audit log: {plugin.log}")


# =============================================================================
# Part 2: Callback Handler
# =============================================================================


def example_callback():
    """Receive events with a plain function."""
    print("\n=== Part 2: Callback Handler ===\n")

    model = get_model()
    events = []

    agent = Agent(
        config=AgentConfig(
            system_prompt="Answer concisely.",
            max_iterations=3,
            model=model,
            callback_handler=lambda e: events.append(e.event_type),
        )
    )

    agent.run_sync("What is 2+2?")
    print(f"Events received: {events}")


# =============================================================================
# Part 3: Cancel Signal
# =============================================================================


def example_cancel():
    """Stop an agent from another thread."""
    print("\n=== Part 3: Cancel Signal ===\n")

    model = get_model()

    agent = Agent(
        config=AgentConfig(
            system_prompt="Answer concisely.",
            max_iterations=3,
            model=model,
        )
    )

    # Cancel before running
    agent.cancel()
    result = agent.run_sync("This should be cancelled")
    print(f"Stop reason: {result.stop_reason}")  # "cancelled"


if __name__ == "__main__":
    example_plugin()
    example_callback()
    example_cancel()
