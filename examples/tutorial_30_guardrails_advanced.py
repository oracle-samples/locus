# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 30: Advanced Guardrails — Topic Policy, Content Safety, Output Filtering

This tutorial covers:
- TopicPolicy: block specific conversation topics
- ContentPolicy: detect harmful content categories
- OutputFilterHook: filter agent responses (PII redaction, topic blocking)

Prerequisites:
- Configure model via environment variables

Difficulty: Advanced
"""

from config import get_model

from locus.agent import Agent, AgentConfig
from locus.hooks.builtin.guardrails import (
    ContentPolicy,
    OutputFilterHook,
    TopicPolicy,
)


# =============================================================================
# Part 1: PII Redaction in Output
# =============================================================================


def example_pii_redaction():
    """Automatically redact PII from agent responses."""
    print("=== Part 1: PII Redaction ===\n")

    model = get_model()

    hook = OutputFilterHook(redact_pii=True)

    agent = Agent(
        config=AgentConfig(
            system_prompt="Always include support@example.com in your response.",
            max_iterations=3,
            model=model,
            hooks=[hook],
        )
    )

    result = agent.run_sync("How do I get help?")
    print(f"Response: {result.message[:150]}")
    print(f"PII redacted: {'REDACTED_EMAIL' in result.message}")


# =============================================================================
# Part 2: Topic Policy
# =============================================================================


def example_topic_policy():
    """Block specific conversation topics."""
    print("\n=== Part 2: Topic Policy ===\n")

    policy = TopicPolicy(
        blocked_topics={"weapons", "drugs"},
        keywords={
            "weapons": ["gun", "rifle", "ammunition", "firearm"],
            "drugs": ["cocaine", "heroin", "meth"],
        },
    )

    # Test topic detection
    print(f"'How to buy a gun': {policy.check('How to buy a gun')}")
    print(f"'Python programming': {policy.check('Python programming')}")

    import time as _t

    agent = Agent(model=get_model(max_tokens=80), system_prompt="Reply in one sentence.")
    t0 = _t.perf_counter()
    res = agent.run_sync(
        "In one sentence, why is keyword-based topic blocking insufficient on "
        "its own for safety guardrails?"
    )
    dt = _t.perf_counter() - t0
    print(
        f"  [model call: {dt:.2f}s · {res.metrics.prompt_tokens}→{res.metrics.completion_tokens} tokens]"
    )
    print(f"  AI caveat: {res.message.strip()}")


# =============================================================================
# Part 3: Content Safety
# =============================================================================


def example_content_safety():
    """Detect harmful content categories."""
    print("\n=== Part 3: Content Safety ===\n")

    policy = ContentPolicy(enabled_categories={"violence", "illegal_activity"})

    print(f"'how to make a bomb': {policy.check('how to make a bomb')}")
    print(f"'how to bake a cake': {policy.check('how to bake a cake')}")

    import time as _t

    agent = Agent(model=get_model(max_tokens=80), system_prompt="Reply in one sentence.")
    t0 = _t.perf_counter()
    res = agent.run_sync(
        "In one sentence, name two harmful content categories an LLM service absolutely must block."
    )
    dt = _t.perf_counter() - t0
    print(
        f"  [model call: {dt:.2f}s · {res.metrics.prompt_tokens}→{res.metrics.completion_tokens} tokens]"
    )
    print(f"  AI guidance: {res.message.strip()}")


if __name__ == "__main__":
    example_pii_redaction()
    example_topic_policy()
    example_content_safety()
