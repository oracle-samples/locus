"""
Tutorial 14: Reasoning Patterns

This tutorial demonstrates Locus's reasoning capabilities:
- Reflexion: Self-evaluation and progress tracking
- Grounding: Verification that claims are supported by evidence
- Causal: Building and analyzing causal inference chains

These patterns help agents reason more effectively and avoid common pitfalls.

Run with:
    python examples/tutorial_14_reasoning_patterns.py
"""

from locus.core.messages import Message
from locus.core.state import AgentState, ToolExecution
from locus.reasoning import (
    # Causal
    CausalChain,
    # Grounding
    GroundingEvaluator,
    NodeType,
    # Reflexion
    Reflector,
    RelationshipType,
    build_causal_chain,
    evaluate_grounding,
    evaluate_progress,
)


def main():
    print("=" * 60)
    print("Tutorial 14: Reasoning Patterns")
    print("=" * 60)

    # =========================================================================
    # Part 1: Reflexion - Self-Evaluation
    # =========================================================================
    print("\n=== Part 1: Reflexion - Self-Evaluation ===\n")

    # Create a reflector for evaluating agent progress
    reflector = Reflector(
        loop_threshold=3,  # Detect loops after 3 repeated calls
        success_weight=0.15,  # Confidence boost per success
        error_penalty=0.2,  # Confidence penalty per error
    )

    # Create a sample agent state with some tool executions
    state = AgentState(agent_id="demo_agent")
    state = state.with_message(Message.user("Analyze the logs"))

    # Simulate successful tool execution
    execution = ToolExecution(
        tool_name="read_logs",
        tool_call_id="call_001",
        arguments={"file": "app.log"},
        result="Found 3 errors in the last hour",
    )
    state = state.with_tool_execution(execution)

    # Reflect on progress
    reflection = reflector.reflect(state)
    print(f"Assessment: {reflection.assessment.value}")
    print(f"Confidence Delta: {reflection.confidence_delta:+.2f}")
    if reflection.guidance:
        print(f"Guidance: {reflection.guidance}")

    # =========================================================================
    # Part 2: Detecting Loops
    # =========================================================================
    print("\n=== Part 2: Detecting Loops ===\n")

    # Create state with repeated tool calls (a loop pattern)
    # Manually set tool_history to simulate repeated calls
    loop_state = AgentState(
        agent_id="looping_agent",
        tool_history=("search_logs", "search_logs", "search_logs", "search_logs"),
    )

    # Reflect - should detect the loop
    reflection = reflector.reflect(loop_state)
    print(f"Assessment: {reflection.assessment.value}")
    if reflection.loop_pattern:
        print(f"Loop Pattern: {reflection.loop_pattern}")
    if reflection.guidance:
        print(f"Guidance: {reflection.guidance[:100]}...")

    # =========================================================================
    # Part 3: Convenience Function
    # =========================================================================
    print("\n=== Part 3: Quick Progress Evaluation ===\n")

    # Use the convenience function for quick evaluation
    quick_result = evaluate_progress(
        state=state,
        loop_threshold=3,
        success_weight=0.2,
    )
    print(f"Quick assessment: {quick_result.assessment.value}")

    # =========================================================================
    # Part 4: Grounding - Claim Verification
    # =========================================================================
    print("\n=== Part 4: Grounding - Claim Verification ===\n")

    # Create a grounding evaluator
    evaluator = GroundingEvaluator(
        replan_threshold=0.65,  # Replan if score below this
        claim_threshold=0.5,  # Individual claim threshold
        require_evidence=True,  # Require evidence for claims
    )

    # Define claims and evidence
    claims = [
        "The database is experiencing high load",
        "Memory usage is at 95%",
        "The API is responding normally",
    ]

    evidence = [
        "CPU usage: 89%",
        "Memory usage: 95%",
        "Database connections: 45/50 (90% utilized)",
        "API response time: 2500ms (above 200ms threshold)",
    ]

    # Evaluate grounding
    result = evaluator.evaluate(claims, evidence)

    print(f"Overall Grounding Score: {result.score:.2f}")
    print(f"Requires Replan: {result.requires_replan}")
    print("\nClaim Evaluations:")
    for claim_eval in result.claims:
        status = "grounded" if claim_eval.is_grounded else "UNGROUNDED"
        print(f"  [{status}] {claim_eval.claim}")
        print(f"    Score: {claim_eval.score:.2f} - {claim_eval.reasoning}")

    if result.ungrounded_claims:
        print(f"\nUngrounded claims: {result.ungrounded_claims}")

    # =========================================================================
    # Part 5: Grounding Guidance
    # =========================================================================
    print("\n=== Part 5: Replan Guidance ===\n")

    # Get guidance for replanning
    if evaluator.should_replan(result):
        guidance = evaluator.get_replan_guidance(result)
        print(guidance)
    else:
        print("All claims are sufficiently grounded. No replan needed.")

    # =========================================================================
    # Part 6: Causal Chains - Basic
    # =========================================================================
    print("\n=== Part 6: Causal Chains ===\n")

    # Build a causal chain for root cause analysis
    chain = CausalChain()

    # Add nodes (events/conditions)
    db_failure = chain.create_node(
        label="Database connection pool exhausted",
        node_type=NodeType.ROOT_CAUSE,
        evidence=["Connection count: 50/50"],
        confidence=0.9,
    )

    query_timeout = chain.create_node(
        label="Query timeouts",
        evidence=["Timeout errors in logs"],
        confidence=0.85,
    )

    api_slow = chain.create_node(
        label="API response slow",
        evidence=["P99 latency: 5000ms"],
        confidence=0.8,
    )

    user_errors = chain.create_node(
        label="Users seeing errors",
        node_type=NodeType.SYMPTOM,
        evidence=["Error rate: 15%"],
        confidence=0.95,
    )

    # Link nodes with causal relationships
    chain.link(
        db_failure.id, query_timeout.id, relationship=RelationshipType.CAUSES, confidence=0.9
    )
    chain.link(query_timeout.id, api_slow.id, relationship=RelationshipType.CAUSES, confidence=0.85)
    chain.link(api_slow.id, user_errors.id, relationship=RelationshipType.CAUSES, confidence=0.9)

    # Analyze the chain
    print("Root Causes:")
    for root in chain.identify_root_causes():
        print(f"  - {root.label} (confidence: {root.confidence:.0%})")

    print("\nSymptoms:")
    for symptom in chain.identify_symptoms():
        print(f"  - {symptom.label} (confidence: {symptom.confidence:.0%})")

    # =========================================================================
    # Part 7: Causal Path Analysis
    # =========================================================================
    print("\n=== Part 7: Causal Path Analysis ===\n")

    # Find the causal path from root cause to symptom
    path = chain.get_causal_path(db_failure.id, user_errors.id)
    if path:
        print("Causal path from root cause to symptom:")
        for i, node in enumerate(path):
            prefix = "  " * i + ("-> " if i > 0 else "")
            print(f"{prefix}{node.label}")

    # Get chain summary
    summary = chain.get_chain_summary()
    print("\nChain Summary:")
    print(f"  Total nodes: {summary['total_nodes']}")
    print(f"  Total edges: {summary['total_edges']}")
    print(f"  Avg confidence: {summary['avg_confidence']:.0%}")

    # =========================================================================
    # Part 8: Detecting Causal Conflicts
    # =========================================================================
    print("\n=== Part 8: Detecting Conflicts ===\n")

    # Create a chain with a conflict
    conflict_chain = CausalChain()

    a = conflict_chain.create_node(label="Event A")
    b = conflict_chain.create_node(label="Event B")

    # Create bidirectional causation (conflict!)
    conflict_chain.link(a.id, b.id, relationship=RelationshipType.CAUSES)
    conflict_chain.link(b.id, a.id, relationship=RelationshipType.CAUSES)

    # Detect conflicts
    conflicts = conflict_chain.detect_conflicts()
    if conflicts:
        print(f"Found {len(conflicts)} conflict(s):")
        for conflict in conflicts:
            print(f"  Type: {conflict.conflict_type}")
            print(f"  Description: {conflict.description}")
            if conflict.resolution_hint:
                print(f"  Resolution: {conflict.resolution_hint}")
    else:
        print("No conflicts detected")

    # =========================================================================
    # Part 9: Building Chains from Events
    # =========================================================================
    print("\n=== Part 9: Building from Event Data ===\n")

    # Build chain from event data (common pattern)
    events = [
        {"label": "Memory leak in service"},
        {"label": "Heap usage grows over time", "causes": ["Memory leak in service"]},
        {"label": "OutOfMemoryError", "causes": ["Heap usage grows over time"]},
        {"label": "Service crash", "causes": ["OutOfMemoryError"]},
        {"label": "Users disconnected", "causes": ["Service crash"]},
    ]

    auto_chain = build_causal_chain(events, auto_classify=True)

    print("Auto-built chain:")
    classifications = auto_chain.classify_nodes()
    for node_id, node_type in classifications.items():
        node = auto_chain.get_node(node_id)
        print(f"  [{node_type.value:12}] {node.label}")

    # =========================================================================
    # Part 10: Complete Reasoning Pipeline
    # =========================================================================
    print("\n=== Part 10: Complete Reasoning Pipeline ===\n")

    print("A typical agent reasoning pipeline:")
    print("1. Agent makes claims about the system state")
    print("2. Grounding evaluator checks if claims are supported by evidence")
    print("3. If not grounded, agent replans to gather more evidence")
    print("4. Once grounded, agent builds causal chain")
    print("5. Reflexion monitors for loops and adjusts confidence")
    print("6. Final output includes root causes and recommendations")

    # Demonstrate the pipeline
    agent_claims = [
        "Database is the bottleneck",
        "Network latency is normal",
    ]

    tool_evidence = [
        "DB query time: 500ms average",
        "Network RTT: 5ms",
        "DB CPU: 95%",
    ]

    grounding = evaluate_grounding(agent_claims, tool_evidence)
    print(f"\nGrounding score: {grounding.score:.0%}")

    if grounding.requires_replan:
        print("Need more evidence for some claims")
    else:
        print("Claims are grounded, proceeding with analysis")

    print("\n" + "=" * 60)
    print("Next: Tutorial 15 - Playbooks")
    print("=" * 60)


if __name__ == "__main__":
    main()
