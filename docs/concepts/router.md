# Router — bounded graph generation

`locus.router` is a meta-orchestration layer on top of locus's existing
primitives. It decomposes a natural-language request into a typed
`GoalFrame`, then deterministically picks a `Protocol` and compiles it
onto a real `Agent` / `SequentialPipeline` / `Orchestrator` from the
standard locus toolkit.

The contribution is the *layer*, not the primitives — every router
execution is just a normal locus orchestration that you can already
inspect, replay, and extend.

## Why a routing layer

Frameworks tend to pick one extreme:

- **LangGraph** — you author the topology by hand. Predictable, but
  every new shape is more code.
- **CrewAI / free-form agent swarms** — the LLM picks the topology. As
  flexible as the model, as fragile as the model.

`locus.router` splits the difference: the LLM produces *only* a typed
`GoalFrame`; the rest of the pipeline is rule-based. You get adaptive
routing without giving the model the steering wheel.

## The five layers

```
┌────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ user input │ ──► │ Goal Frame      │ ──► │ Protocol        │
└────────────┘     │ extraction      │     │ Registry        │
                   │ (typed Pydantic)│     │ (deterministic) │
                   └─────────────────┘     └────────┬────────┘
                                                    │
                                                    ▼
                                       ┌────────────────────────┐
                                       │ Policy Gate (allow /   │
                                       │ require_approval /     │
                                       │ deny)                  │
                                       └────────────┬───────────┘
                                                    │
                                                    ▼
                                       ┌────────────────────────┐
                                       │ Cognitive Compiler     │
                                       │ — emits a real         │
                                       │ Agent / Pipeline /     │
                                       │ Orchestrator           │
                                       └────────────┬───────────┘
                                                    │
                                                    ▼
                                       ┌────────────────────────┐
                                       │ Runnable.execute()     │
                                       │ → RunnableResult       │
                                       └────────────────────────┘
```

### 1. GoalFrame — the typed contract

```python
from locus import GoalFrame, TaskType, Risk, Complexity

frame = GoalFrame(
    primary_goal=TaskType.DIAGNOSE,
    domain="observability",
    complexity=Complexity.HIGH,
    risk=Risk.MEDIUM,
    required_capabilities=["metric_probe", "alert_list"],
)
```

The LLM extractor — a standard locus
`Agent(model=..., output_schema=GoalFrame)` — fills exactly this
schema. It does *not* author orchestration topology.

### 2. Protocol Registry — deterministic selection

```python
from locus.router import ProtocolRegistry, builtin_protocols

protocols = ProtocolRegistry()
protocols.register_many(builtin_protocols())

chosen = protocols.select(frame, available_capabilities={"metric_probe", "alert_list"})
# chosen.id == "specialist_fanout"
```

Selection filters on `handles ∋ primary_goal`,
`risk_max ≥ frame.risk`, and `requires_capabilities ⊆ available`,
then ranks candidates by complexity-fit + cost. It never asks the LLM.

### 3. CapabilityIndex — view over `ToolRegistry`

```python
from locus.router import CapabilityIndex
from locus.tools.registry import create_registry

tools = create_registry(kb_search, get_metric, list_alerts)
caps = CapabilityIndex(tools)
caps.annotate(
    "metric_probe",
    tool_name="get_metric",
    description="Latest value for a named metric.",
    domain="observability",
)
```

The index is an **overlay**, not a parallel registry — the underlying
`Tool` still lives in `ToolRegistry`. Capabilities just add the
domain + risk metadata that the router needs.

### 4. PolicyGate — risk + approval

```python
from locus.router import PolicyGate, Risk

gate = PolicyGate(
    max_risk=Risk.HIGH,                # nothing above HIGH allowed
    require_approval_above=Risk.MEDIUM,  # HIGH-risk frames need approval
)
verdict = gate.check(frame, chosen)
# verdict.allow / verdict.require_approval / verdict.reason
```

The gate produces one of three verdicts. Approval-flagged runnables
are wrapped with a callback that the workbench's interrupt UI (or your
own approval flow) can drive.

### 5. CognitiveCompiler — composition, not codegen

```python
from locus.router import CognitiveCompiler, Router

compiler = CognitiveCompiler(
    protocols=protocols,
    capabilities=caps,
    policy=gate,
    model=model,
)
router = Router(extractor=extractor, compiler=compiler)
result = await router.dispatch("Diagnose the checkout slowdown.")
print(result.protocol_id, result.text)
```

The compiler instantiates a real locus primitive and wraps it in a
`Runnable` adapter so call sites get a single shape
(`async execute(task) -> RunnableResult`) regardless of which protocol
fired.

## Built-in protocols

The eight builtins span the cardinal orchestration shapes.
`primary_for` (a strict subset of `handles`) names the task types each
protocol is the **canonical** choice for — that flag breaks ties in
the registry's ranking.

| `Protocol.id` | Compiled shape | `handles` | `primary_for` |
|---|---|---|---|
| `direct_response` | `Agent` (single call) | `ANSWER`, `EXPLAIN`, `RESEARCH` | `ANSWER`, `EXPLAIN` |
| `plan_execute_validate` | `SequentialPipeline([planner, executor, validator])` | `PLAN`, `BUILD`, `MODIFY`, `GENERATE_CODE`, `REMEDIATE` | `PLAN`, `BUILD`, `MODIFY` |
| `specialist_fanout` | `ParallelPipeline` of N tool-bound `Agent`s | `DIAGNOSE`, `COMPARE`, `MONITOR`, `COORDINATE`, `RESEARCH` | `DIAGNOSE`, `MONITOR`, `RESEARCH` |
| `debate` | `ParallelPipeline` of 2 debaters + a judge `Agent` | `COMPARE`, `RESEARCH` | `COMPARE` |
| `codegen_test_validate` | `LoopAgent` (stops on `PASS`) | `GENERATE_CODE`, `BUILD` | `GENERATE_CODE` |
| `approval_gated_execution` | Single `Agent` wrapped in an approval interrupt | `REMEDIATE`, `MODIFY`, `ESCALATE` | `ESCALATE`, `REMEDIATE` |
| `a2a_delegate` | `A2AClient.invoke` against a remote endpoint | `COORDINATE`, `ESCALATE` | *(opt-in only)* |
| `handoff_chain` | `SequentialPipeline` of one-tool `Agent`s | `PLAN`, `RESEARCH`, `COORDINATE` | `COORDINATE` |

Note: the `specialist_fanout` and `handoff_chain` builders use real
`Agent` instances (not the native `Specialist` / `HandoffAgent`)
because those primitives execute a single `model.complete()` and don't
loop on tool calls — so models that say "I'll call the tool" never
actually invoke it. The `Agent` loop runs the full tool cycle.

## Ranking — how the registry picks one protocol

When more than one protocol matches a frame, `_rank_key` layers four
signals (lower wins each layer):

1. **Distance** — how close the protocol's `cost` matches `frame.complexity`. A LOW-complexity request never gets a HIGH-cost protocol just because that protocol claims to be canonical for the goal type.
2. **Canonical** — `0` if `frame.primary_goal in protocol.primary_for`, else `1`. Breaks distance ties: when two protocols both fit the complexity, the one designed for the specific goal wins.
3. **Cost** — lower-cost protocols win at the next tier.
4. **Handles count** — fewer = more specific; final tiebreaker.

## Skills integration

Skills (`SKILL.md` packages following the
[AgentSkills.io](https://agentskills.io) spec) attach to every Agent
the compiler emits, scoped to `frame.domain`. The agent's
`SkillsPlugin` does the L1 / L2 / L3 progressive disclosure at
runtime — the catalog appears in the system prompt; the agent calls
the `skills` tool to load full instructions.

```python
from locus.router import SkillIndex
from locus.skills import Skill

skills = SkillIndex()
for s in Skill.from_directory("./examples/skills"):
    # Tag each skill with the domain it applies to. Skills registered
    # without a domain ("global") appear in every domain's catalog.
    skills.register(s, domain=s.metadata.get("domain", ""))

compiler = CognitiveCompiler(
    protocols=protocols,
    capabilities=caps,
    policy=gate,
    model=model,
    skills=skills,
)
```

When a user dispatches a request with `domain="observability"`, every
emitted Agent (planner / executor / validator for
`plan_execute_validate`; each fan-out leg for `specialist_fanout`;
etc.) sees the observability-tagged skills catalog and can activate
any one of them on demand.

## A2A delegation

`a2a_delegate` is the only builtin protocol that's **opt-in only**:
its `primary_for` list is empty, so the registry never picks it
canonically. To enable it, configure the remote endpoint at compile
time:

```python
compiler = CognitiveCompiler(
    protocols=protocols,
    capabilities=caps,
    policy=gate,
    model=model,
    a2a_endpoint="https://remote-agent.example.com",
)
```

The compiler passes the endpoint into `BuilderContext`; the builder
constructs an `A2AClient` and wraps it in an `A2ARunnable`. Without an
endpoint, picking the protocol raises `RuntimeError` — the registry
won't reach that path under default ranking.

## Custom protocols

Build your own by writing a builder function and registering it:

```python
from locus.router import Protocol, TaskType, Risk

def _my_builder(frame, capabilities, ctx):
    ...  # return a Runnable
    return wrap_pipeline(my_pipeline, "my_protocol", frame)

protocols.register(
    Protocol(
        id="my_protocol",
        description="...",
        handles=[TaskType.RESEARCH],
        risk_max=Risk.MEDIUM,
        builder=_my_builder,
    )
)
```

The same `Router` instance can serve multiple domains (observability,
codegen, support) by swapping `CapabilityIndex` content — protocols
themselves are domain-agnostic.

## See also

- Tutorial: [`examples/tutorial_51_cognitive_router.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_51_cognitive_router.py)
- API reference: `locus.router` (`GoalFrame`, `Protocol`,
  `ProtocolRegistry`, `PolicyGate`, `CognitiveCompiler`, `Router`,
  `RunnableResult`).
