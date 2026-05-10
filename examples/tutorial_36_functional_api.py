# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 36: Functional API — @entrypoint and @task Decorators

This tutorial covers:
- @task: define parallelizable units with retry and caching
- @entrypoint: orchestrate tasks with automatic tracking
- TaskResult and EntrypointResult for metadata
- Alternative to StateGraph for imperative workflows

Prerequisites:
- No model needed for this tutorial

Difficulty: Intermediate
"""

import asyncio
import time

from config import get_model

from locus.agent import Agent
from locus.multiagent.functional import entrypoint, task


def _llm_call(
    prompt: str, *, system: str = "Reply in one short sentence.", max_tokens: int = 80
) -> str:
    """Helper: real model call with timing/token banner — used by every Part."""
    agent = Agent(model=get_model(max_tokens=max_tokens), system_prompt=system)
    t0 = time.perf_counter()
    res = agent.run_sync(prompt)
    dt = time.perf_counter() - t0
    print(
        f"  [model call: {dt:.2f}s · {res.metrics.prompt_tokens}→{res.metrics.completion_tokens} tokens]"
    )
    return res.message.strip()


# =============================================================================
# Part 1: Basic Pipeline
# =============================================================================


async def example_basic():
    """Simple task chain with automatic tracking."""
    print("=== Part 1: Basic Pipeline ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, when is the Locus functional API a better choice than StateGraph?')}"
    )

    @task
    async def fetch(url: str) -> dict:
        return {"data": f"fetched from {url}", "status": 200}

    @task
    async def process(data: dict) -> str:
        return f"processed: {data['data']}"

    @entrypoint
    async def pipeline(url: str) -> str:
        data = await fetch(url)
        result = await process(data)
        return result

    result = await pipeline("https://api.example.com/data")
    print(f"Result: {result}")

    # Access metadata
    ep = pipeline.get_result()
    print(f"Tasks executed: {len(ep.tasks)}")
    for t in ep.tasks:
        print(f"  {t.task_name}: {t.duration_ms:.1f}ms")
    print(f"Total: {ep.duration_ms:.1f}ms")


# =============================================================================
# Part 2: Task with Retry
# =============================================================================


async def example_retry():
    """Tasks can retry on failure."""
    print("\n=== Part 2: Task with Retry ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, why does @task(retry_attempts=3) belong on the task and not in caller code?')}"
    )

    attempt = 0

    @task(retry_attempts=3)
    async def unreliable_api(query: str) -> str:
        nonlocal attempt
        attempt += 1
        if attempt < 3:
            raise ConnectionError("API timeout")
        return f"result for: {query}"

    @entrypoint
    async def retry_pipeline() -> str:
        return await unreliable_api("test")

    result = await retry_pipeline()
    print(f"Result: {result}")
    print(f"Attempts needed: {attempt}")


# =============================================================================
# Part 3: Task with Caching
# =============================================================================


async def example_cache():
    """Cache task results for identical arguments."""
    print("\n=== Part 3: Task with Caching ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, when should you turn @task(cache=True) ON for an LLM-heavy pipeline?')}"
    )

    call_count = 0

    @task(cache=True)
    async def expensive_compute(key: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"computed_{call_count}"

    @entrypoint
    async def cache_pipeline() -> tuple:
        r1 = await expensive_compute("same_key")
        r2 = await expensive_compute("same_key")  # Cache hit!
        r3 = await expensive_compute("diff_key")  # Different key
        return (r1, r2, r3)

    r1, r2, r3 = await cache_pipeline()
    print(f"r1={r1}, r2={r2}, r3={r3}")
    print(f"Actual calls: {call_count}")  # 2, not 3


async def example_with_llm():
    """A functional pipeline whose inner task delegates to a real Agent."""
    print("\n=== Part 4: @task with real LLM ===\n")

    @task
    async def fetch_topic(seed: str) -> str:
        return f"Tell me about {seed}."

    @task
    async def think(prompt: str) -> str:
        import time as _t

        agent = Agent(
            model=get_model(max_tokens=80),
            system_prompt="Answer in one factual sentence.",
        )
        t0 = _t.perf_counter()
        result = agent.run_sync(prompt)
        dt = _t.perf_counter() - t0
        print(
            f"  [model call: {dt:.2f}s · {result.metrics.prompt_tokens}→{result.metrics.completion_tokens} tokens]"
        )
        return result.message.strip()

    @entrypoint
    async def pipeline(seed: str) -> str:
        question = await fetch_topic(seed)
        return await think(question)

    answer = await pipeline("Oracle Cloud Infrastructure")
    print(f"Answer: {answer}")


if __name__ == "__main__":
    asyncio.run(example_basic())
    asyncio.run(example_retry())
    asyncio.run(example_cache())
    asyncio.run(example_with_llm())
