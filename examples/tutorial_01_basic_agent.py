# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 01: Basic Agent - Your First Locus Agent

This tutorial covers:
- Creating an Agent with a model
- Running simple prompts
- Understanding Agent results

Prerequisites:
- Configure model via environment variables (see examples/.env.example)
- Or run with default mock model (no configuration needed)

Difficulty: Beginner
"""

import asyncio

# Import shared config - handles model selection via env vars
from config import get_model, print_config

from locus.agent import Agent


# =============================================================================
# Part 1: Creating an Agent
# =============================================================================


def example_create_agent():
    """Create a basic agent — and immediately prove it talks to the provider."""
    print("=== Part 1: Creating an Agent ===\n")

    model = get_model(max_tokens=40)

    agent = Agent(
        model=model,
        system_prompt="You are a helpful assistant. Be concise.",
    )

    print(f"Agent created with model: {type(model).__name__}")
    print(f"System prompt: {agent.system_prompt[:50]}...")

    import time as _t

    t0 = _t.perf_counter()
    smoke = agent.run_sync("Say 'ready' in one word.")
    dt = _t.perf_counter() - t0
    print(
        f"  [OCI smoke call: {dt:.2f}s · "
        f"{smoke.metrics.prompt_tokens}→{smoke.metrics.completion_tokens} tokens]"
    )
    print(f"  Smoke reply: {smoke.message.strip()}")
    print()

    return agent


# =============================================================================
# Part 2: Running a Simple Prompt (Sync)
# =============================================================================


def example_sync_run():
    """Run agent synchronously."""
    print("=== Part 2: Synchronous Execution ===\n")

    model = get_model(max_tokens=100)

    agent = Agent(
        model=model,
        system_prompt="You are a helpful assistant. Keep responses under 20 words.",
    )

    # run_sync() blocks until completion
    result = agent.run_sync("What is Python?")

    print("Prompt: What is Python?")
    print(f"Response: {result.message}")
    print(f"Success: {result.success}")
    print(f"Stop reason: {result.stop_reason}")
    print()


# =============================================================================
# Part 3: Running a Prompt (Async)
# =============================================================================


async def example_async_run():
    """Run agent asynchronously with streaming events."""
    print("=== Part 3: Async Execution with Events ===\n")

    model = get_model(max_tokens=100)

    agent = Agent(
        model=model,
        system_prompt="You are a helpful assistant. Be brief.",
    )

    print("Prompt: Name 3 programming languages.")
    print("Events:")

    # run() yields events as they happen
    async for event in agent.run("Name 3 programming languages."):
        print(f"  {event.event_type}: ", end="")
        if hasattr(event, "reasoning") and event.reasoning:
            print(f"{event.reasoning[:60]}...")
        elif hasattr(event, "final_message") and event.final_message:
            print(f"Final: {event.final_message[:60]}...")
        else:
            print(f"{event}")

    print()


# =============================================================================
# Part 4: Understanding Agent Results
# =============================================================================


def example_agent_result():
    """Explore the AgentResult structure."""
    print("=== Part 4: Understanding Results ===\n")

    model = get_model(max_tokens=50)

    agent = Agent(
        model=model,
        system_prompt="You are helpful. One sentence answers only.",
    )

    result = agent.run_sync("What is 2 + 2?")

    print("AgentResult fields:")
    print(f"  .message     = {result.message}")
    print(f"  .success     = {result.success}")
    print(f"  .stop_reason = {result.stop_reason}")
    print(f"  .confidence  = {result.confidence}")

    print("\nMetrics:")
    print(f"  .metrics.iterations  = {result.metrics.iterations}")
    print(f"  .metrics.tool_calls  = {result.metrics.tool_calls}")
    print(f"  .metrics.duration_ms = {result.metrics.duration_ms:.0f}")
    print()


# =============================================================================
# Part 5: Multiple Prompts
# =============================================================================


def example_multiple_prompts():
    """Run multiple prompts with the same agent."""
    print("=== Part 5: Multiple Prompts ===\n")

    model = get_model(max_tokens=50)

    agent = Agent(
        model=model,
        system_prompt="You are a math tutor. Answer in one line.",
    )

    prompts = [
        "What is 5 * 5?",
        "What is the square root of 144?",
        "What is 10% of 200?",
    ]

    for prompt in prompts:
        result = agent.run_sync(prompt)
        print(f"Q: {prompt}")
        print(f"A: {result.message}")
        print()


# =============================================================================
# Main
# =============================================================================


def main():
    """Run all tutorial parts."""
    print("=" * 60)
    print("Tutorial 01: Basic Agent")
    print("=" * 60)
    print()

    # Show current configuration
    print_config()
    print()

    example_create_agent()
    example_sync_run()
    asyncio.run(example_async_run())
    example_agent_result()
    example_multiple_prompts()

    print("=" * 60)
    print("Next: Tutorial 02 - Agent with Tools")
    print("=" * 60)


if __name__ == "__main__":
    main()
