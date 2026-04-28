"""
Tutorial 37: Composable Termination, output_key, Dynamic System Prompt

This tutorial covers:
- Composable termination: MaxIterations | TextMention & TokenLimit
- output_key: auto-save agent output to state metadata
- Dynamic system_prompt: callable that receives runtime context

Prerequisites:
- Configure model via environment variables

Difficulty: Intermediate
"""

from config import get_model

from locus.agent import Agent, AgentConfig
from locus.core.termination import (
    ConfidenceMet,
    CustomCondition,
    MaxIterations,
    TextMention,
    TimeLimit,
    TokenLimit,
)


# =============================================================================
# Part 1: Composable Termination Conditions
# =============================================================================


def example_termination():
    """Combine termination conditions with | (OR) and & (AND)."""
    print("=== Part 1: Composable Termination ===\n")

    from locus.core.messages import Message
    from locus.core.state import AgentState

    # OR: stop if EITHER condition met
    condition = MaxIterations(5) | TextMention("DONE")
    print("MaxIterations(5) | TextMention('DONE')")

    state = AgentState(agent_id="test").with_iteration(6)
    stop, reason = condition.check(state)
    print(f"  Iteration 6: stop={stop}, reason={reason}")

    state2 = AgentState(agent_id="test").with_message(Message.assistant("All DONE"))
    stop2, reason2 = condition.check(state2)
    print(f"  Message 'DONE': stop={stop2}, reason={reason2}")

    # AND: stop only if BOTH conditions met
    condition2 = MaxIterations(3) & TokenLimit(1000)
    print(f"\nMaxIterations(3) & TokenLimit(1000)")

    state3 = AgentState(agent_id="test").with_iteration(4)
    stop3, _ = condition2.check(state3)
    print(f"  Iterations met, tokens not: stop={stop3}")

    state4 = state3.with_token_usage(prompt_tokens=600, completion_tokens=500)
    stop4, reason4 = condition2.check(state4)
    print(f"  Both met: stop={stop4}, reason={reason4}")

    # Custom
    custom = CustomCondition(lambda state, **ctx: (state.iteration > 10, "too_many_iterations"))
    print(f"\nCustomCondition: {custom.check(AgentState(agent_id='t').with_iteration(11))}")


# =============================================================================
# Part 2: output_key — Auto-Save Agent Output
# =============================================================================


def example_output_key():
    """Agent output automatically saved to state metadata."""
    print("\n=== Part 2: output_key ===\n")

    model = get_model()

    agent = Agent(
        config=AgentConfig(
            system_prompt="Answer in one word.",
            max_iterations=3,
            model=model,
            output_key="answer",
        )
    )

    result = agent.run_sync("Capital of France?")
    print(f"Response: {result.message}")
    print(f"State metadata['answer']: {result.state.metadata.get('answer')}")
    print("Now other agents can read state['answer'] without parsing!")


# =============================================================================
# Part 3: Dynamic System Prompt
# =============================================================================


def example_dynamic_prompt():
    """System prompt changes based on runtime context."""
    print("\n=== Part 3: Dynamic System Prompt ===\n")

    model = get_model()

    def my_prompt(context):
        role = context.get("metadata", {}).get("role", "assistant")
        language = context.get("metadata", {}).get("language", "English")
        return f"You are a {role}. Respond in {language}. Be concise."

    agent = Agent(
        config=AgentConfig(
            system_prompt=my_prompt,
            max_iterations=3,
            model=model,
        )
    )

    # Different metadata → different behavior
    r1 = agent.run_sync("What is 7*8?", metadata={"role": "math teacher"})
    print(f"Math teacher: {r1.message}")

    r2 = agent.run_sync("What is gravity?", metadata={"role": "physicist", "language": "Spanish"})
    print(f"Physicist (Spanish): {r2.message[:100]}")


if __name__ == "__main__":
    example_termination()
    example_output_key()
    example_dynamic_prompt()
