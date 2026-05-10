# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 10: Advanced Patterns

This tutorial covers:
- Command primitive for routing control
- Send for map-reduce patterns
- Subgraph composition
- Cross-thread Store
- Combining patterns

Prerequisites: Tutorial 09 (Human-in-the-Loop)
Difficulty: Advanced
"""

import asyncio
import time

from config import get_model

from locus.agent import Agent
from locus.core import Command, broadcast, end, goto, scatter
from locus.memory import InMemoryStore
from locus.multiagent import END, START, StateGraph


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
# Part 1: Command Primitive
# =============================================================================


async def example_command_routing():
    """Use Command for dynamic routing decisions."""
    print("=== Part 1: Command Routing ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, why is Locus Command better than separate edges + state writes?')}"
    )

    graph = StateGraph()

    async def classify(inputs):
        request_type = inputs.get("type", "unknown")

        # Command controls both state update AND routing
        if request_type == "urgent":
            return Command(
                update={"priority": "high", "classified": True},
                goto="fast_track",
            )
        elif request_type == "normal":
            return Command(
                update={"priority": "normal", "classified": True},
                goto="standard",
            )
        else:
            return Command(
                update={"priority": "low", "classified": True},
                goto="review",
            )

    async def fast_track(inputs):
        return {"path": "fast_track", "sla": "1 hour"}

    async def standard(inputs):
        return {"path": "standard", "sla": "24 hours"}

    async def review(inputs):
        return {"path": "review", "sla": "48 hours"}

    graph.add_node("classify", classify)
    graph.add_node("fast_track", fast_track)
    graph.add_node("standard", standard)
    graph.add_node("review", review)

    graph.add_edge(START, "classify")
    # No need for explicit edges - Command handles routing
    graph.add_edge("fast_track", END)
    graph.add_edge("standard", END)
    graph.add_edge("review", END)

    for req_type in ["urgent", "normal", "unknown"]:
        result = await graph.execute({"type": req_type})
        print(
            f"{req_type}: path={result.final_state.get('path')}, sla={result.final_state.get('sla')}"
        )
    print()


async def example_goto_helpers():
    """Use goto() and end() helper functions."""
    print("=== Part 1b: goto/end Helpers ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, when is goto() preferable to a Command literal?')}"
    )

    graph = StateGraph()

    async def check_auth(inputs):
        token = inputs.get("token", "")
        if token == "valid":  # noqa: S105 — tutorial literal, not a real secret
            # goto() is shorthand for Command(goto=...)
            return goto("authorized", authenticated=True)
        return goto("denied", authenticated=False)

    async def authorized(inputs):
        # end() routes to END with final state update
        return end(message="Welcome!", access="granted")

    async def denied(inputs):
        return end(message="Access denied", access="none")

    graph.add_node("auth", check_auth)
    graph.add_node("authorized", authorized)
    graph.add_node("denied", denied)

    graph.add_edge(START, "auth")
    graph.add_edge("authorized", END)
    graph.add_edge("denied", END)

    for token in ["valid", "invalid"]:
        result = await graph.execute({"token": token})
        print(f"Token '{token}': {result.final_state.get('message')}")
    print()


# =============================================================================
# Part 2: Send for Map-Reduce
# =============================================================================


async def example_scatter():
    """Fan-out processing with scatter()."""
    print("=== Part 2: scatter() Pattern ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, give an SDK use-case for the scatter() fan-out helper.')}"
    )

    graph = StateGraph()

    async def split_work(inputs):
        items = inputs.get("items", [])
        # scatter sends each item to a worker node
        return scatter("process", items, key="item")

    async def process(inputs):
        item = inputs.get("item", "")
        # Process each item
        return {"processed": item.upper()}

    async def collect(inputs):
        # Collect all send results
        results = []
        for key, value in inputs.items():
            if key.startswith("send_") and isinstance(value, dict):
                results.append(value.get("processed"))
        return {"results": results, "count": len(results)}

    graph.add_node("split", split_work)
    graph.add_node("process", process)
    graph.add_node("collect", collect)

    graph.add_edge(START, "split")
    graph.add_edge("split", "collect")
    graph.add_edge("collect", END)

    result = await graph.execute({"items": ["apple", "banana", "cherry"]})
    print(f"Processed {result.final_state.get('count')} items")
    print(f"Results: {result.final_state.get('results')}")
    print()


async def example_broadcast():
    """Send same data to multiple processors."""
    print("=== Part 2b: broadcast() Pattern ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, when is broadcast() better than scatter() in a graph?')}"
    )

    graph = StateGraph()

    async def prepare(inputs):
        text = inputs.get("text", "")
        # Send same text to multiple analyzers
        return broadcast(["sentiment", "keywords", "length"], {"text": text})

    async def sentiment(inputs):
        text = inputs.get("text", "").lower()
        score = "positive" if "good" in text or "great" in text else "neutral"
        return {"sentiment": score}

    async def keywords(inputs):
        words = inputs.get("text", "").split()
        return {"keywords": words[:3]}

    async def length(inputs):
        return {"length": len(inputs.get("text", ""))}

    async def combine(inputs):
        analysis = {}
        for key in ["sentiment", "keywords", "length"]:
            if key in inputs:
                analysis[key] = inputs[key]
        return {"analysis": analysis}

    graph.add_node("prepare", prepare)
    graph.add_node("sentiment", sentiment)
    graph.add_node("keywords", keywords)
    graph.add_node("length", length)
    graph.add_node("combine", combine)

    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "combine")
    graph.add_edge("combine", END)

    result = await graph.execute({"text": "This is a great example of text analysis"})
    print(f"Analysis: {result.final_state.get('analysis')}")
    print()


# =============================================================================
# Part 3: Subgraph Composition
# =============================================================================


async def example_subgraph():
    """Compose graphs from reusable subgraphs."""
    print("=== Part 3: Subgraph Composition ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, when should you factor a piece of graph logic out as a subgraph?')}"
    )

    # Create a reusable validation subgraph
    validation_graph = StateGraph()

    async def check_required(inputs):
        data = inputs.get("data", {})
        missing = [f for f in ["name", "email"] if f not in data]
        return {"missing_fields": missing, "has_required": len(missing) == 0}

    async def check_format(inputs):
        data = inputs.get("data", {})
        email = data.get("email", "")
        return {"valid_email": "@" in email}

    validation_graph.add_node("required", check_required)
    validation_graph.add_node("format", check_format)
    validation_graph.add_edge(START, "required")
    validation_graph.add_edge("required", "format")
    validation_graph.add_edge("format", END)

    # Main graph uses the subgraph
    main_graph = StateGraph()

    async def prepare_data(inputs):
        return {"data": inputs}

    # Add subgraph as a node!
    main_graph.add_node("prepare", prepare_data)
    main_graph.add_node("validate", validation_graph)  # Subgraph as node

    async def process_result(inputs):
        is_valid = inputs.get("has_required") and inputs.get("valid_email")
        return {"status": "valid" if is_valid else "invalid"}

    main_graph.add_node("result", process_result)

    main_graph.add_edge(START, "prepare")
    main_graph.add_edge("prepare", "validate")
    main_graph.add_edge("validate", "result")
    main_graph.add_edge("result", END)

    # Test with valid data
    result = await main_graph.execute({"name": "Alice", "email": "alice@example.com"})
    print(f"Valid data: status = {result.final_state.get('status')}")

    # Test with invalid data
    result = await main_graph.execute({"name": "Bob"})
    print(f"Missing email: status = {result.final_state.get('status')}")
    print()


# =============================================================================
# Part 4: Cross-Thread Store
# =============================================================================


async def example_store():
    """Use Store for cross-conversation memory."""
    print("=== Part 4: Cross-Thread Store ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, what kind of state belongs in InMemoryStore vs in graph state?')}"
    )

    store = InMemoryStore()
    graph = StateGraph()

    async def greet_user(inputs):
        user_id = inputs.get("user_id")

        # Check if we know this user
        name = await store.get(("users", user_id), "name")

        if name:
            return {"greeting": f"Welcome back, {name}!", "known_user": True}
        return {"greeting": "Hello! What's your name?", "known_user": False}

    async def learn_name(inputs):
        if not inputs.get("known_user"):
            user_id = inputs.get("user_id")
            name = inputs.get("provided_name", "Friend")

            # Store for next time
            await store.put(("users", user_id), "name", name)
            return {"learned": True, "stored_name": name}
        return {"learned": False}

    graph.add_node("greet", greet_user)
    graph.add_node("learn", learn_name)

    graph.add_edge(START, "greet")
    graph.add_edge("greet", "learn")
    graph.add_edge("learn", END)

    # First visit - don't know user
    print("Session 1:")
    result = await graph.execute({"user_id": "user123", "provided_name": "Alice"})
    print(f"  {result.final_state.get('greeting')}")

    # Second visit - remember user
    print("\nSession 2:")
    result = await graph.execute({"user_id": "user123"})
    print(f"  {result.final_state.get('greeting')}")
    print()


# =============================================================================
# Part 5: Combining Patterns
# =============================================================================


async def example_combined():
    """Combine multiple patterns in one workflow."""
    print("=== Part 5: Combined Patterns ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, why is combining Command + scatter + Store typical for multi-tenant order pipelines?')}"
    )

    store = InMemoryStore()
    graph = StateGraph()

    async def classify_order(inputs):
        amount = inputs.get("amount", 0)
        user_id = inputs.get("user_id")

        # Check user's VIP status from store
        is_vip = await store.get(("users", user_id), "vip") or False

        if amount > 1000 or is_vip:
            return Command(
                update={"priority": "high", "vip": is_vip},
                goto="priority_process",
            )
        return Command(
            update={"priority": "normal", "vip": is_vip},
            goto="standard_process",
        )

    async def priority_process(inputs):
        # Send to multiple handlers in parallel
        return scatter("handler", ["verify", "discount", "notify"], key="action")

    async def standard_process(inputs):
        return {"processed": True, "path": "standard"}

    async def handler(inputs):
        action = inputs.get("action", "")
        return {f"{action}_done": True}

    async def finalize(inputs):
        # Store order in user's history
        user_id = inputs.get("user_id")
        await store.put(
            ("users", user_id, "orders"),
            f"order_{inputs.get('amount')}",
            {"amount": inputs.get("amount"), "priority": inputs.get("priority")},
        )
        return {"status": "complete", "priority": inputs.get("priority")}

    graph.add_node("classify", classify_order)
    graph.add_node("priority_process", priority_process)
    graph.add_node("standard_process", standard_process)
    graph.add_node("handler", handler)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "classify")
    graph.add_edge("priority_process", "finalize")
    graph.add_edge("standard_process", "finalize")
    graph.add_edge("finalize", END)

    # Set up a VIP user
    await store.put(("users", "vip_user"), "vip", True)  # noqa: FBT003 — store.put signature is (key, value, is_vip)

    # Regular user, small order
    result = await graph.execute({"user_id": "regular", "amount": 50})
    print(f"Regular user, $50: {result.final_state.get('priority')} priority")

    # Regular user, large order
    result = await graph.execute({"user_id": "regular", "amount": 2000})
    print(f"Regular user, $2000: {result.final_state.get('priority')} priority")

    # VIP user, any order
    result = await graph.execute({"user_id": "vip_user", "amount": 10})
    print(f"VIP user, $10: {result.final_state.get('priority')} priority")
    print()


# =============================================================================
# Part 6: LLM picks the Command target
# =============================================================================


async def example_command_with_llm():
    """An LLM classifies a customer request and the node returns a Command
    with the chosen branch — combining real reasoning with structured
    routing primitives."""
    print("=== Part 6: Command + real LLM ===\n")

    graph = StateGraph()

    async def triage(inputs):
        import time as _t

        message = inputs.get("message", "")
        agent = Agent(
            model=get_model(max_tokens=10),
            system_prompt=(
                "You are a triage classifier. Output one of: refund, ship, escalate. "
                "Reply with just that single word."
            ),
        )
        t0 = _t.perf_counter()
        result = agent.run_sync(message)
        dt = _t.perf_counter() - t0
        print(
            f"  [model call: {dt:.2f}s · {result.metrics.prompt_tokens}→{result.metrics.completion_tokens} tokens]"
        )
        label = result.message.strip().lower()
        if label not in {"refund", "ship", "escalate"}:
            label = "escalate"
        return Command(update={"label": label}, goto=label)

    async def refund(_inputs):
        return {"resolution": "refund queued"}

    async def ship(_inputs):
        return {"resolution": "shipping label generated"}

    async def escalate(_inputs):
        return {"resolution": "escalated to a human agent"}

    graph.add_node("triage", triage)
    graph.add_node("refund", refund)
    graph.add_node("ship", ship)
    graph.add_node("escalate", escalate)
    graph.add_edge(START, "triage")
    graph.add_edge("refund", END)
    graph.add_edge("ship", END)
    graph.add_edge("escalate", END)

    samples = [
        "Charge me back, the package never arrived.",
        "When will my order #482 ship?",
        "I want to speak with a manager about your data policy.",
    ]
    for msg in samples:
        result = await graph.execute({"message": msg})
        print(f"  '{msg[:40]}…' → {result.final_state.get('resolution')}")
    print()


# =============================================================================
# Main
# =============================================================================


async def main():
    """Run all tutorial parts."""
    print("=" * 60)
    print("Tutorial 10: Advanced Patterns")
    print("=" * 60)
    print()

    await example_command_routing()
    await example_goto_helpers()
    await example_scatter()
    await example_broadcast()
    await example_subgraph()
    await example_store()
    await example_combined()
    await example_command_with_llm()

    print("=" * 60)
    print("Next: Tutorial 11 - Swarm Multi-Agent")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
