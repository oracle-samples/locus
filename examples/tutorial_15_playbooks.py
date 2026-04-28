"""
Tutorial 15: Playbooks

This tutorial demonstrates Locus's playbook system for structured
agent execution plans.

Topics covered:
1. Creating playbook steps
2. Defining playbooks with validation
3. Tracking execution progress
4. Enforcing playbook compliance
5. Loading playbooks from YAML

Run with:
    python examples/tutorial_15_playbooks.py
"""

from datetime import UTC, datetime

from locus.playbooks import (
    Playbook,
    PlaybookPlan,
    PlaybookStep,
    StepExecution,
    StepStatus,
)


def main():
    print("=" * 60)
    print("Tutorial 15: Playbooks")
    print("=" * 60)

    # =========================================================================
    # Part 1: Creating Playbook Steps
    # =========================================================================
    print("\n=== Part 1: Creating Playbook Steps ===\n")

    # Define individual steps
    step1 = PlaybookStep(
        id="gather_logs",
        description="Collect relevant log files from the affected services",
        expected_tools=["read_file", "search_logs"],
        hints=[
            "Start with the most recent logs",
            "Look for ERROR and WARN levels",
        ],
        required=True,
        max_tool_calls=5,
    )

    step2 = PlaybookStep(
        id="analyze_errors",
        description="Analyze the collected logs for error patterns",
        expected_tools=["analyze_logs", "count_errors"],
        hints=["Group errors by type", "Note timestamps"],
        required=True,
    )

    step3 = PlaybookStep(
        id="check_metrics",
        description="Review system metrics during the incident window",
        expected_tools=["query_metrics", "get_dashboard"],
        hints=["Focus on CPU, memory, and network"],
        required=False,  # Optional step
    )

    step4 = PlaybookStep(
        id="summarize_findings",
        description="Create a summary of findings and recommendations",
        expected_tools=[],  # No specific tools required
        hints=["Include root cause if identified"],
        required=True,
    )

    print(f"Step 1: {step1.id}")
    print(f"  Description: {step1.description}")
    print(f"  Expected tools: {step1.expected_tools}")
    print(f"  Required: {step1.required}")

    # =========================================================================
    # Part 2: Creating a Complete Playbook
    # =========================================================================
    print("\n=== Part 2: Creating a Playbook ===\n")

    playbook = Playbook(
        id="incident_investigation",
        name="Incident Investigation Playbook",
        description="Standard procedure for investigating production incidents",
        version="1.0.0",
        steps=[step1, step2, step3, step4],
        strict_sequence=True,  # Steps must be in order
        allow_extra_tools=True,  # Allow tools not in expected_tools
        max_iterations=20,
        tags=["incident", "investigation", "production"],
    )

    print(f"Playbook: {playbook.name}")
    print(f"Version: {playbook.version}")
    print(f"Steps: {len(playbook.steps)}")
    print(f"Strict sequence: {playbook.strict_sequence}")
    print(f"Tags: {playbook.tags}")

    # Access specific step
    step = playbook.get_step("analyze_errors")
    if step:
        print(f"\nStep 'analyze_errors': {step.description}")

    # =========================================================================
    # Part 3: Execution Plans
    # =========================================================================
    print("\n=== Part 3: Execution Plans ===\n")

    # Create an execution plan from the playbook
    plan = PlaybookPlan(playbook=playbook)

    print(f"Current step: {plan.current_step.id if plan.current_step else 'None'}")
    print(f"Progress: {plan.progress:.0%}")
    print(f"Pending steps: {plan.pending_steps}")

    # Simulate completing a step
    step_exec = StepExecution(
        step_id="gather_logs",
        status=StepStatus.COMPLETED,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        tool_calls=["read_file", "search_logs", "read_file"],
        tool_call_count=3,
        result="Found 15 error entries in app.log",
    )

    # Update plan with execution
    plan.step_executions["gather_logs"] = step_exec
    plan.current_step_index = 1  # Move to next step

    print("\nAfter completing step 1:")
    print(f"Progress: {plan.progress:.0%}")
    print(f"Current step: {plan.current_step.id if plan.current_step else 'None'}")
    print(f"Completed steps: {plan.completed_steps}")

    # =========================================================================
    # Part 4: Step Status Tracking
    # =========================================================================
    print("\n=== Part 4: Step Status Tracking ===\n")

    # Different step statuses
    for status in StepStatus:
        print(f"  {status.value}")

    # Check step completion
    print(f"\nIs 'gather_logs' complete? {plan.is_step_complete('gather_logs')}")
    print(f"Is 'analyze_errors' complete? {plan.is_step_complete('analyze_errors')}")

    # Get execution details
    exec_details = plan.get_step_execution("gather_logs")
    if exec_details:
        print("\nStep 'gather_logs' execution:")
        print(f"  Status: {exec_details.status.value}")
        print(f"  Tool calls: {exec_details.tool_call_count}")
        print(f"  Result: {exec_details.result}")

    # =========================================================================
    # Part 5: Playbook Validation
    # =========================================================================
    print("\n=== Part 5: Playbook Validation ===\n")

    # Playbooks with validation criteria
    validated_step = PlaybookStep(
        id="validate_fix",
        description="Verify the fix is working",
        expected_tools=["run_tests", "check_health"],
        validation={
            "min_tool_calls": 1,
            "required_result_keywords": ["passed", "healthy"],
        },
        required=True,
    )

    print(f"Step with validation: {validated_step.id}")
    print(f"Validation rules: {validated_step.validation}")

    # =========================================================================
    # Part 6: Playbook Metadata
    # =========================================================================
    print("\n=== Part 6: Playbook Metadata ===\n")

    # Steps and playbooks can have arbitrary metadata
    step_with_meta = PlaybookStep(
        id="escalate",
        description="Escalate if issue persists",
        expected_tools=["send_alert", "page_oncall"],
        metadata={
            "severity_threshold": "high",
            "escalation_timeout_minutes": 30,
            "notify_channels": ["#incidents", "#oncall"],
        },
    )

    print(f"Step metadata: {step_with_meta.metadata}")

    playbook_with_meta = Playbook(
        id="deployment_rollback",
        name="Deployment Rollback",
        description="Procedure for rolling back a failed deployment",
        steps=[step_with_meta],
        metadata={
            "owner": "platform-team",
            "last_reviewed": "2024-01-15",
            "sla_minutes": 15,
        },
    )

    print(f"Playbook metadata: {playbook_with_meta.metadata}")

    # =========================================================================
    # Part 7: Building Playbooks Programmatically
    # =========================================================================
    print("\n=== Part 7: Building Playbooks Programmatically ===\n")

    def create_deployment_playbook(environment: str, services: list[str]) -> Playbook:
        """Create a deployment playbook for specific services."""
        steps = []

        # Pre-deployment checks
        steps.append(
            PlaybookStep(
                id="pre_check",
                description=f"Verify {environment} environment is ready",
                expected_tools=["check_health", "verify_deps"],
                required=True,
            )
        )

        # Deploy each service
        for service in services:
            steps.append(
                PlaybookStep(
                    id=f"deploy_{service}",
                    description=f"Deploy {service} to {environment}",
                    expected_tools=["deploy", "wait_healthy"],
                    metadata={"service": service},
                    required=True,
                )
            )

        # Post-deployment validation
        steps.append(
            PlaybookStep(
                id="post_validate",
                description="Validate deployment success",
                expected_tools=["run_smoke_tests", "check_metrics"],
                required=True,
            )
        )

        return Playbook(
            id=f"deploy_{environment}",
            name=f"{environment.title()} Deployment",
            steps=steps,
            tags=["deployment", environment],
        )

    prod_playbook = create_deployment_playbook("production", ["api", "web", "worker"])
    print(f"Generated playbook: {prod_playbook.name}")
    print(f"Steps: {[s.id for s in prod_playbook.steps]}")

    # =========================================================================
    # Part 8: Playbook Progress Visualization
    # =========================================================================
    print("\n=== Part 8: Progress Visualization ===\n")

    def visualize_progress(plan: PlaybookPlan) -> None:
        """Visualize playbook execution progress."""
        print(f"Playbook: {plan.playbook.name}")
        print(
            f"Progress: [{'#' * int(plan.progress * 20)}{'-' * (20 - int(plan.progress * 20))}] {plan.progress:.0%}"
        )
        print()

        for i, step in enumerate(plan.playbook.steps):
            exec_info = plan.step_executions.get(step.id)

            if exec_info:
                status_icon = {
                    StepStatus.COMPLETED: "[done]",
                    StepStatus.IN_PROGRESS: "[....]",
                    StepStatus.FAILED: "[FAIL]",
                    StepStatus.SKIPPED: "[skip]",
                    StepStatus.PENDING: "[    ]",
                }[exec_info.status]
            elif i == plan.current_step_index:
                status_icon = "[>>>>]"
            else:
                status_icon = "[    ]"

            required = "*" if step.required else " "
            print(f"  {status_icon} {required} {step.id}: {step.description[:40]}...")

    # Create a demo plan with mixed progress
    demo_plan = PlaybookPlan(playbook=playbook)
    demo_plan.step_executions["gather_logs"] = StepExecution(
        step_id="gather_logs", status=StepStatus.COMPLETED
    )
    demo_plan.step_executions["analyze_errors"] = StepExecution(
        step_id="analyze_errors", status=StepStatus.IN_PROGRESS
    )
    demo_plan.current_step_index = 1

    visualize_progress(demo_plan)

    # =========================================================================
    # Part 9: Playbook Best Practices
    # =========================================================================
    print("\n=== Part 9: Best Practices ===\n")

    print("1. Keep steps focused and atomic")
    print("2. Use descriptive step IDs (snake_case)")
    print("3. Provide helpful hints for complex steps")
    print("4. Mark truly optional steps as required=False")
    print("5. Set reasonable max_tool_calls to prevent runaway")
    print("6. Use metadata for operational context")
    print("7. Version your playbooks for change tracking")
    print("8. Include validation criteria for critical steps")

    # =========================================================================
    print("\n" + "=" * 60)
    print("Next: Tutorial 16 - Agent Handoff")
    print("=" * 60)


if __name__ == "__main__":
    main()
