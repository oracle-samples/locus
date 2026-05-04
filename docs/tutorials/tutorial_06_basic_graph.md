# Tutorial 06: Introduction to StateGraph

This tutorial covers:

- What is a StateGraph and when to use it
- Creating nodes and edges
- Executing a simple graph
- Understanding state flow

Prerequisites: Tutorial 05 (Agent Hooks)
Difficulty: Intermediate

When to use StateGraph vs Agent:

- Agent: Single LLM with tools, ReAct loop, simple tasks
- StateGraph: Complex workflows, multiple steps, conditional logic,
              human-in-the-loop, multi-agent coordination

## Source

```python
--8<-- "examples/tutorial_06_basic_graph.py"
```
