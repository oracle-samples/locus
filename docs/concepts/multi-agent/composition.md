# Composition (pipelines)

The composition primitives are for flows you can write as a regular
function: do A, then B, then C — with optional fan-out and merge.

```python
from locus.agent.composition import (
    SequentialPipeline, ParallelPipeline, LoopAgent,
)

pipeline = SequentialPipeline(
    agents=[
        ParallelPipeline(agents=[researcher, fact_checker]),
        summariser,
        LoopAgent(agent=reviser, max_iterations=5),
    ],
)

result = pipeline.run_sync("Brief on Q3 launch.")
```

- **`SequentialPipeline`** — chain agents; each takes the previous
  output as input.
- **`ParallelPipeline`** — fan-out to N agents on the same input;
  merge their results.
- **`LoopAgent`** — run an agent until a max-iteration ceiling or
  custom stop condition. Useful for revise-until-confidence patterns.

The result is a single object that walks like one agent and runs the
whole pipeline.

## When to use

- You can describe the flow in one sentence: "A then B then C".
- The fan-out is symmetric (all branches do similar work).
- You don't need cycles — use [StateGraph](graph.md) for that.

## Tutorial

[`tutorial_25_composition.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_25_composition.py).

## Source

`src/locus/agent/composition.py`.
