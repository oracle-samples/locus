# StateGraph

`StateGraph` is the explicit-control-flow shape: nodes do work, edges
decide what runs next, and state flows through. It supports cycles
(retry-until-confidence), conditional branches, and subgraphs.

```python
from locus.multiagent import StateGraph

graph = StateGraph(state_schema=ResearchState)

graph.add_node("plan", plan_agent)
graph.add_node("research", research_agent)
graph.add_node("write", write_agent)
graph.add_node("review", review_agent)

graph.add_edge("plan", "research")
graph.add_edge("research", "write")
graph.add_conditional_edges(
    "review",
    lambda state: "write" if state.confidence < 0.8 else END,
)
graph.add_edge("write", "review")

result = graph.compile().run_sync({"prompt": "Write a launch brief."})
```

State is a typed value object (`ResearchState` here) with custom
**reducers** controlling how each node's output merges into shared
fields. Edges can be **static** (always go from A to B) or
**conditional** (a function of state picks the next node).

## Features

- **Cycles** — `add_conditional_edges` can route back to an earlier
  node. Combine with a [termination](../termination.md) condition to
  guarantee progress.
- **Subgraphs** — a node can be another compiled graph. Encapsulate
  sub-workflows.
- **Send / SendBatch** — fan-out to N copies of a node with different
  inputs (map/reduce; see [Functional](functional.md)).
- **RetryPolicy** / **CachePolicy** per node — retry on transient
  errors, cache deterministic outputs.
- **Mermaid** visualisation — `graph.compile().get_mermaid()` for a
  drop-in diagram.

## When to use

- The flow has cycles (review-loop, retry, refine-until-confidence).
- You want explicit, inspectable control flow.
- You need per-node retry / cache policies.

## When not to use

- The flow is a straight pipe → use [Composition](composition.md).
- You don't know the flow at design time; agents should self-organise →
  use [Swarm](swarm.md).

## Tutorials

- [`tutorial_06_basic_graph.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_06_basic_graph.py)
- [`tutorial_07_conditional_routing.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_07_conditional_routing.py)
- [`tutorial_08_state_reducers.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_08_state_reducers.py)
- [`tutorial_35_graph_advanced.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_35_graph_advanced.py)

## Source

`src/locus/multiagent/graph.py`.
