"""
Tutorial 18: Specialist Agents

This tutorial provides a deep dive into specialist agents - domain-focused
agents with specific capabilities and playbook integration.

Topics covered:
1. Creating custom specialists
2. Specialist playbooks
3. Confidence estimation
4. Pre-built specialists
5. Specialist execution patterns

Run with:
    python examples/tutorial_18_specialist_agents.py
"""

import asyncio

from config import get_model, print_config

from locus.multiagent.specialist import (
    Playbook,
    PlaybookStep,
    Specialist,
    create_code_analyst,
    create_log_analyst,
    create_metrics_analyst,
    create_trace_analyst,
)
from locus.tools.decorator import tool


async def main():
    print("=" * 60)
    print("Tutorial 18: Specialist Agents")
    print("=" * 60)
    print()
    print_config()

    model = get_model()

    # =========================================================================
    # Part 1: Specialist Anatomy
    # =========================================================================
    print("\n=== Part 1: Specialist Anatomy ===\n")

    # A specialist has:
    # - Focused domain expertise (system_prompt)
    # - Specific tools for their domain
    # - Optional playbooks for procedures
    # - Confidence-based execution

    specialist = Specialist(
        name="API Specialist",
        specialist_type="api_analyst",
        description="Analyzes API performance, errors, and patterns",
        system_prompt="""You are an API analysis specialist. Your expertise:
1. Analyzing HTTP status codes and error rates
2. Identifying slow endpoints
3. Detecting anomalous traffic patterns
4. Recommending API optimizations

When analyzing:
- Check error rates by endpoint
- Look for latency outliers
- Identify authentication issues
- Note rate limiting triggers""",
        max_iterations=10,
        confidence_threshold=0.85,
        model=model,
    )

    print(f"Specialist: {specialist.name}")
    print(f"  Type: {specialist.specialist_type}")
    print(f"  Max iterations: {specialist.max_iterations}")
    print(f"  Confidence threshold: {specialist.confidence_threshold}")

    # =========================================================================
    # Part 2: Adding Domain Tools
    # =========================================================================
    print("\n=== Part 2: Domain Tools ===\n")

    # Define tools specific to API analysis
    @tool(name="get_endpoint_stats", description="Get statistics for an API endpoint")
    async def get_endpoint_stats(endpoint: str) -> str:
        return f"Endpoint {endpoint}: 1000 req/min, 2.5% error rate, p99=450ms"

    @tool(name="get_error_breakdown", description="Get error breakdown by status code")
    async def get_error_breakdown() -> str:
        return "Errors: 400=15%, 401=5%, 403=2%, 500=75%, 503=3%"

    @tool(name="get_top_slow_endpoints", description="Get slowest API endpoints")
    async def get_top_slow_endpoints() -> str:
        return "Slowest: /api/users (800ms), /api/search (650ms), /api/reports (500ms)"

    # Add tools to specialist
    specialist = Specialist(
        name="API Specialist",
        specialist_type="api_analyst",
        description="Analyzes API performance, errors, and patterns",
        system_prompt="You analyze API behavior and performance.",
        tools=[get_endpoint_stats, get_error_breakdown, get_top_slow_endpoints],
        model=model,
    )

    print(f"Tools available: {[t.name for t in specialist.tools]}")

    # =========================================================================
    # Part 3: Specialist Playbooks
    # =========================================================================
    print("\n=== Part 3: Specialist Playbooks ===\n")

    # Define playbooks for common procedures
    api_debug_playbook = Playbook(
        name="API Debug Procedure",
        description="Standard procedure for debugging API issues",
        preconditions=[
            "Incident ticket exists",
            "Basic metrics are accessible",
        ],
        steps=[
            PlaybookStep(
                instruction="Check overall API health metrics",
                required_tools=["get_endpoint_stats"],
                expected_output="Current request rate and error percentages",
            ),
            PlaybookStep(
                instruction="Analyze error distribution",
                required_tools=["get_error_breakdown"],
                expected_output="Breakdown of errors by type",
                on_failure="Escalate if unable to get error data",
            ),
            PlaybookStep(
                instruction="Identify slow endpoints",
                required_tools=["get_top_slow_endpoints"],
                expected_output="List of endpoints exceeding latency threshold",
            ),
        ],
        success_criteria="Root cause identified or escalation path determined",
    )

    # Add playbook to specialist
    specialist.playbooks.append(api_debug_playbook)

    print(f"Playbook: {api_debug_playbook.name}")
    print(f"  Preconditions: {api_debug_playbook.preconditions}")
    print(f"  Steps: {len(api_debug_playbook.steps)}")
    print(f"  Success criteria: {api_debug_playbook.success_criteria}")

    # Playbook as prompt
    playbook_prompt = api_debug_playbook.to_prompt()
    print("\nPlaybook prompt:")
    print("-" * 40)
    print(playbook_prompt[:500] + "...")

    # =========================================================================
    # Part 4: Playbook Selection
    # =========================================================================
    print("\n=== Part 4: Playbook Selection ===\n")

    # Add multiple playbooks
    performance_playbook = Playbook(
        name="Performance Optimization",
        description="Procedure for optimizing API performance",
        steps=[
            PlaybookStep(instruction="Profile slow endpoints"),
            PlaybookStep(instruction="Identify bottlenecks"),
            PlaybookStep(instruction="Recommend optimizations"),
        ],
    )

    security_playbook = Playbook(
        name="Security Analysis",
        description="Procedure for analyzing security issues",
        steps=[
            PlaybookStep(instruction="Check authentication failures"),
            PlaybookStep(instruction="Review access patterns"),
            PlaybookStep(instruction="Identify suspicious activity"),
        ],
    )

    specialist.playbooks.extend([performance_playbook, security_playbook])

    # Specialist automatically selects appropriate playbook based on task
    tasks = [
        "Debug the API errors we're seeing",
        "Optimize the slow /api/search endpoint",
        "Check for unauthorized access attempts",
    ]

    for task in tasks:
        selected = specialist.select_playbook(task)
        if selected:
            print(f"Task: '{task[:40]}...'")
            print(f"  Selected playbook: {selected.name}")

    # =========================================================================
    # Part 5: Executing Specialists
    # =========================================================================
    print("\n=== Part 5: Executing Specialists ===\n")

    result = await specialist.execute(
        task="API error rates have spiked in the last hour. Investigate and identify the cause.",
        context={
            "incident_id": "INC-2024-001",
            "affected_services": ["api-gateway"],
            "start_time": "2024-01-15T10:00:00Z",
        },
    )

    print("Execution Result:")
    print(f"  Success: {result.success}")
    print(f"  Confidence: {result.confidence:.0%}")
    print(f"  Duration: {result.duration_ms:.0f}ms")
    if result.output:
        print(f"  Output: {result.output[:300]}...")
    if result.error:
        print(f"  Error: {result.error}")

    # =========================================================================
    # Part 6: Pre-built Specialists
    # =========================================================================
    print("\n=== Part 6: Pre-built Specialists ===\n")

    # Use pre-built specialists for common domains
    log_analyst = create_log_analyst(model=model)
    metrics_analyst = create_metrics_analyst(model=model)
    trace_analyst = create_trace_analyst(model=model)
    code_analyst = create_code_analyst(model=model)

    specialists = [log_analyst, metrics_analyst, trace_analyst, code_analyst]

    print("Pre-built Specialists:")
    for spec in specialists:
        print(f"\n  {spec.name}")
        print(f"    Type: {spec.specialist_type}")
        # Show first part of system prompt
        prompt_preview = spec.system_prompt.split("\n")[0]
        print(f"    Focus: {prompt_preview[:60]}...")

    # =========================================================================
    # Part 7: Specialist with Custom Tools
    # =========================================================================
    print("\n=== Part 7: Custom Tools Integration ===\n")

    # Create tools for log analysis
    @tool(name="search_logs", description="Search logs for patterns")
    async def search_logs(pattern: str, timerange: str = "1h") -> str:
        return f"Found 42 matches for '{pattern}' in last {timerange}"

    @tool(name="get_error_logs", description="Get recent error logs")
    async def get_error_logs(limit: int = 10) -> str:
        return f"Retrieved {limit} most recent error logs"

    # Create log analyst with custom tools
    custom_log_analyst = create_log_analyst(
        model=model,
        tools=[search_logs, get_error_logs],
    )

    print(f"Custom log analyst tools: {[t.name for t in custom_log_analyst.tools]}")

    # Execute with tools
    log_result = await custom_log_analyst.execute(
        task="Search for NullPointerException errors in the last hour",
    )

    print("Log analysis result:")
    print(f"  Confidence: {log_result.confidence:.0%}")
    if log_result.output:
        print(f"  Output: {log_result.output[:200]}...")

    # =========================================================================
    # Part 8: Confidence Estimation
    # =========================================================================
    print("\n=== Part 8: Confidence Estimation ===\n")

    # Specialists estimate confidence based on response markers
    responses = [
        ("definitely the root cause", "High confidence markers"),
        ("might be related to", "Low confidence markers"),
        ("confirmed by the logs", "Verification markers"),
        ("unclear what is causing", "Uncertainty markers"),
    ]

    print("Confidence markers in responses:")
    for response, description in responses:
        confidence = specialist._estimate_confidence(response)
        print(f"  '{response}' -> {confidence:.0%} ({description})")

    # =========================================================================
    # Part 9: Specialist Patterns
    # =========================================================================
    print("\n=== Part 9: Specialist Patterns ===\n")

    print("Pattern 1: Domain Expert")
    print("  - Focused system prompt")
    print("  - Domain-specific tools")
    print("  - High confidence threshold")
    print()

    print("Pattern 2: Procedure Follower")
    print("  - Playbook-driven execution")
    print("  - Step validation")
    print("  - Clear success criteria")
    print()

    print("Pattern 3: Adaptive Analyst")
    print("  - Multiple playbooks")
    print("  - Task-based selection")
    print("  - Dynamic tool usage")
    print()

    print("Pattern 4: Pipeline Stage")
    print("  - Part of larger workflow")
    print("  - Receives context from upstream")
    print("  - Produces structured output")

    # =========================================================================
    # Part 10: Creating Specialist Teams
    # =========================================================================
    print("\n=== Part 10: Specialist Teams ===\n")

    def create_incident_response_team(model):
        """Create a team of specialists for incident response."""
        return {
            "triage": Specialist(
                name="Triage Specialist",
                specialist_type="triage",
                description="Initial incident assessment and severity classification",
                system_prompt="Assess incidents and determine severity and routing.",
                model=model,
            ),
            "logs": create_log_analyst(model=model),
            "metrics": create_metrics_analyst(model=model),
            "code": create_code_analyst(model=model),
        }

    team = create_incident_response_team(model)
    print("Incident Response Team:")
    for role, spec in team.items():
        print(f"  {role}: {spec.name}")

    # =========================================================================
    print("\n" + "=" * 60)
    print("Next: Tutorial 19 - Guardrails & Security")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
