# Tutorial 25: Agent Composition — Sequential, Parallel, and Loop Pipelines

This tutorial covers:

- SequentialPipeline: chain agents in order, output feeds next
- ParallelPipeline: run agents concurrently, merge results
- LoopAgent: iterate until a condition is met
- Convenience functions: sequential(), parallel(), loop()

Prerequisites:

- Configure model via environment variables (see examples/.env.example)

Difficulty: Intermediate

## Source

```python
--8<-- "examples/tutorial_25_composition.py"
```
