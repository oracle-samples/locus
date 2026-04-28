"""
Tutorial 09: Human-in-the-Loop

This tutorial covers:
- Pausing graphs for human input
- The interrupt() function
- Resuming execution with responses
- Approval workflows

Prerequisites: Tutorial 08 (State Reducers)
Difficulty: Advanced
"""

import asyncio

from locus.core import Command, interrupt
from locus.multiagent import END, START, StateGraph


# =============================================================================
# Part 1: Basic Interrupt
# =============================================================================


async def example_basic_interrupt():
    """Pause execution and wait for human input."""
    print("=== Part 1: Basic Interrupt ===\n")

    graph = StateGraph()

    async def prepare(inputs):
        return {"action": "delete", "target": inputs.get("file", "data.txt")}

    async def request_approval(inputs):
        # interrupt() pauses execution and returns when resumed
        response = interrupt(
            {
                "question": f"Approve {inputs['action']} on {inputs['target']}?",
                "options": ["yes", "no"],
            }
        )
        return {"approved": response == "yes", "response": response}

    async def execute_action(inputs):
        if inputs.get("approved"):
            return {"result": f"Executed {inputs['action']} on {inputs['target']}"}
        return {"result": "Action cancelled"}

    graph.add_node("prepare", prepare)
    graph.add_node("approval", request_approval)
    graph.add_node("execute", execute_action)

    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "approval")
    graph.add_edge("approval", "execute")
    graph.add_edge("execute", END)

    # First execution - will pause at approval
    print("Starting workflow...")
    result = await graph.execute({"file": "important.txt"})

    if result.is_interrupted:
        print(f"PAUSED at: {result.interrupt.node_id}")
        print(f"Question: {result.interrupt.interrupt.payload['question']}")

        # Simulate human providing "yes"
        print("User responds: 'yes'")

        # Resume with the response
        result = await graph.execute(Command(update=result.final_state, resume="yes"))

        print(f"Result: {result.final_state.get('result')}")
    print()


# =============================================================================
# Part 2: Multi-Step Approval
# =============================================================================


async def example_multi_step():
    """Multiple interrupt points in a workflow."""
    print("=== Part 2: Multi-Step Approval ===\n")

    graph = StateGraph()

    async def ask_name(inputs):
        name = interrupt({"question": "What is your name?", "type": "text"})
        return {"name": name}

    async def ask_email(inputs):
        email = interrupt({"question": f"Hi {inputs['name']}, what's your email?"})
        return {"email": email}

    async def confirm(inputs):
        confirmed = interrupt(
            {
                "question": f"Confirm: {inputs['name']} <{inputs['email']}>?",
                "options": ["confirm", "cancel"],
            }
        )
        return {"confirmed": confirmed == "confirm"}

    async def complete(inputs):
        if inputs.get("confirmed"):
            return {"status": "Account created", "user": inputs["name"]}
        return {"status": "Cancelled"}

    graph.add_node("name", ask_name)
    graph.add_node("email", ask_email)
    graph.add_node("confirm", confirm)
    graph.add_node("complete", complete)

    graph.add_edge(START, "name")
    graph.add_edge("name", "email")
    graph.add_edge("email", "confirm")
    graph.add_edge("confirm", "complete")
    graph.add_edge("complete", END)

    # Simulate the full flow
    responses = ["Alice", "alice@example.com", "confirm"]

    print("Registration flow:")
    result = await graph.execute({})

    for response in responses:
        if result.is_interrupted:
            print(f"  Q: {result.interrupt.interrupt.payload['question']}")
            print(f"  A: {response}")
            result = await graph.execute(Command(update=result.final_state, resume=response))
        else:
            break

    print(f"\nFinal: {result.final_state.get('status')}")
    print()


# =============================================================================
# Part 3: Conditional Interrupts
# =============================================================================


async def example_conditional_interrupt():
    """Only interrupt when certain conditions are met."""
    print("=== Part 3: Conditional Interrupts ===\n")

    graph = StateGraph()

    async def assess_risk(inputs):
        amount = inputs.get("amount", 0)
        if amount < 100:
            risk = "low"
        elif amount < 1000:
            risk = "medium"
        else:
            risk = "high"
        return {"amount": amount, "risk": risk}

    async def maybe_approve(inputs):
        risk = inputs.get("risk")

        # Only interrupt for medium/high risk
        if risk == "low":
            return {"approved": True, "approver": "auto"}

        # High risk needs manager approval
        required = "manager" if risk == "medium" else "executive"
        response = interrupt(
            {
                "message": f"${inputs['amount']} requires {required} approval",
                "risk": risk,
            }
        )
        return {"approved": response == "approve", "approver": required}

    async def process(inputs):
        if inputs.get("approved"):
            return {"result": f"Transaction approved by {inputs['approver']}"}
        return {"result": "Transaction rejected"}

    graph.add_node("assess", assess_risk)
    graph.add_node("approve", maybe_approve)
    graph.add_node("process", process)

    graph.add_edge(START, "assess")
    graph.add_edge("assess", "approve")
    graph.add_edge("approve", "process")
    graph.add_edge("process", END)

    # Test different amounts
    test_cases = [
        (50, None),  # Low risk - auto approved
        (500, "approve"),  # Medium risk - manager approval
        (5000, "approve"),  # High risk - executive approval
    ]

    for amount, user_response in test_cases:
        print(f"Processing ${amount}...")
        result = await graph.execute({"amount": amount})

        if result.is_interrupted:
            print(f"  Needs approval: {result.interrupt.interrupt.payload['risk']} risk")
            result = await graph.execute(Command(update=result.final_state, resume=user_response))

        print(f"  -> {result.final_state.get('result')}")
    print()


# =============================================================================
# Part 4: interrupt_before Configuration
# =============================================================================


async def example_interrupt_before():
    """Use config to interrupt before specific nodes."""
    print("=== Part 4: interrupt_before ===\n")

    graph = StateGraph()

    async def prepare(inputs):
        return {"data": inputs.get("data", "sample"), "prepared": True}

    async def deploy(inputs):
        # This is a sensitive operation
        return {"deployed": True, "target": inputs.get("environment")}

    async def verify(inputs):
        return {"verified": True}

    graph.add_node("prepare", prepare)
    graph.add_node("deploy", deploy)
    graph.add_node("verify", verify)

    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "deploy")
    graph.add_edge("deploy", "verify")
    graph.add_edge("verify", END)

    # Configure to interrupt before deploy node
    graph.config.interrupt_before = ["deploy"]

    print("Deploying to production...")
    result = await graph.execute({"environment": "production", "data": "v2.0"})

    if result.is_interrupted:
        print(f"PAUSED before: {result.interrupt.node_id}")
        print(f"Current state: prepared={result.final_state.get('prepared')}")
        print("\nThis allows review before sensitive operations!")
    print()


# =============================================================================
# Part 5: Complete Approval Workflow
# =============================================================================


async def example_complete_workflow():
    """A realistic approval workflow."""
    print("=== Part 5: Complete Approval Workflow ===\n")

    graph = StateGraph()

    async def create_request(inputs):
        return {
            "request_id": "REQ-001",
            "type": inputs.get("type", "change"),
            "description": inputs.get("description", ""),
            "status": "pending",
        }

    async def technical_review(inputs):
        approval = interrupt(
            {
                "step": "Technical Review",
                "request": inputs["request_id"],
                "description": inputs["description"],
                "question": "Is this technically feasible?",
            }
        )
        return {
            "tech_approved": approval == "approve",
            "tech_comments": "Reviewed by engineering",
        }

    async def manager_approval(inputs):
        if not inputs.get("tech_approved"):
            return {"status": "rejected", "reason": "Technical review failed"}

        approval = interrupt(
            {
                "step": "Manager Approval",
                "request": inputs["request_id"],
                "question": "Approve this change request?",
            }
        )
        return {
            "manager_approved": approval == "approve",
            "status": "approved" if approval == "approve" else "rejected",
        }

    async def finalize(inputs):
        status = inputs.get("status")
        return {
            "final_status": status,
            "message": f"Request {inputs['request_id']}: {status}",
        }

    graph.add_node("create", create_request)
    graph.add_node("tech", technical_review)
    graph.add_node("manager", manager_approval)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "create")
    graph.add_edge("create", "tech")
    graph.add_edge("tech", "manager")
    graph.add_edge("manager", "finalize")
    graph.add_edge("finalize", END)

    # Simulate the workflow
    print("Change Request Workflow")
    print("-" * 30)

    result = await graph.execute(
        {
            "type": "change",
            "description": "Update database schema",
        }
    )

    approvals = ["approve", "approve"]
    approval_idx = 0

    while result.is_interrupted and approval_idx < len(approvals):
        step = result.interrupt.interrupt.payload.get("step", "Unknown")
        question = result.interrupt.interrupt.payload.get("question", "")
        print(f"\n{step}: {question}")
        print(f"  -> {approvals[approval_idx]}")

        result = await graph.execute(
            Command(update=result.final_state, resume=approvals[approval_idx])
        )
        approval_idx += 1

    print(f"\nResult: {result.final_state.get('message')}")
    print()


# =============================================================================
# Main
# =============================================================================


async def main():
    """Run all tutorial parts."""
    print("=" * 60)
    print("Tutorial 09: Human-in-the-Loop")
    print("=" * 60)
    print()

    await example_basic_interrupt()
    await example_multi_step()
    await example_conditional_interrupt()
    await example_interrupt_before()
    await example_complete_workflow()

    print("=" * 60)
    print("Next: Tutorial 10 - Advanced Patterns")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
