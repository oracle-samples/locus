# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 11: Swarm Multi-Agent

This tutorial covers:
- Creating self-organizing agent swarms
- Shared context for inter-agent communication
- Task queues and dynamic allocation
- Capability-based agent selection

Prerequisites: Tutorial 10 (Advanced Patterns)
Difficulty: Advanced
"""

import asyncio
import time

# Import shared config for model
from config import get_model, print_config

from locus.agent import Agent
from locus.multiagent.swarm import (
    SharedContext,
    Swarm,
    SwarmTask,
    create_swarm,
    create_swarm_agent,
)


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
# Part 1: Creating Swarm Agents
# =============================================================================


def example_create_agents():
    """Create specialized swarm agents."""
    print("=== Part 1: Creating Swarm Agents ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, when is a swarm of small specialised agents a better fit than one generalist agent?')}"
    )

    # Agents have names, capabilities, and system prompts
    researcher = create_swarm_agent(
        name="Researcher",
        capabilities=["research", "analyze", "investigate"],
        system_prompt="You are a research specialist. Find and analyze information.",
    )

    writer = create_swarm_agent(
        name="Writer",
        capabilities=["write", "summarize", "document"],
        system_prompt="You are a writing specialist. Create clear documentation.",
    )

    reviewer = create_swarm_agent(
        name="Reviewer",
        capabilities=["review", "validate", "check"],
        system_prompt="You are a quality reviewer. Verify accuracy and completeness.",
    )

    print("Created agents:")
    for agent in [researcher, writer, reviewer]:
        print(f"  - {agent.name}: capabilities = {agent.capabilities}")
    print()

    return researcher, writer, reviewer


# =============================================================================
# Part 2: Shared Context
# =============================================================================


async def example_shared_context():
    """Demonstrate shared context for inter-agent communication."""
    print("=== Part 2: Shared Context ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, why does a swarm need SharedContext for messages and discoveries?')}"
    )

    context = SharedContext()

    # Agents can add findings
    await context.add_finding(
        key="api_docs",
        value="The API uses REST with JSON responses",
        agent_id="agent_1",
    )

    # Agents can post to the blackboard for others to read
    await context.post_to_blackboard(
        key="need_help",
        message="Need someone to review the authentication section",
        agent_id="agent_1",
    )

    # Agents can record task results
    await context.record_task_result(
        task_id="task_001",
        result="Completed analysis of the codebase structure",
    )

    print("Current context:")
    print(context.get_summary())
    print()


# =============================================================================
# Part 3: Task Queue
# =============================================================================


def example_task_queue():
    """Demonstrate the task queue system."""
    print("=== Part 3: Task Queue ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, why is task-queue routing useful for a heterogeneous swarm?')}"
    )

    swarm = Swarm(name="Research Team")

    # Add tasks with different priorities
    task1 = swarm.add_task("Research the API documentation", priority=5)
    task2 = swarm.add_task("Write a summary report", priority=3)
    task3 = swarm.add_task("Review the findings for accuracy", priority=2)
    task4 = swarm.add_task("Investigate security concerns", priority=10)  # Highest

    print("Task queue (sorted by priority):")
    for task in swarm.task_queue:
        print(f"  [{task.priority}] {task.description} (status: {task.status})")
    print()

    return swarm


# =============================================================================
# Part 4: Capability-Based Assignment
# =============================================================================


def example_capability_matching():
    """Show how agents are matched to tasks based on capabilities."""
    print("=== Part 4: Capability-Based Assignment ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, why is capability-based agent selection better than random round-robin?')}"
    )

    researcher = create_swarm_agent(
        name="Researcher",
        capabilities=["research", "analyze"],
    )

    writer = create_swarm_agent(
        name="Writer",
        capabilities=["write", "document"],
    )

    # ``SwarmTask`` carries a typed capability registry alongside the
    # description: ``required_tags`` are the tags an agent MUST advertise
    # to claim the task (set-membership), and ``preferred_tags`` boost
    # the priority score without being a hard requirement. Tasks that
    # don't declare tags fall through to the legacy substring match
    # against the description, so pre-tag swarms keep working.
    tasks = [
        SwarmTask(
            description="Research the competitor landscape",
            required_tags=["research"],
            preferred_tags=["analyze"],
        ),
        SwarmTask(
            description="Write documentation for the API",
            required_tags=["write", "document"],
        ),
        SwarmTask(description="Analyze the performance data", required_tags=["analyze"]),
        SwarmTask(description="Create a summary document"),  # tagless → substring fallback
    ]

    print("Task-Agent matching:")
    for task in tasks:
        print(f"\n  Task: {task.description}")
        print(f"    required_tags={task.required_tags} preferred_tags={task.preferred_tags}")
        print(f"    Researcher can handle: {researcher.can_handle(task)}")
        print(f"    Writer can handle: {writer.can_handle(task)}")
        print(f"    Researcher priority: {researcher.priority_for_task(task):.2f}")
        print(f"    Writer priority: {writer.priority_for_task(task):.2f}")
    print()


# =============================================================================
# Part 5: Simple Swarm Execution
# =============================================================================


async def example_simple_swarm():
    """Execute a simple swarm — and verify the provider is reachable."""
    print("=== Part 5: Simple Swarm Execution ===\n")
    rationale_prompt = (
        "In one sentence, what does 'simple swarm execution' mean and when is it enough?"
    )
    print(f"AI rationale: {_llm_call(rationale_prompt)}")

    # Create a swarm with mock execution
    swarm = Swarm(name="Demo Swarm")

    # Create agents
    agent1 = create_swarm_agent(
        name="Analyst",
        capabilities=["analyze"],
        system_prompt="You analyze data.",
    )

    agent2 = create_swarm_agent(
        name="Reporter",
        capabilities=["report"],
        system_prompt="You create reports.",
    )

    swarm.add_agent(agent1)
    swarm.add_agent(agent2)

    # Add tasks
    swarm.add_task("Analyze the sales data", priority=5)
    swarm.add_task("Report on the findings", priority=3)

    print(f"Swarm '{swarm.name}' configured:")
    print(f"  Agents: {[a.name for a in swarm.agents]}")
    print(f"  Tasks: {len(swarm.task_queue)}")
    print()

    # Note: Without a model, agents can't actually work
    # This demonstrates the structure
    print("Note: Full execution requires a configured model.")
    print("See Part 6 for execution with a model.")
    print()


# =============================================================================
# Part 6: Full Swarm with Model
# =============================================================================


async def example_full_swarm():
    """Execute a swarm with a real model."""
    print("=== Part 6: Full Swarm with Model ===\n")

    # The swarm asks each agent for a structured
    # `### Findings / ### Analysis / ### Blackboard` response, so we need
    # enough completion budget to leave room for substantive content.
    model = get_model(max_tokens=2000)

    # Create swarm with model
    swarm = create_swarm(
        name="Analysis Team",
        agents=[
            create_swarm_agent(
                name="Researcher",
                capabilities=["research", "investigate", "find"],
                system_prompt="You are a research specialist. Find relevant information.",
            ),
            create_swarm_agent(
                name="Analyst",
                capabilities=["analyze", "evaluate", "assess"],
                system_prompt="You analyze and evaluate findings critically.",
            ),
            create_swarm_agent(
                name="Writer",
                capabilities=["write", "summarize", "document"],
                system_prompt="You write clear, concise summaries.",
            ),
        ],
        model=model,
    )

    # Execute on a task
    print("Executing swarm on: 'Analyze the benefits of async programming'")
    print("This may take a moment...\n")

    result = await swarm.execute(
        initial_task=(
            "Research, analyze, and write a brief summary of the benefits "
            "of async programming in Python."
        ),
        decompose_tasks=True,  # Let the swarm break this into capability-matched subtasks
    )

    print("Swarm completed!")
    print(f"  Success: {result.success}")
    print(f"  Completed tasks: {len(result.completed_tasks)}")
    print(f"  Failed tasks: {len(result.failed_tasks)}")
    print(f"  Duration: {result.duration_ms:.0f}ms")

    if result.completed_tasks:
        print("\nCompleted subtasks:")
        for t in result.completed_tasks[:5]:
            assigned = t.claimed_by or "unassigned"
            print(f"  - [{assigned}] {t.description[:80]}")
            preview = (t.result or "<empty>").strip().splitlines()[0:6]
            for line in preview:
                print(f"      {line[:120]}")
            if not t.result:
                print("      (no .result text — model returned empty)")
    if result.failed_tasks:
        print("\nFailed subtasks:")
        for t in result.failed_tasks[:5]:
            print(f"  - {t.description[:80]} (reason: {t.error or 'no agent matched'})")
    if result.summary:
        print(f"\nSummary:\n{result.summary[:500]}...")
    print()


# =============================================================================
# Part 7: Swarm Patterns
# =============================================================================


def example_swarm_patterns():
    """Common swarm patterns and configurations."""
    print("=== Part 7: Swarm Patterns ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, when is a Specialist Team swarm preferable to a Pipeline swarm?')}"
    )

    print("Pattern 1: Specialist Team")
    print("-" * 40)
    specialist_team = create_swarm(
        name="Specialist Team",
        agents=[
            create_swarm_agent("Frontend Dev", ["frontend", "UI", "React"]),
            create_swarm_agent("Backend Dev", ["backend", "API", "database"]),
            create_swarm_agent("DevOps", ["deploy", "infrastructure", "CI/CD"]),
        ],
    )
    print("  Agents with distinct, non-overlapping capabilities")
    print("  Each task goes to the most qualified agent")
    print()

    print("Pattern 2: Redundant Team")
    print("-" * 40)
    redundant_team = create_swarm(
        name="Redundant Team",
        agents=[
            create_swarm_agent("Analyst A", ["analyze", "research"]),
            create_swarm_agent("Analyst B", ["analyze", "research"]),
            create_swarm_agent("Analyst C", ["analyze", "research"]),
        ],
    )
    print("  Agents with overlapping capabilities")
    print("  Tasks distributed for parallel processing")
    print()

    print("Pattern 3: Pipeline Team")
    print("-" * 40)
    pipeline_team = create_swarm(
        name="Pipeline Team",
        agents=[
            create_swarm_agent("Gatherer", ["gather", "collect", "fetch"]),
            create_swarm_agent("Processor", ["process", "transform", "clean"]),
            create_swarm_agent("Presenter", ["present", "format", "display"]),
        ],
    )
    print("  Agents form a processing pipeline")
    print("  Tasks chain from one agent to the next")
    print()


# =============================================================================
# Main
# =============================================================================


async def main():
    """Run all tutorial parts."""
    print("=" * 60)
    print("Tutorial 11: Swarm Multi-Agent")
    print("=" * 60)
    print()

    print_config()
    print()

    example_create_agents()
    await example_shared_context()
    example_task_queue()
    example_capability_matching()
    await example_simple_swarm()
    await example_full_swarm()
    example_swarm_patterns()

    print("=" * 60)
    print("Next: Tutorial 12 - MCP Integration")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
