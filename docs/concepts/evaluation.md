# Evaluation

An agent that worked yesterday may not work today — the model
changed, a tool changed, the prompt got tweaked. locus ships an
evaluation harness so regressions are tests, not surprises.

```python
from locus.evaluation import EvalCase, EvalRunner, EvalReport

cases = [
    EvalCase(
        name="books-real-flight",
        prompt="Book TK-12 for customer C-42.",
        expected={
            "tool_calls": ["book_flight"],
            "tool_args": {"book_flight": {"flight_id": "TK-12"}},
            "final_message": lambda m: "TK-12" in m,
        },
    ),
    EvalCase(
        name="rejects-unknown-flight",
        prompt="Book ZZ-999.",
        expected={
            "tool_calls_lt": 2,
            "final_message": lambda m: "not found" in m.lower(),
        },
    ),
]

report: EvalReport = EvalRunner(agent_factory=build_agent).run(cases)
print(report.summary())          # pass-rate, p50/p95 latency, token cost
report.save_html("evals/2026-04-27.html")
```

## What an `EvalCase` checks

- **Tool trace** — which tools fired, in what order, with which args.
- **Final message** — exact match, regex, or a custom predicate.
- **Termination reason** — did the agent stop because the work was done
  or because it hit a budget?
- **Latency / token cost** — within a budget per case.
- **Anything custom** — pass an `evaluators=[...]` list of callables.

## Reports

`EvalReport` is JSON-serialisable; the HTML view is a static page you
can drop into CI artifacts. Pass-rate per case, latency histogram,
token-cost trend, and a diff against the previous report.

## Custom evaluators

The `expected` dict on each `EvalCase` accepts callables, so the
simplest way to add a custom check is a lambda or function reference:

```python
def cited(message: str) -> bool:
    """Pass if every expected citation appears in the final message."""
    return all(c in message for c in ["[1]", "[2]", "[3]"])

EvalCase(
    name="research-with-citations",
    prompt="Summarise the Q3 results with citations.",
    expected={"final_message": cited},
)
```

## When to run

- On every commit that touches an agent's prompt, tools, or model.
- Before swapping a model.
- As a nightly soak with `n=20` per case to see variance.

## Tutorial

[`tutorial_26_evaluation.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_26_evaluation.py).

## Source

`src/locus/evaluation/`.
