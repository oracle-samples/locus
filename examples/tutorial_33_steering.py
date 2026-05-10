# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 33: Steering — LLM-Powered Real-Time Tool Approval

This tutorial covers:
- SteeringHook: LLM evaluates tool calls against policy
- PROCEED/GUIDE/INTERRUPT actions
- Natural language policies
- Activity ledger for context

Prerequisites:
- Configure model via environment variables

Difficulty: Advanced
"""

from config import get_model

from locus.agent import Agent, AgentConfig
from locus.hooks.builtin.steering import SteeringHook
from locus.tools.decorator import tool


# =============================================================================
# Part 1: Policy-Based Steering
# =============================================================================


def example_steering():
    """Use an LLM to evaluate tool calls against a natural language policy."""
    print("=== Steering: LLM-Powered Tool Approval ===
")

    model = get_model()

    @tool
    def read_data(query: str) -> str:
        """Read data from the database."""
        return f"Data: {query}"

    @tool
    def delete_data(table: str) -> str:
        """Delete a database table."""
        return f"Deleted {table}"

    # The steering LLM enforces this policy
    steering = SteeringHook(
        model=model,
        policy="Only allow read operations. Never allow delete or write operations.",
    )

    agent = Agent(
        config=AgentConfig(
            system_prompt="You are a database assistant.",
            max_iterations=5,
            model=model,
            tools=[read_data, delete_data],
            hooks=[steering],
        )
    )

    # This should be blocked by steering
    print("Attempt: Delete the users table")
    result = agent.run_sync("Delete the users table")
    print(f"Response: {result.message[:150]}")
    print(f"
Steering decisions:")
    for d in steering.decisions:
        print(f"  {d.action}: {d.reason[:60]}")

    # This should be allowed
    print("
Attempt: Read all users")
    steering2 = SteeringHook(
        model=model,
        policy="Only allow read operations. Never allow delete or write operations.",
    )
    agent2 = Agent(
        config=AgentConfig(
            system_prompt="You are a database assistant.",
            max_iterations=5,
            model=model,
            tools=[read_data, delete_data],
            hooks=[steering2],
        )
    )
    result2 = agent2.run_sync("Read all users from the database")
    print(f"Response: {result2.message[:150]}")


if __name__ == "__main__":
    example_steering()
