"""
Tutorial 26: Evaluation Framework — Systematic Agent Quality Testing

This tutorial covers:
- EvalCase: defining test cases with expected behaviors
- EvalRunner: running agents against test suites
- EvalReport: analyzing results and scoring

Prerequisites:
- Configure model via environment variables

Difficulty: Intermediate
"""

from config import get_model

from locus.agent import Agent, AgentConfig
from locus.evaluation import EvalCase, EvalRunner


# =============================================================================
# Part 1: Define evaluation cases
# =============================================================================


def example_evaluation():
    """Run a systematic evaluation of an agent."""
    print("=== Agent Evaluation ===\n")

    model = get_model()

    agent = Agent(config=AgentConfig(
        system_prompt="You are a helpful assistant. Answer concisely.",
        max_iterations=3, model=model,
    ))

    # Define test cases
    cases = [
        EvalCase(
            name="basic_knowledge",
            prompt="What is the capital of France?",
            expected_output_contains=["paris"],
            max_iterations=3,
        ),
        EvalCase(
            name="math",
            prompt="What is 15 * 7?",
            expected_output_contains=["105"],
        ),
        EvalCase(
            name="no_hallucination",
            prompt="What is the capital of France?",
            expected_output_not_contains=["berlin", "london"],
        ),
    ]

    # Run evaluation
    runner = EvalRunner(agent=agent)
    report = runner.run(cases)

    # Print results
    print(report.summary())
    print(f"\nTotal: {report.total_cases}, Passed: {report.passed}, Failed: {report.failed}")
    print(f"Average score: {report.avg_score:.2f}")


if __name__ == "__main__":
    example_evaluation()
