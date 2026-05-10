# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 17: Orchestrator Pattern

This tutorial demonstrates the orchestrator pattern for coordinating
multiple specialist agents.

Topics covered:
1. Creating specialists with domain focus
2. Building an orchestrator
3. Routing decisions
4. Parallel specialist execution
5. Correlating and summarizing findings

Run with:
    python examples/tutorial_17_orchestrator_pattern.py
"""

import asyncio
import time

from config import get_model, get_model_b, print_config

from locus.agent import Agent
from locus.multiagent import (
    Orchestrator,
    RoutingDecision,
    Specialist,
    create_code_analyst,
    create_log_analyst,
    create_metrics_analyst,
    create_orchestrator,
    create_trace_analyst,
)
from locus.tools.decorator import tool


def _llm_call(
    prompt: str, *, system: str = "Reply in one short sentence.", max_tokens: int = 80
) -> str:
    """Helper: real model call with timing/token banner — used by every Part.
    Uses slot B (a faster model when configured) since the commentary
    calls don't need the heavy specialist model."""
    agent = Agent(model=get_model_b(max_tokens=max_tokens), system_prompt=system)
    t0 = time.perf_counter()
    res = agent.run_sync(prompt)
    dt = time.perf_counter() - t0
    print(
        f"  [model call: {dt:.2f}s · {res.metrics.prompt_tokens}→{res.metrics.completion_tokens} tokens]"
    )
    return res.message.strip()


async def main():
    print("=" * 60)
    print("Tutorial 17: Orchestrator Pattern")
    print("=" * 60)
    print()
    print_config()

    model = get_model()

    # =========================================================================
    # Part 1: Pre-built Specialists
    # =========================================================================
    print("\n=== Part 1: Pre-built Specialists ===\n")

    # Locus provides pre-built specialists for common domains
    log_analyst = create_log_analyst(model=model)
    metrics_analyst = create_metrics_analyst(model=model)
    trace_analyst = create_trace_analyst(model=model)
    code_analyst = create_code_analyst(model=model)

    print("Pre-built Specialists:")
    for specialist in [log_analyst, metrics_analyst, trace_analyst, code_analyst]:
        print(f"  - {specialist.name}")
        print(f"    Type: {specialist.specialist_type}")
        print(f"    Description: {specialist.description[:60]}...")
        print()

    # Run one of them on a tiny task — proves the pre-built specialists hit OCI.
    t0 = time.perf_counter()
    p1 = await log_analyst.execute(task="In one sentence, summarise what a log analyst does.")
    dt = time.perf_counter() - t0
    print(f"  [model call: {dt:.2f}s · log_analyst.execute()]")
    if p1.output:
        print(f"  Output: {p1.output[:160]}")

    # =========================================================================
    # Part 2: Custom Specialists
    # =========================================================================
    print("\n=== Part 2: Custom Specialists ===\n")

    # Create custom tools for the specialist
    @tool(name="check_database", description="Check database health and connections")
    async def check_database() -> str:
        return "Database: 45/50 connections used, avg query time 250ms"

    @tool(name="check_cache", description="Check cache hit rates")
    async def check_cache() -> str:
        return "Cache hit rate: 85%, memory usage: 2.1GB/4GB"

    # Create a custom specialist
    database_specialist = Specialist(
        name="Database Specialist",
        specialist_type="database_analyst",
        description="Analyzes database performance, connections, and queries",
        system_prompt="""You are a database specialist. Your expertise includes:
- Analyzing query performance
- Monitoring connection pools
- Identifying slow queries
- Recommending optimizations

When analyzing, look for connection leaks, slow queries, and lock contention.""",
        tools=[check_database, check_cache],
        max_iterations=5,
        confidence_threshold=0.8,
        model=model,
    )

    print(f"Custom Specialist: {database_specialist.name}")
    print(f"  Tools: {[t.name for t in database_specialist.tools]}")
    print(
        f"AI commentary: {_llm_call('In one sentence, why is a custom Specialist with domain tools better than a generic Agent for DB diagnostics?')}"
    )

    # =========================================================================
    # Part 3: Executing a Specialist
    # =========================================================================
    print("\n=== Part 3: Executing a Specialist ===\n")

    result = await database_specialist.execute(
        task="Analyze current database performance and identify issues",
        context={"incident_id": "INC-12345", "reported_issue": "Slow API responses"},
    )

    print("Specialist Result:")
    print(f"  Success: {result.success}")
    print(f"  Confidence: {result.confidence:.0%}")
    print(f"  Duration: {result.duration_ms:.0f}ms")
    if result.output:
        print(f"  Output: {result.output[:300]}...")

    # =========================================================================
    # Part 4: Creating an Orchestrator
    # =========================================================================
    print("\n=== Part 4: Creating an Orchestrator ===\n")

    # Create orchestrator with specialists
    orchestrator = create_orchestrator(
        name="Incident Analysis Orchestrator",
        specialists=[log_analyst, metrics_analyst, database_specialist],
        model=model,
    )

    print(f"Orchestrator: {orchestrator.name}")
    print("Registered specialists:")
    for spec_id, spec in orchestrator.specialists.items():
        print(f"  - {spec.name} ({spec_id})")
    # AI commentary call dropped — Part 7's full orchestration run
    # exercises the same Orchestrator code path live.

    # =========================================================================
    # Part 5: Orchestrator Configuration
    # =========================================================================
    print("\n=== Part 5: Orchestrator Configuration ===\n")

    # Configure orchestrator behavior. ``max_parallel_specialists``
    # caps the asyncio.Semaphore that bounds the parallel fan-out —
    # the orchestrator runs every routed specialist concurrently
    # behind this gate (per-specialist exception isolation, retry on
    # the empty-completion blip). Drop to 1 if you want the old
    # serialised behaviour (e.g. to debug a flaky specialist).
    orchestrator.max_parallel_specialists = 3
    orchestrator.correlation_threshold = 0.7  # Correlation confidence

    print(f"Max parallel specialists: {orchestrator.max_parallel_specialists}")
    print(f"Correlation threshold: {orchestrator.correlation_threshold}")

    # Custom system prompt for orchestration
    custom_orchestrator = Orchestrator(
        name="Custom Orchestrator",
        description="Orchestrates analysis with custom logic",
        system_prompt="""You coordinate specialist agents for incident analysis.

When routing:
1. For performance issues -> metrics + database specialists
2. For error spikes -> log + trace specialists
3. For unknown issues -> all specialists

Prioritize based on urgency indicated in the task.""",
        model=model,
    )
    custom_orchestrator.register_specialists([log_analyst, metrics_analyst])

    print(f"\nCustom orchestrator with {len(custom_orchestrator.specialists)} specialists")
    # The custom_orchestrator object above is the demo itself — no
    # need for a separate LLM commentary call.

    # =========================================================================
    # Part 6: Routing Decisions
    # =========================================================================
    print("\n=== Part 6: Routing Decisions ===\n")

    # Routing decisions determine which specialists to invoke
    routing = RoutingDecision(
        decision_type="invoke",
        specialists=["log_analyst", "metrics_analyst"],
        reasoning="Performance issue requires log and metrics analysis",
        context={
            "subtasks": {
                "log_analyst": "Search for timeout errors in the last hour",
                "metrics_analyst": "Check CPU and memory trends",
            }
        },
    )

    print("Routing Decision:")
    print(f"  Type: {routing.decision_type}")
    print(f"  Specialists: {routing.specialists}")
    print(f"  Reasoning: {routing.reasoning}")
    print(f"  Subtasks: {routing.context.get('subtasks', {})}")
    # RoutingDecision is a typed object — the field set above is the demo.

    # =========================================================================
    # Part 7: Full Orchestration
    # =========================================================================
    print("\n=== Part 7: Full Orchestration ===\n")

    # Execute the full orchestration workflow
    orch_result = await orchestrator.execute(
        task="API response times have increased from 200ms to 2000ms in the last 30 minutes",
        context={"severity": "high", "affected_services": ["api-gateway", "user-service"]},
    )

    print("Orchestration Result:")
    print(f"  Success: {orch_result.success}")
    print(f"  Duration: {orch_result.duration_ms:.0f}ms")
    # max_parallel_specialists=3 means the three routed specialists
    # ran concurrently behind an asyncio.Semaphore, not back-to-back.
    # With per-specialist budgets averaging ~5s, parallel finishes in
    # ~5s; serial would take ~15s.
    print(f"  Parallel cap: max_parallel_specialists={orchestrator.max_parallel_specialists}")
    print(f"  Decisions made: {len(orch_result.decisions)}")

    for i, decision in enumerate(orch_result.decisions):
        print(f"\n  Decision {i + 1}: {decision.decision_type}")
        if decision.specialists:
            print(f"    Specialists: {decision.specialists}")

    print("\nSpecialist Results:")
    for spec_id, spec_result in orch_result.specialist_results.items():
        status = "OK" if spec_result.success else f"ERROR: {spec_result.error}"
        print(f"  {spec_id}: {status}")
        if spec_result.output:
            print(f"    Output preview: {spec_result.output[:100]}...")

    if orch_result.summary:
        print("\nFinal Summary:")
        print(f"  {orch_result.summary[:500]}...")

    # =========================================================================
    # Part 8: Adding Specialists Dynamically
    # =========================================================================
    print("\n=== Part 8: Dynamic Specialist Registration ===\n")

    # Specialists can be added at runtime
    network_specialist = Specialist(
        name="Network Analyst",
        specialist_type="network_analyst",
        description="Analyzes network connectivity and latency",
        system_prompt="You analyze network issues including DNS, latency, and connectivity.",
        model=model,
    )

    orchestrator.register_specialist(network_specialist)
    print(f"Added specialist: {network_specialist.name}")
    print(f"Total specialists: {len(orchestrator.specialists)}")
    # Run the just-registered specialist on a one-shot task.
    t0 = time.perf_counter()
    p8 = await network_specialist.execute(
        task="In one short sentence, what would you check first if a service had intermittent timeouts?",
    )
    dt = time.perf_counter() - t0
    print(f"  [model call: {dt:.2f}s · network_specialist.execute()]")
    if p8.output:
        print(f"  Output: {p8.output[:160]}")

    # =========================================================================
    # Part 9: Orchestrator Patterns
    # =========================================================================
    print("\n=== Part 9: Common Patterns ===\n")

    print("Pattern 1: Parallel Analysis")
    print("  - Invoke multiple specialists simultaneously")
    print("  - Correlate findings")
    print("  - Produce unified summary")
    print()

    print("Pattern 2: Sequential Refinement")
    print("  - Start with broad analysis")
    print("  - Route to specific specialist based on findings")
    print("  - Iterate until confident")
    print()

    print("Pattern 3: Hierarchical Routing")
    print("  - High-level orchestrator routes to sub-orchestrators")
    print("  - Each sub-orchestrator manages domain specialists")
    print()

    print("Pattern 4: Consensus Analysis")
    print("  - Multiple specialists analyze the same data")
    print("  - Compare and validate findings")
    print("  - Flag disagreements for human review")

    # =========================================================================
    # Part 10: Best Practices
    # =========================================================================
    print("\n=== Part 10: Best Practices ===\n")

    print("1. Give specialists focused, non-overlapping domains")
    print("2. Use clear naming for specialist types")
    print("3. Provide domain-specific system prompts")
    print("4. Set appropriate parallel limits")
    print("5. Include correlation logic in summarization")
    print("6. Handle specialist failures gracefully")
    print("7. Track specialist performance metrics")

    # =========================================================================
    print("\n" + "=" * 60)
    print("Next: Tutorial 18 - Specialist Agents")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
