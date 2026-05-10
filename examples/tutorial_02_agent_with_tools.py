# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 02: Agent with Tools

This tutorial covers:
- Defining tools with the @tool decorator
- Giving tools to an agent
- Watching the agent use tools
- Understanding tool execution events

Prerequisites: Tutorial 01 (Basic Agent)
Difficulty: Beginner
"""

import asyncio
from datetime import datetime

# Import shared config
from config import get_model, print_config

from locus.agent import Agent
from locus.tools import tool


# =============================================================================
# Part 1: Defining a Simple Tool
# =============================================================================

# Tools are just Python functions decorated with @tool
# The docstring becomes the tool description for the LLM


@tool
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


@tool
def multiply_numbers(a: int, b: int) -> int:
    """Multiply two numbers together."""
    return a * b


def example_simple_tools():
    """Create and use simple tools — and confirm the model can describe them."""
    print("=== Part 1: Simple Tools ===\n")

    result = add_numbers(5, 3)
    print(f"Direct call: add_numbers(5, 3) = {result}")

    print(f"\nTool name: {add_numbers.name}")
    print(f"Tool description: {add_numbers.description}")
    print(f"Tool parameters: {add_numbers.parameters}")

    import time as _t

    agent = Agent(
        model=get_model(max_tokens=80),
        system_prompt="Reply in one short sentence.",
    )
    t0 = _t.perf_counter()
    desc = agent.run_sync(
        f"In one sentence, when would an LLM agent use a tool called '{add_numbers.name}' "
        f"that {add_numbers.description}?"
    )
    dt = _t.perf_counter() - t0
    print(
        f"  [model call: {dt:.2f}s · "
        f"{desc.metrics.prompt_tokens}→{desc.metrics.completion_tokens} tokens]"
    )
    print(f"  AI commentary: {desc.message.strip()}")
    print()


# =============================================================================
# Part 2: Agent Using Tools
# =============================================================================


def example_agent_with_tools():
    """Give tools to an agent."""
    print("=== Part 2: Agent Using Tools ===\n")

    model = get_model(max_tokens=200)

    # Pass tools to the agent
    agent = Agent(
        model=model,
        tools=[add_numbers, multiply_numbers],
        system_prompt="You are a calculator assistant. Use the provided tools to perform calculations.",
    )

    print(f"Agent has {len(agent.tools)} tools registered")

    # Ask the agent to use a tool
    result = agent.run_sync("What is 15 + 27?")
    print("\nQ: What is 15 + 27?")
    print(f"A: {result.message}")
    print(f"Tool calls made: {result.metrics.tool_calls}")
    print()


# =============================================================================
# Part 3: More Complex Tools
# =============================================================================


@tool
def get_current_time() -> str:
    """Get the current date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def calculate_age(birth_year: int) -> str:
    """Calculate someone's age given their birth year."""
    current_year = datetime.now().year
    age = current_year - birth_year
    return f"A person born in {birth_year} is {age} years old."


@tool
def format_greeting(name: str, formal: bool = False) -> str:
    """Create a greeting for someone.

    Args:
        name: The person's name
        formal: Whether to use formal greeting (default: False)
    """
    if formal:
        return f"Good day, {name}. It is a pleasure to meet you."
    return f"Hey {name}! Nice to meet you!"


def example_complex_tools():
    """Use more complex tools with optional parameters."""
    print("=== Part 3: Complex Tools ===\n")

    model = get_model(max_tokens=200)

    agent = Agent(
        model=model,
        tools=[get_current_time, calculate_age, format_greeting],
        system_prompt="You are a helpful assistant with access to time and greeting tools.",
    )

    # Test different tools
    prompts = [
        "What time is it right now?",
        "How old would someone born in 1990 be?",
        "Give me a formal greeting for Dr. Smith",
    ]

    for prompt in prompts:
        result = agent.run_sync(prompt)
        print(f"Q: {prompt}")
        print(f"A: {result.message}")
        print()


# =============================================================================
# Part 4: Watching Tool Execution Events
# =============================================================================


async def example_tool_events():
    """Watch events as tools are executed."""
    print("=== Part 4: Tool Execution Events ===\n")

    model = get_model(max_tokens=200)

    agent = Agent(
        model=model,
        tools=[add_numbers, multiply_numbers],
        system_prompt="Use tools to calculate. Always use tools for math.",
    )

    print("Q: What is (5 + 3) * 2?\n")
    print("Events:")

    async for event in agent.run("What is (5 + 3) * 2?"):
        event_type = event.event_type

        if event_type == "tool_start":
            print(f"  TOOL_START: {event.tool_name}({event.arguments})")
        elif event_type == "tool_complete":
            print(f"  TOOL_COMPLETE: {event.tool_name} -> {event.result}")
        elif event_type == "think":
            if event.tool_calls:
                print(f"  THINK: Planning to call {len(event.tool_calls)} tool(s)")
        elif event_type == "terminate":
            print(f"  TERMINATE: {event.reason}")
            if event.final_message:
                print(f"\nFinal Answer: {event.final_message}")

    print()


# =============================================================================
# Part 5: Tools That Return Structured Data
# =============================================================================


@tool
def search_products(query: str, max_results: int = 3) -> list[dict]:
    """Search for products in the catalog.

    Args:
        query: Search query
        max_results: Maximum number of results to return
    """
    # In-memory product catalogue. Real apps swap this for a DB query;
    # the tutorial keeps the data inline so the search logic is the
    # whole story.
    products = [
        {"id": 1, "name": "Laptop", "price": 999.99, "category": "electronics", "in_stock": True},
        {
            "id": 2,
            "name": "Headphones",
            "price": 149.99,
            "category": "electronics",
            "in_stock": True,
        },
        {"id": 3, "name": "Mouse", "price": 49.99, "category": "electronics", "in_stock": True},
        {"id": 4, "name": "Keyboard", "price": 79.99, "category": "electronics", "in_stock": False},
        {"id": 5, "name": "Monitor", "price": 299.99, "category": "electronics", "in_stock": True},
        {"id": 6, "name": "Webcam", "price": 89.99, "category": "electronics", "in_stock": True},
        {
            "id": 7,
            "name": "Standing Desk",
            "price": 449.99,
            "category": "furniture",
            "in_stock": True,
        },
        {
            "id": 8,
            "name": "Office Chair",
            "price": 329.99,
            "category": "furniture",
            "in_stock": False,
        },
    ]

    # Real search — match on name OR category, case-insensitive, with
    # in-stock filtering.
    q = query.lower()
    matches = [p for p in products if q in p["name"].lower() or q in p["category"].lower()]
    return matches[:max_results]


@tool
def get_product_details(product_id: int) -> dict:
    """Get detailed information about a specific product."""
    details = {
        1: {
            "id": 1,
            "name": "Laptop",
            "price": 999.99,
            "specs": '16GB RAM, 512GB SSD, 14" 2.8K display',
        },
        2: {
            "id": 2,
            "name": "Headphones",
            "price": 149.99,
            "specs": "Noise-canceling, 40h battery, USB-C",
        },
        3: {
            "id": 3,
            "name": "Mouse",
            "price": 49.99,
            "specs": "Wireless, 16k DPI, programmable buttons",
        },
        4: {"id": 4, "name": "Keyboard", "price": 79.99, "specs": "Mechanical, hot-swappable, RGB"},
        5: {"id": 5, "name": "Monitor", "price": 299.99, "specs": '27" 4K IPS, 144Hz, USB-C 90W'},
        6: {"id": 6, "name": "Webcam", "price": 89.99, "specs": "1080p60, dual mic, auto-framing"},
        7: {
            "id": 7,
            "name": "Standing Desk",
            "price": 449.99,
            "specs": "Sit-stand, 60×30, programmable presets",
        },
        8: {
            "id": 8,
            "name": "Office Chair",
            "price": 329.99,
            "specs": "Lumbar support, adjustable arms",
        },
    }
    return details.get(product_id, {"error": f"Product {product_id} not found"})


def example_structured_tools():
    """Tools that return complex data structures."""
    print("=== Part 5: Structured Data Tools ===\n")

    model = get_model(max_tokens=300)

    agent = Agent(
        model=model,
        tools=[search_products, get_product_details],
        system_prompt="You are a shopping assistant. Help users find products.",
    )

    result = agent.run_sync("Find me some electronics, then tell me about the laptop")
    print("Q: Find me some electronics, then tell me about the laptop")
    print(f"A: {result.message}")
    print(f"\nTool calls made: {result.metrics.tool_calls}")
    print()


# =============================================================================
# Main
# =============================================================================


def main():
    """Run all tutorial parts."""
    print("=" * 60)
    print("Tutorial 02: Agent with Tools")
    print("=" * 60)
    print()

    print_config()
    print()

    example_simple_tools()
    example_agent_with_tools()
    example_complex_tools()
    asyncio.run(example_tool_events())
    example_structured_tools()

    print("=" * 60)
    print("Next: Tutorial 03 - Agent Memory & Checkpointing")
    print("=" * 60)


if __name__ == "__main__":
    main()
