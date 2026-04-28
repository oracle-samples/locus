# Multi-agent

One metaphor for multi-agent systems is wrong because there are seven
of them. Different problems want different shapes. locus ships all
seven, sharing one `Agent` class and one event type — so you can mix
them in a single process and stream events from any of them in the
same loop.

| Pattern | Best for | Source |
|---|---|---|
| [Composition](multi-agent/composition.md) | Linear chains; fan-out + merge | `src/locus/agent/composition.py` |
| [Orchestrator + Specialists](multi-agent/orchestrator.md) | Router decides which expert handles each sub-task | `src/locus/multiagent/orchestrator.py` |
| [Swarm](multi-agent/swarm.md) | Peer-to-peer task queue with `SharedContext` | `src/locus/multiagent/swarm.py` |
| [Handoff](multi-agent/handoff.md) | Explicit role transfers carrying conversation history | `src/locus/multiagent/handoff.py` |
| [StateGraph](multi-agent/graph.md) | DAG with cycles, conditional edges, subgraphs | `src/locus/multiagent/graph.py` |
| [Functional](multi-agent/functional.md) | `Send` / `SendBatch` for map/reduce | `src/locus/multiagent/functional.py` |
| [A2A protocol](multi-agent/a2a.md) | Cross-runtime messaging via `AgentCard` | `src/locus/a2a/` |

## Picking a shape

```text
                 do agents need to talk to each other across processes?
                 ┌──── yes ──────► A2A
                 │
need explicit ───┤
control flow?    │      ── linear with optional fan-out ──► Composition
                 │      ── one router + N experts ────────► Orchestrator
                 │      ── DAG with cycles + branches ────► StateGraph
                 │      ── functional map/reduce ─────────► Functional
                 │
                 │
no — let agents ─┤
self-organise    │      ── shared queue, peer-to-peer ────► Swarm
                 │      ── one agent picks the next ──────► Handoff
```

Use **Composition** when you can write the flow as a linear function
with maybe a fan-out. Use **StateGraph** when the flow has cycles
(retry, loop until-confidence). Use **Orchestrator** when one agent
should decide which specialist runs. Use **Swarm** when no agent
should — they pull from a shared queue. Use **Handoff** when the
hand-back of a single conversation matters (escalation desks).

## Shared event stream

All seven patterns produce the same events. A consumer loop can stream
across patterns:

```python
async for event in pipeline.run("Plan Q3"):
    match event:
        case ToolStartEvent(tool_name=n, agent_name=a):
            print(f"{a} → {n}")
        case TerminateEvent(final_message=m, agent_name=a):
            print(f"{a} done: {m}")
```

`agent_name` is set on every event so you can attribute output to the
specialist that produced it.

## Tutorials

- [`tutorial_11_swarm_multiagent.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_11_swarm_multiagent.py)
- [`tutorial_16_agent_handoff.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_16_agent_handoff.py)
- [`tutorial_17_orchestrator_pattern.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_17_orchestrator_pattern.py)
- [`tutorial_25_composition.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_25_composition.py)
- [`tutorial_34_a2a_protocol.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_34_a2a_protocol.py)
- [`tutorial_35_graph_advanced.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_35_graph_advanced.py)
- [`tutorial_36_functional_api.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_36_functional_api.py)
