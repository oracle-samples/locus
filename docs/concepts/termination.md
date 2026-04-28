# Termination algebra

When does an agent stop? locus answers that with **composable
conditions** — small classes that return `True` when the run is done,
combined with `And` / `Or`.

```python
from locus.core.termination import (
    MaxIterations, TokenLimit, TimeLimit,
    NoToolCalls, ToolCalled, ConfidenceMet,
    TextMention, CustomCondition,
)

agent = Agent(
    model=...,
    tools=[search, send],
    termination=(
        # the work happened AND we believe it
        (ToolCalled("send") & ConfidenceMet(0.9))
        # … or we hit the safety cap
        | MaxIterations(10)
    ),
)
```

## Built-in conditions

| Condition | Trigger |
|---|---|
| `MaxIterations(n)` | n ReAct turns reached. |
| `TokenLimit(n)` | Cumulative model tokens exceed n. |
| `TimeLimit(seconds)` | Wall-clock budget exceeded. |
| `NoToolCalls()` | Last turn produced text and no tool calls. |
| `ToolCalled(name)` | A specific tool fired (with optional args predicate). |
| `ConfidenceMet(threshold)` | Reflexion / self-eval clears the bar. |
| `TextMention(pattern)` | Final message contains a regex match. |
| `CustomCondition(fn)` | Anything you can write as `(state) -> bool`. |

## Composition

Compose with the `&` (And) and `|` (Or) operators directly on the
condition objects. The result is a typed `AndCondition` /
`OrCondition` you can keep composing:

```python
termination=(
    ToolCalled("submit")
    & (ConfidenceMet(0.85) | MaxIterations(5))
)
```

## Why algebra?

Real agents have multiple stopping criteria — *"finish when X is done
**and** we're confident, **or** time's up"*. Hand-rolling that as `if`
statements gets painful fast. Termination conditions are explicit,
inspectable, and unit-testable as ordinary classes.

## Tutorial

[`tutorial_37_termination.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_37_termination.py).

## Source

`src/locus/core/termination.py`.
