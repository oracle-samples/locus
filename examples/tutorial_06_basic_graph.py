"""
Tutorial 06: Introduction to StateGraph

This tutorial covers:
- What is a StateGraph and when to use it
- Creating nodes and edges
- Executing a simple graph
- Understanding state flow

Prerequisites: Tutorial 05 (Agent Hooks)
Difficulty: Intermediate

When to use StateGraph vs Agent:
- Agent: Single LLM with tools, ReAct loop, simple tasks
- StateGraph: Complex workflows, multiple steps, conditional logic,
              human-in-the-loop, multi-agent coordination
"""

import asyncio

from locus.multiagent import END, START, StateGraph


# =============================================================================
# Part 1: Your First Graph
# =============================================================================


async def example_first_graph():
    """Create the simplest possible graph."""
    print("=== Part 1: Your First Graph ===\n")

    # Create a new graph
    graph = StateGraph()

    # Define a node function
    # - Receives: inputs (dict) containing all state
    # - Returns: updates (dict) to merge into state
    async def greet(inputs):
        name = inputs.get("name", "World")
        return {"greeting": f"Hello, {name}!"}

    # Add the node
    graph.add_node("greet", greet)

    # Connect: START -> greet -> END
    graph.add_edge(START, "greet")
    graph.add_edge("greet", END)

    # Execute with initial state
    result = await graph.execute({"name": "Alice"})

    print("Input:   name = 'Alice'")
    print(f"Output:  greeting = '{result.final_state.get('greeting')}'")
    print(f"Success: {result.success}")
    print()


# =============================================================================
# Part 2: Multiple Nodes in Sequence
# =============================================================================


async def example_sequence():
    """Chain multiple nodes together."""
    print("=== Part 2: Sequential Nodes ===\n")

    graph = StateGraph()

    # Step 1: Validate input
    async def validate(inputs):
        text = inputs.get("text", "")
        return {
            "text": text.strip(),
            "is_valid": len(text.strip()) > 0,
        }

    # Step 2: Transform text
    async def transform(inputs):
        text = inputs.get("text", "")
        return {
            "uppercase": text.upper(),
            "word_count": len(text.split()),
        }

    # Step 3: Create summary
    async def summarize(inputs):
        return {
            "summary": f"{inputs.get('word_count')} words, valid={inputs.get('is_valid')}",
        }

    graph.add_node("validate", validate)
    graph.add_node("transform", transform)
    graph.add_node("summarize", summarize)

    # Chain: START -> validate -> transform -> summarize -> END
    graph.add_edge(START, "validate")
    graph.add_edge("validate", "transform")
    graph.add_edge("transform", "summarize")
    graph.add_edge("summarize", END)

    result = await graph.execute({"text": "  hello world  "})

    print("Input:     text = '  hello world  '")
    print(f"Validated: is_valid = {result.final_state.get('is_valid')}")
    print(f"Uppercase: {result.final_state.get('uppercase')}")
    print(f"Summary:   {result.final_state.get('summary')}")
    print()


# =============================================================================
# Part 3: Understanding State Flow
# =============================================================================


async def example_state_flow():
    """See how state accumulates through nodes."""
    print("=== Part 3: State Flow ===\n")

    graph = StateGraph()

    async def step_a(inputs):
        print(f"  Step A receives: {list(inputs.keys())}")
        return {"a_output": "from A", "value": 10}

    async def step_b(inputs):
        print(f"  Step B receives: {list(inputs.keys())}")
        # Can access step A's output
        value = inputs.get("value", 0)
        return {"b_output": "from B", "doubled": value * 2}

    async def step_c(inputs):
        print(f"  Step C receives: {list(inputs.keys())}")
        # Can access both A and B's outputs
        return {"c_output": "from C", "final": inputs.get("doubled", 0) + 5}

    graph.add_node("step_a", step_a)
    graph.add_node("step_b", step_b)
    graph.add_node("step_c", step_c)

    graph.add_edge(START, "step_a")
    graph.add_edge("step_a", "step_b")
    graph.add_edge("step_b", "step_c")
    graph.add_edge("step_c", END)

    print("Executing graph...")
    result = await graph.execute({"initial_data": True})

    print("\nFinal state:")
    for key, value in result.final_state.items():
        if not key.startswith("_"):  # Skip internal keys
            print(f"  {key}: {value}")
    print()


# =============================================================================
# Part 4: Parallel Nodes
# =============================================================================


async def example_parallel():
    """Execute independent nodes in parallel."""
    print("=== Part 4: Parallel Nodes ===\n")

    graph = StateGraph()
    graph.config.parallel = True  # Enable parallel execution

    async def analyze_sentiment(inputs):
        text = inputs.get("text", "")
        # Simulate analysis
        await asyncio.sleep(0.1)
        is_positive = "good" in text.lower() or "great" in text.lower()
        return {"sentiment": "positive" if is_positive else "neutral"}

    async def count_words(inputs):
        text = inputs.get("text", "")
        await asyncio.sleep(0.1)
        return {"word_count": len(text.split())}

    async def detect_language(inputs):
        # Simplified - always returns English
        await asyncio.sleep(0.1)
        return {"language": "en"}

    async def combine_results(inputs):
        return {
            "analysis": {
                "sentiment": inputs.get("sentiment"),
                "words": inputs.get("word_count"),
                "lang": inputs.get("language"),
            }
        }

    graph.add_node("sentiment", analyze_sentiment)
    graph.add_node("words", count_words)
    graph.add_node("language", detect_language)
    graph.add_node("combine", combine_results)

    # Fan-out: START -> [sentiment, words, language]
    graph.add_edge(START, "sentiment")
    graph.add_edge(START, "words")
    graph.add_edge(START, "language")

    # Fan-in: [sentiment, words, language] -> combine
    graph.add_edge("sentiment", "combine")
    graph.add_edge("words", "combine")
    graph.add_edge("language", "combine")

    graph.add_edge("combine", END)

    import time

    start = time.time()
    result = await graph.execute({"text": "This is a great example!"})
    elapsed = (time.time() - start) * 1000

    print("Input: 'This is a great example!'")
    print(f"Analysis: {result.final_state.get('analysis')}")
    print(f"Time: {elapsed:.0f}ms (parallel nodes run concurrently)")
    print()


# =============================================================================
# Part 5: Graph Results and Metadata
# =============================================================================


async def example_results():
    """Explore the GraphResult structure."""
    print("=== Part 5: Graph Results ===\n")

    graph = StateGraph()

    async def process(inputs):
        return {"processed": True, "result": inputs.get("value", 0) * 2}

    graph.add_node("process", process)
    graph.add_edge(START, "process")
    graph.add_edge("process", END)

    result = await graph.execute({"value": 21})

    print("GraphResult fields:")
    print(f"  .success         = {result.success}")
    print(f"  .graph_id        = {result.graph_id}")
    print(f"  .duration_ms     = {result.duration_ms:.1f}")
    print(f"  .iterations      = {result.iterations}")
    print(f"  .execution_order = {result.execution_order}")

    print("\n  .final_state:")
    for k, v in result.final_state.items():
        if not k.startswith("_"):
            print(f"    {k}: {v}")

    print("\n  .node_results:")
    for node_id, node_result in result.node_results.items():
        print(f"    {node_id}: status={node_result.status.value}")
    print()


# =============================================================================
# Main
# =============================================================================


async def main():
    """Run all tutorial parts."""
    print("=" * 60)
    print("Tutorial 06: Introduction to StateGraph")
    print("=" * 60)
    print()

    await example_first_graph()
    await example_sequence()
    await example_state_flow()
    await example_parallel()
    await example_results()

    print("=" * 60)
    print("Next: Tutorial 07 - Conditional Routing")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
