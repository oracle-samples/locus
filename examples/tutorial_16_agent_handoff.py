"""
Tutorial 16: Agent Handoff

This tutorial demonstrates agent-to-agent context transfer,
enabling complex workflows where agents delegate and escalate tasks.

Topics covered:
1. Creating handoff-capable agents
2. Context transfer between agents
3. Handoff reasons (escalation, delegation, completion)
4. Chain of custody tracking
5. Handoff manager patterns

Run with:
    python examples/tutorial_16_agent_handoff.py
"""

import asyncio
import time

from config import get_model, get_model_b, print_config

from locus.core.messages import Message
from locus.core.state import AgentState
from locus.multiagent.handoff import (
    HandoffContext,
    HandoffReason,
    create_handoff_agent,
    create_handoff_manager,
)


def _banner(label: str, dt: float, prompt_tok: int = 0, completion_tok: int = 0) -> None:
    """Print a uniform [model call …] banner so each Part proves it hit the model."""
    print(f"  [model call · {label}: {dt:.2f}s · {prompt_tok}→{completion_tok} tokens]")


async def main():
    print("=" * 60)
    print("Tutorial 16: Agent Handoff")
    print("=" * 60)
    print()
    print_config()

    # =========================================================================
    # Part 1: Creating Handoff Agents
    # =========================================================================
    print("\n=== Part 1: Creating Handoff Agents ===\n")

    # Create specialized agents using the convenience function
    triage_agent = create_handoff_agent(
        name="Triage Agent",
        description="Initial assessment and routing of issues",
        system_prompt="You are a triage agent. Assess issues and route to specialists.",
    )

    technical_agent = create_handoff_agent(
        name="Technical Specialist",
        description="Deep technical analysis and debugging",
        system_prompt="You are a technical specialist. Perform detailed analysis.",
    )

    escalation_agent = create_handoff_agent(
        name="Escalation Manager",
        description="Handles critical issues requiring senior attention",
        system_prompt="You are an escalation manager. Handle critical issues.",
    )

    print("Created agents:")
    print(f"  - {triage_agent.name} (id: {triage_agent.id})")
    print(f"  - {technical_agent.name} (id: {technical_agent.id})")
    print(f"  - {escalation_agent.name} (id: {escalation_agent.id})")

    # Configure handoff paths
    triage_agent.can_delegate_to = [technical_agent.id]
    triage_agent.can_escalate_to = [escalation_agent.id]
    technical_agent.can_escalate_to = [escalation_agent.id]

    print("\nHandoff paths:")
    print("  Triage -> Technical (delegation)")
    print("  Triage -> Escalation (escalation)")
    print("  Technical -> Escalation (escalation)")

    # This tutorial fires ~9 handoff round-trips serially, so it's a
    # natural fit for slot B (a faster model) — set "Model B" in the
    # workbench Provider settings to e.g. claude-haiku-4-5 to cut total
    # runtime ~3×. When B is unset, get_model_b() falls back to slot A
    # so behavior is unchanged.
    triage_model = get_model_b(max_tokens=2000)
    model = get_model(max_tokens=2000)
    triage_with_model = triage_agent.with_model(triage_model)
    smoke_ctx = HandoffContext(
        source_agent_id="user",
        target_agent_id=triage_agent.id,
        reason=HandoffReason.SPECIALIZATION,
        original_task="Smoke test the triage agent",
        conversation_summary="Need a one-line confirmation the agent is alive.",
        confidence=0.5,
        instructions="Reply 'triage agent online'.",
    )
    t0 = time.perf_counter()
    smoke_result = await triage_with_model.receive_handoff(smoke_ctx)
    _banner("Part 1", time.perf_counter() - t0)
    print(f"  Smoke output: {(smoke_result.output or '')[:120]}")

    # =========================================================================
    # Part 2: Handoff Context
    # =========================================================================
    print("\n=== Part 2: Handoff Context ===\n")

    # Create a handoff context manually
    context = HandoffContext(
        source_agent_id=triage_agent.id,
        target_agent_id=technical_agent.id,
        reason=HandoffReason.SPECIALIZATION,
        original_task="Investigate slow API response times",
        conversation_summary="User reported 5s response times. Initial check shows normal CPU.",
        findings={
            "api_latency_p99": "5200ms",
            "cpu_usage": "45%",
            "memory_usage": "62%",
        },
        confidence=0.4,
        instructions="Focus on database query performance",
        handoff_chain=[triage_agent.id],
    )

    print("Handoff Context:")
    print(f"  From: {context.source_agent_id}")
    print(f"  To: {context.target_agent_id}")
    print(f"  Reason: {context.reason.value}")
    print(f"  Confidence: {context.confidence:.0%}")

    # Convert context to prompt for the target agent
    prompt = context.to_prompt()
    print("\nGenerated prompt for target agent:")
    print("-" * 40)
    print(prompt[:500] + "...")
    # Note: the receive_handoff() is exercised live in Part 4 + Part 7.
    # We skip a separate live call here to keep the tutorial fast.

    # =========================================================================
    # Part 3: Handoff Reasons
    # =========================================================================
    print("\n=== Part 3: Handoff Reasons ===\n")

    for reason in HandoffReason:
        descriptions = {
            HandoffReason.SPECIALIZATION: "Target has better capabilities for this task",
            HandoffReason.ESCALATION: "Issue needs higher authority or expertise",
            HandoffReason.DELEGATION: "Sub-task delegation to another agent",
            HandoffReason.COMPLETION: "Task completed, returning to parent",
            HandoffReason.FAILURE: "Agent failed, trying another approach",
        }
        print(f"  {reason.value}: {descriptions[reason]}")
    # Live ESCALATION example folds into the chain in Part 7.

    # =========================================================================
    # Part 4: Handoff Manager
    # =========================================================================
    print("\n=== Part 4: Handoff Manager ===\n")

    # Create a handoff manager
    manager = create_handoff_manager(
        agents=[triage_agent, technical_agent, escalation_agent],
        max_chain=5,  # Maximum number of handoffs
    )

    print("Handoff Manager:")
    print(f"  Registered agents: {len(manager.agents)}")
    print(f"  Max chain length: {manager.max_handoff_chain}")

    # Wire the model into all manager agents and run a real handoff.
    for agent_id in list(manager.agents):
        manager.agents[agent_id] = manager.agents[agent_id].with_model(model)
    state_smoke = AgentState(agent_id=triage_agent.id).with_message(
        Message.user("DB latency spiked to 5s, cpu normal.")
    )
    t0 = time.perf_counter()
    mgr_result = await manager.execute_handoff(
        source_agent=triage_agent,
        target_agent_id=technical_agent.id,
        task="Diagnose the latency spike",
        reason=HandoffReason.SPECIALIZATION,
        state=state_smoke,
        findings={"p99_ms": 5000},
    )
    _banner("Part 4", time.perf_counter() - t0)
    print(f"  Manager handoff output: {(mgr_result.output or '')[:160]}")

    # =========================================================================
    # Part 5: Creating Handoff Contexts Through Manager
    # =========================================================================
    print("\n=== Part 5: Creating Handoffs ===\n")

    # Simulate agent state with some conversation
    state = AgentState(
        agent_id=triage_agent.id,
        tool_history=("check_metrics", "query_logs"),
    )
    state = state.with_message(Message.user("API is slow"))
    state = state.with_message(Message.assistant("I'll investigate the API performance."))

    # Create handoff through manager
    handoff_context = await manager.create_handoff(
        source_agent=triage_agent,
        target_agent_id=technical_agent.id,
        task="Investigate slow API response times",
        reason=HandoffReason.SPECIALIZATION,
        state=state,
        findings={"initial_metrics": "Normal CPU, high DB latency"},
        instructions="Focus on database performance",
    )

    print("Created handoff:")
    print(f"  ID: {handoff_context.handoff_id}")
    print(f"  Chain: {' -> '.join(handoff_context.handoff_chain)}")
    print(f"  State snapshot: {handoff_context.state_snapshot}")
    # Live receive_handoff() folds into Part 7's chain demo.

    # =========================================================================
    # Part 6: Executing Handoffs with Model
    # =========================================================================
    print("\n=== Part 6: Executing Handoffs ===\n")
    print("`manager.execute_handoff(...)` was exercised in Part 4. The same")
    print("call shape works for any (source -> target, reason) pair — see")
    print("the chain demo in Part 7 for back-to-back execution.")

    # =========================================================================
    # Part 7: Chain Handoffs
    # =========================================================================
    print("\n=== Part 7: Chain Handoffs ===\n")

    # Configure all agents with model
    manager.agents[triage_agent.id] = triage_agent.with_model(triage_model)
    manager.agents[escalation_agent.id] = escalation_agent.with_model(model)

    # Execute a chain of handoffs
    chain_results = await manager.chain_handoff(
        agent_chain=[triage_agent.id, technical_agent.id, escalation_agent.id],
        task="Critical production outage affecting all users",
        initial_state=state,
    )

    print("Chain handoff completed:")
    for i, result in enumerate(chain_results):
        status = "OK" if result.success else f"FAILED: {result.error}"
        print(f"  Step {i + 1}: {result.source_agent_id} -> {result.target_agent_id}: {status}")

    # =========================================================================
    # Part 8: Handoff History
    # =========================================================================
    print("\n=== Part 8: Handoff History ===\n")

    print(f"Total handoffs in history: {len(manager.history)}")
    for ctx in manager.history[-3:]:  # Last 3 handoffs
        print(f"  {ctx.handoff_id}: {ctx.source_agent_id} -> {ctx.target_agent_id}")
        print(f"    Reason: {ctx.reason.value}")
        print(f"    Created: {ctx.created_at.isoformat()}")

    # Replay would just re-call receive_handoff() on the recorded
    # context — covered live in Parts 1, 4, and 7. We skip the replay
    # to keep the tutorial under the workbench's per-run budget.

    # =========================================================================
    # Part 9: Handoff Patterns
    # =========================================================================
    print("\n=== Part 9: Common Handoff Patterns ===\n")

    print("Pattern 1: Triage -> Specialist")
    print("  A generalist agent assesses and routes to domain experts")
    print()

    print("Pattern 2: Hierarchical Escalation")
    print("  L1 -> L2 -> L3 support escalation chain")
    print()

    print("Pattern 3: Parallel Specialists")
    print("  Multiple specialists analyze in parallel, results aggregated")
    print()

    print("Pattern 4: Return with Findings")
    print("  Specialist completes work and returns to coordinator")
    print()

    print("Pattern 5: Failover")
    print("  If one agent fails, handoff to backup agent")

    # =========================================================================
    # Part 10: Best Practices
    # =========================================================================
    print("\n=== Part 10: Best Practices ===\n")

    print("1. Keep handoff contexts focused - transfer only relevant info")
    print("2. Set reasonable max_chain limits to prevent infinite loops")
    print("3. Include clear instructions for the target agent")
    print("4. Track confidence through handoff chain")
    print("5. Use appropriate handoff reasons for clarity")
    print("6. Preserve key findings across handoffs")
    print("7. Monitor handoff history for debugging")

    # =========================================================================
    print("\n" + "=" * 60)
    print("Next: Tutorial 17 - Orchestrator Pattern")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
