# Functional API

The functional API is locus's "agent as a task" shape — `@task` and
`@entrypoint` decorators, plus the `Send` / `SendBatch` primitives for
map/reduce.

```python
import asyncio
from locus.multiagent.functional import task, entrypoint

@task
async def vet_vendor(vendor: dict) -> dict:
    """Run an agent to score one vendor."""
    return await compliance_agent.run(f"Vet {vendor['name']}.")

@entrypoint
async def vet_all(vendors: list[dict]) -> list[dict]:
    return await asyncio.gather(*[vet_vendor(v) for v in vendors])

scored = vet_all.run_sync(catalogue)
```

`@task` and `@entrypoint` adapt agent runs into the regular asyncio
universe — fan out with `asyncio.gather`, retry with `tenacity`,
schedule with `asyncio.create_task`, and so on. For graph-based
fan-out (map/reduce) the `Send` primitive from `locus.core.send`
lives inside [StateGraph](graph.md).

## Why this shape

- **Pythonic.** If you already think in `asyncio.gather`, this is the
  same shape with agents as tasks.
- **Composable.** Tasks can call other tasks; entrypoints can be tasks
  for higher-level entrypoints.
- **Per-task retry / cache** policies via decorator args.

## When to use

- You want fan-out and merge without drawing a graph.
- The work is naturally framed as functions over inputs.
- You like `async def` and want agents to fit that shape.

## Tutorial

[`tutorial_36_functional_api.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_36_functional_api.py).

## Source

`src/locus/multiagent/functional.py`.
