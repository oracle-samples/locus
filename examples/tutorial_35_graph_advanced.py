"""
Tutorial 35: Advanced Graph — RetryPolicy, CachePolicy, Visualization

This tutorial covers:
- RetryPolicy: exponential backoff with jitter per node
- CachePolicy: TTL-based result caching per node
- Deferred nodes: execute at graph exit
- Graph visualization: Mermaid and ASCII diagrams

Prerequisites:
- No model needed for this tutorial

Difficulty: Advanced
"""

import asyncio
import time

from config import get_model

from locus.agent import Agent
from locus.multiagent.graph import (
    END,
    START,
    CachePolicy,
    GraphConfig,
    RetryPolicy,
    StateGraph,
)
from locus.multiagent.visualize import draw_ascii, draw_mermaid


def _llm_call(
    prompt: str, *, system: str = "Reply in one short sentence.", max_tokens: int = 80
) -> str:
    """Helper: real OCI call with timing/token banner — used by every Part."""
    agent = Agent(model=get_model(max_tokens=max_tokens), system_prompt=system)
    t0 = time.perf_counter()
    res = agent.run_sync(prompt)
    dt = time.perf_counter() - t0
    print(
        f"  [OCI call: {dt:.2f}s · {res.metrics.prompt_tokens}→{res.metrics.completion_tokens} tokens]"
    )
    return res.message.strip()


# =============================================================================
# Part 1: RetryPolicy — Exponential Backoff
# =============================================================================


async def example_retry():
    """Node with retry policy retries on failure."""
    print("=== Part 1: RetryPolicy ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, why is exponential backoff with jitter the right retry default?')}"
    )

    attempt = 0

    async def flaky_api(inputs):
        nonlocal attempt
        attempt += 1
        if attempt < 3:
            raise ConnectionError(f"Attempt {attempt}: API unreachable")
        return {"data": "success"}

    graph = StateGraph(config=GraphConfig(parallel=False))
    graph.add_node(
        "api_call",
        flaky_api,
        retry_policy=RetryPolicy(max_attempts=3, initial_interval=0.1, jitter=False),
    )
    graph.add_edge(START, "api_call")
    graph.add_edge("api_call", END)

    result = await graph.execute({})
    print(f"Success: {result.success}")
    print(f"Attempts needed: {attempt}")
    print(f"Result: {result.final_state.get('data')}")


# =============================================================================
# Part 2: CachePolicy — Avoid Re-computation
# =============================================================================


async def example_cache():
    """Cache node results to avoid re-computation."""
    print("\n=== Part 2: CachePolicy ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, when does CachePolicy on a node beat memoising the function yourself?')}"
    )

    call_count = 0

    async def expensive_lookup(inputs):
        nonlocal call_count
        call_count += 1
        return {"result": f"computed_{call_count}"}

    graph = StateGraph(config=GraphConfig(parallel=False))
    graph.add_node(
        "lookup",
        expensive_lookup,
        cache_policy=CachePolicy(ttl_seconds=60),
    )
    graph.add_edge(START, "lookup")
    graph.add_edge("lookup", END)

    # First call — computes
    r1 = await graph.execute({"query": "test"})
    # Second call — cache hit
    r2 = await graph.execute({"query": "test"})

    print(f"Call count: {call_count}")  # 1 — second was cached
    print(f"Both same result: {r1.final_state.get('result') == r2.final_state.get('result')}")


# =============================================================================
# Part 3: Graph Visualization
# =============================================================================


async def example_visualization():
    """Generate Mermaid and ASCII diagrams."""
    print("\n=== Part 3: Visualization ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, why are Mermaid diagrams useful when reviewing a Locus StateGraph?')}"
    )

    graph = StateGraph(config=GraphConfig(parallel=False))

    async def validate(i):
        return {"valid": True}

    async def process(i):
        return {"processed": True}

    async def notify(i):
        return {"done": True}

    graph.add_node("validate", validate)
    graph.add_node("process", process)
    graph.add_node("notify", notify)
    graph.add_edge(START, "validate")
    graph.add_edge("validate", "process")
    graph.add_conditional_edges(
        "process",
        lambda s: "notify" if s.get("valid") else "__END__",
        {
            "notify": "notify",
            "__END__": "__END__",
        },
    )
    graph.add_edge("notify", END)

    print("Mermaid (paste into https://mermaid.live):")
    print(draw_mermaid(graph))
    print(f"\nASCII:")
    print(draw_ascii(graph))


async def example_realtime_streaming():
    """Stream node events in real time + push custom progress events."""
    print("\n=== Part 4: Real-time streaming with emit_custom ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, why is streaming progress events better than polling for graph status?')}"
    )
    from locus.multiagent import StreamMode, emit_custom

    graph = StateGraph(config=GraphConfig(parallel=False))

    async def slow_node(inputs):
        for i in range(3):
            await emit_custom({"step": i + 1, "of": 3}, node_id="slow_node")
            await asyncio.sleep(0.05)
        return {"done": True}

    graph.add_node("slow_node", slow_node)
    graph.add_edge(START, "slow_node")
    graph.add_edge("slow_node", END)

    seen_custom = 0
    seen_updates = 0
    async for event in graph.stream({}, mode=StreamMode.UPDATES):
        if event.mode == StreamMode.CUSTOM:
            seen_custom += 1
            print(f"  [CUSTOM]  {event.data}")
        else:
            seen_updates += 1
            print(f"  [UPDATE]  {event.node_id}: {event.data}")
    print(f"\nDelivered {seen_custom} custom events + {seen_updates} updates.")


async def example_retry_with_llm() -> None:
    """Wrap a real model call in a node so RetryPolicy guards LLM blips too."""
    print("\n=== Part 5: RetryPolicy + real LLM ===\n")

    async def llm_node(inputs):
        import time as _t

        agent = Agent(
            model=get_model(max_tokens=60),
            system_prompt="Answer in one sentence.",
        )
        t0 = _t.perf_counter()
        result = agent.run_sync(inputs["question"])
        dt = _t.perf_counter() - t0
        print(
            f"  [OCI call: {dt:.2f}s · {result.metrics.prompt_tokens}→{result.metrics.completion_tokens} tokens]"
        )
        return {"answer": result.message.strip()}

    graph = StateGraph(config=GraphConfig(parallel=False))
    graph.add_node(
        "llm",
        llm_node,
        retry_policy=RetryPolicy(max_attempts=2, initial_interval=0.2, jitter=False),
    )
    graph.add_edge(START, "llm")
    graph.add_edge("llm", END)

    result = await graph.execute({"question": "What is OCI Generative AI?"})
    print(f"Answer: {result.final_state.get('answer')}")


if __name__ == "__main__":
    asyncio.run(example_retry())
    asyncio.run(example_cache())
    asyncio.run(example_visualization())
    asyncio.run(example_realtime_streaming())
    asyncio.run(example_retry_with_llm())
