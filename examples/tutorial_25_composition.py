# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 25: Agent Composition — Sequential, Parallel, and Loop Pipelines

This tutorial covers:
- SequentialPipeline: chain agents in order, output feeds next
- ParallelPipeline: run agents concurrently, merge results
- LoopAgent: iterate until a condition is met
- Convenience functions: sequential(), parallel(), loop()

Prerequisites:
- Configure model via environment variables (see examples/.env.example)

Difficulty: Intermediate
"""

import asyncio

from config import get_model

from locus.agent import (
    Agent,
    AgentConfig,
    LoopAgent,
    ParallelPipeline,
    SequentialPipeline,
)


# =============================================================================
# Part 1: Sequential Pipeline — Researcher → Writer
# =============================================================================


async def example_sequential():
    """Chain agents so each one's output feeds the next."""
    print("=== Part 1: Sequential Pipeline ===\n")

    model = get_model()

    researcher = Agent(
        config=AgentConfig(
            system_prompt="You are a researcher. Provide 3 key facts about the topic.",
            max_iterations=3,
            model=model,
        )
    )
    writer = Agent(
        config=AgentConfig(
            system_prompt="You are a writer. Take the research and write a short paragraph.",
            max_iterations=3,
            model=model,
        )
    )

    pipeline = SequentialPipeline(agents=[researcher, writer])
    result = await pipeline.run("Benefits of regular exercise")

    print(f"Stage 1 (Researcher): {result.outputs[0][:100]}...")
    print(f"Stage 2 (Writer): {result.outputs[1][:100]}...")
    print(f"Duration: {result.duration_ms:.0f}ms")


# =============================================================================
# Part 2: Parallel Pipeline — Multiple perspectives
# =============================================================================


async def example_parallel():
    """Run agents concurrently and merge their results."""
    print("\n=== Part 2: Parallel Pipeline ===\n")

    model = get_model()

    pros = Agent(
        config=AgentConfig(
            system_prompt="List 2 pros of the topic. Be concise.",
            max_iterations=3,
            model=model,
        )
    )
    cons = Agent(
        config=AgentConfig(
            system_prompt="List 2 cons of the topic. Be concise.",
            max_iterations=3,
            model=model,
        )
    )

    pipeline = ParallelPipeline(agents=[pros, cons])
    result = await pipeline.run("Remote work for engineers")

    print(f"Pros: {result.outputs[0][:100]}...")
    print(f"Cons: {result.outputs[1][:100]}...")
    print(f"Merged: {result.final_output[:150]}...")


# =============================================================================
# Part 3: Loop Agent — Iterate until done
# =============================================================================


async def example_loop():
    """Run an agent in a loop until a condition is met."""
    print("\n=== Part 3: Loop Agent ===\n")

    model = get_model()

    improver = Agent(
        config=AgentConfig(
            system_prompt=(
                "You improve text quality. When the text is good enough, "
                "include the word APPROVED at the end."
            ),
            max_iterations=3,
            model=model,
        )
    )

    loop = LoopAgent(
        agent=improver,
        condition=lambda output: "APPROVED" in output.upper(),
        max_loops=3,
        loop_prompt="Improve this text. Say APPROVED when done:\n{previous_output}",
    )

    result = await loop.run("The quick brown fox jumps over the lazy dog.")
    print(f"Iterations: {len(result.outputs)}")
    print(f"Final: {result.final_output[:100]}...")


# =============================================================================
# Run all examples
# =============================================================================


if __name__ == "__main__":
    asyncio.run(example_sequential())
    asyncio.run(example_parallel())
    asyncio.run(example_loop())
