---
hide:
  - navigation
  - toc
---

<div class="locus-hero" markdown>
<div class="locus-hero__copy" markdown>

# Multi-agent workflows built for <span class="accent">production.</span>

locus picks the right coordination strategy for any task — and runs it production-safe.

<div class="locus-stat-strip"><a href="concepts/multi-agent.md">multi-agent</a> &nbsp;·&nbsp; <a href="concepts/router.md">cognitive protocol</a> &nbsp;·&nbsp; <a href="concepts/agent-loop.md">human-in-the-loop</a> &nbsp;·&nbsp; <a href="concepts/reasoning.md">self-evaluating</a></div>

- **Safe by default** — `@tool(idempotent=True)` fires exactly once per `(name, args)`, even after retries or restarts
- **Composable stops** — typed conditions composed with `&` and `|`; inspectable, unit-testable, serialisable
- **Full observability** — opt-in `EventBus` streams 40+ event types; one hook exports OpenTelemetry traces

[Get started](#six-things-you-can-ship){ .md-button .md-button--primary }
[GitHub](https://github.com/oracle-samples/locus){ .md-button }

```bash
pip install "locus[oci]"   # OCI GenAI · OpenAI · Anthropic · Ollama
```

Built inside Oracle · Used in production · Open source

</div>

<div class="locus-hero__code" markdown>

```python
from locus import Agent, tool
from locus.observability import run_context, get_event_bus

@tool(idempotent=True)
def get_metric(name: str) -> float:
    """Return the current value of a named SRE metric."""
    return monitoring.read(name)

@tool(idempotent=True)
def page_oncall(reason: str) -> str:
    """Page the on-call engineer. Fires exactly once per reason."""
    return pager.send(reason)

agent = Agent(
    model="oci:openai.gpt-5",
    tools=[get_metric, page_oncall],
    reflexion=True,   # self-evaluates every turn
)

async with run_context() as rid:
    result = agent.run_sync(
        "p99 latency spiked — investigate and page if critical."
    )

    async for ev in get_event_bus().subscribe(rid):
        match ev.event_type:
            case "agent.think":
                print("💭", ev.data["reasoning_preview"])
            case "agent.tool.started":
                print("🔧", ev.data["tool_name"])
            case "agent.tokens.used":
                print("🪙", ev.data["total_tokens"], "tokens")
            case "agent.terminate":
                print("✓", ev.data["final_message_preview"])
```

</div>
</div>

## Six things you can ship

<div class="grid cards locus-feature-cards" markdown>

- :material-graph:{ .lg .middle } **Multi-agent coordination**

    ---
    Run agents in parallel, sequentially, or adversarially. Hand off between specialists. Connect across services. Eight named patterns, all using the same `Agent` class.

- :material-routes:{ .lg .middle } **Cognitive router**

    ---
    Describe the goal in plain language. locus automatically selects the right coordination pattern — parallel research, sequential pipeline, adversarial debate, approval gate — and assembles the agents.

- :material-shield-check:{ .lg .middle } **Safe by design**

    ---
    Tools never fire twice for the same call, even if the model retries or the workflow restarts mid-run. Stop conditions are typed rules you can unit-test. Workflows checkpoint themselves and resume after failures.

- :material-chart-timeline-variant:{ .lg .middle } **Grounded reasoning**

    ---
    Agents score their own reasoning every turn and verify each claim against the tool result that produced it. Unverified claims get flagged or dropped before they reach the user.

- :material-eye:{ .lg .middle } **Full observability**

    ---
    Every meaningful step — agent thinking, tool calls, token usage, routing decisions — emits a typed event. Subscribe to any live run or export everything to OpenTelemetry with one hook.

- :material-rocket-launch:{ .lg .middle } **Production server**

    ---
    Two lines of code turn any agent into a deployed API — streaming responses, per-user thread isolation, and persistent conversation history out of the box.

</div>

### Let locus pick the right coordination strategy

Describe your goal in plain language. locus classifies the task, selects the best coordination pattern, and assembles the right agents — automatically. You don't choose between parallel vs sequential; locus does.

```python
from locus.router import (
    Router, CognitiveCompiler, ProtocolRegistry,
    builtin_protocols, CapabilityIndex, PolicyGate, GoalFrame,
)

# Register the 8 built-in protocols.
registry = ProtocolRegistry()
registry.register_many(builtin_protocols())

compiler = CognitiveCompiler(
    protocols=registry,
    capabilities=caps,          # annotated ToolRegistry view
    policy=PolicyGate(          # risk thresholds
        max_risk=Risk.HIGH,
        require_approval_above=Risk.MEDIUM,
    ),
    model=model,
)
router = Router(
    extractor=Agent(model=model, output_schema=GoalFrame),
    compiler=compiler,
)

result = await router.dispatch("Diagnose the checkout API slowdown.")
print(result.protocol_id)   # "specialist_fanout"
print(result.text)          # findings from 3 parallel probes
```

Eight built-in protocols, each mapping to a different runtime shape:

| Protocol | Compiled shape | Canonical for |
|---|---|---|
| `direct_response` | Single `Agent` | `ANSWER`, `EXPLAIN` |
| `plan_execute_validate` | `SequentialPipeline` (planner → executor → validator) | `PLAN`, `BUILD`, `MODIFY` |
| `specialist_fanout` | `ParallelPipeline` of N tool-bound Agents | `DIAGNOSE`, `MONITOR` |
| `debate` | Two debaters + judge `Agent` | `COMPARE` |
| `codegen_test_validate` | `LoopAgent` (stops on `PASS`) | `GENERATE_CODE` |
| `approval_gated_execution` | `Agent` wrapped in approval interrupt | `ESCALATE`, `REMEDIATE` |
| `a2a_delegate` | `A2AClient.invoke` (opt-in only) | — |
| `handoff_chain` | `SequentialPipeline` of one-tool Agents | `COORDINATE` |

→ [Cognitive router — full reference](concepts/router.md) ·
[Tutorial 51: route five distinct tasks](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_51_cognitive_router.py)

### Agents that verify their own answers

Agents can hallucinate. locus catches it. After every response, it scores the reasoning and checks each claim against the actual tool output. Claims that don't hold up get dropped or sent back for re-research before the user ever sees them.

```python
from locus import Agent
from locus.tools.decorator import tool

@tool
def search_web(query: str) -> str:
    """Search the web for facts."""
    return search_api.query(query)

@tool
def read_url(url: str) -> str:
    """Fetch and clean text from a URL."""
    return http.fetch_text(url)

agent = Agent(
    model="oci:openai.gpt-5",
    tools=[search_web, read_url],
    reflexion=True,    # self-evaluate every turn
    grounding=True,    # verify claims against tool results
)

result = agent.run_sync("Summarise the Q3 earnings call. Cite every number.")
print(result.text)
print(f"grounding score: {result.grounding_score:.2f}")
# → grounding score: 0.94 — three claims grounded, one dropped (revenue mix)
```

→ [Reasoning inside the loop](concepts/reasoning.md) ·
[Turn on Reflexion + Grounding in one line](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_14_reasoning_patterns.py)

### No double-booking. No duplicate emails

AI models sometimes retry the same action — after a glitch, an ambiguous result, or a restart. Add one decorator and locus guarantees the action only happens once, no matter how many times the model tries. Book a flight, submit an invoice, page an engineer — safely.

```python
from locus import Agent
from locus.tools.decorator import tool

@tool(idempotent=True)
def submit_po(vendor_id: str, line_items: list[dict]) -> dict:
    """Submit the PO. Re-fires within the run return the cached receipt."""
    return procurement.submit(vendor_id, line_items)

@tool(idempotent=True)
def email_cfo(po_id: str, body: str) -> str:
    """Send the CFO note. Same arguments → same delivery."""
    return mail.send(to="cfo@org.com", subject=f"PO {po_id}", body=body)

agent = Agent(
    model="oci:openai.gpt-5",
    tools=[search_vendors, submit_po, email_cfo],
    system_prompt="Approve a vendor; submit the PO; email the CFO.",
)

result = agent.run_sync("Approve Acme for the $42k laptop refresh.")
# → PO-2847 submitted. CFO emailed once. Three model retries deduped on
#   the (name, kwargs) hash inside the ReAct loop's Execute node.
```

→ [Idempotent tools in the ReAct loop](concepts/idempotency.md) ·
[Walk through a vendor PO with human approval](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_09_human_in_the_loop.py)

### One conversation, many specialists

Pass a task from one specialist agent to another — triage to billing, billing to shipping — while the user sees a single, seamless reply. Each specialist is a separate agent, deployed independently by its own team.

```python
from locus import create_handoff_agent, create_handoff_manager, HandoffReason

triage = create_handoff_agent(
    name="Triage",
    description="Routes incoming customer issues",
    system_prompt="Decide: Billing or Shipping. Then hand off.",
)
billing = create_handoff_agent(
    name="Billing",
    description="Resolves invoices, refunds, charges",
    system_prompt="Resolve the billing issue end-to-end.",
)
shipping = create_handoff_agent(
    name="Shipping",
    description="Tracks orders, reroutes shipments",
    system_prompt="Resolve the shipping issue end-to-end.",
)
triage.can_delegate_to = [billing.id, shipping.id]

desk = create_handoff_manager(
    agents=[triage, billing, shipping],
    max_chain=5,
)
# → [Triage → Billing] "Refunded $129. Confirmation RF-19340."
```

→ [Handoff with chain-of-custody](concepts/multi-agent/handoff.md) ·
[Wire a Triage / Billing / Shipping handoff desk](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_16_agent_handoff.py)

### See everything your agents are doing

Watch every step of every agent run in real time — what it thought, which tools it called, how many tokens it used. Wrap your code in one context manager to turn it on; remove it and there's zero performance cost. Connect to any monitoring system with a single OpenTelemetry hook.

```python
from locus import Agent, tool
from locus.observability import run_context, get_event_bus

@tool
def get_metric(name: str) -> float:
    """Return the current value of a named metric."""
    return monitoring.read(name)

agent = Agent(model="oci:openai.gpt-5", tools=[get_metric])

async with run_context() as rid:
    result = agent.run_sync("What is the p99 latency right now?")

    async for ev in get_event_bus().subscribe(rid):
        match ev.event_type:
            case "agent.think":
                print("💭", ev.data["reasoning_preview"])
            case "agent.tool.started":
                print("🔧", ev.data["tool_name"], ev.data["span_id"])
            case "agent.tool.completed":
                print("   ↳", ev.data["output_preview"])
            case "agent.tokens.used":
                print("🪙", ev.data["total_tokens"], "tokens")
            case "agent.terminate":
                print("✓", ev.data["final_message_preview"])
```

Nine event prefixes, 40+ canonical types.
`subscribe(run_id)` replays history then goes live.
`subscribe_global()` watches all concurrent runs.
Slow consumers get dropped events, never stall the publisher.

→ [Observability — EventBus + agent yield bridge](concepts/observability.md) ·
[SSE event catalogue](concepts/sse-events.md) ·
[Tutorial 52: observability basics](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_52_observability_basics.py)

### Tell agents exactly when to stop

Define precisely when your agent should finish — when a specific tool ran, when it's confident enough, or after a safety cap. Combine rules with `&` and `|`. The conditions are typed objects you can unit-test, inspect, and version-control like any other code.

```python
from locus import Agent
from locus.core.termination import (
    MaxIterations, ToolCalled, ConfidenceMet, TextMention,
)

termination = (
    (ToolCalled("submit_po") & ConfidenceMet(0.9))   # work done + confident
    | TextMention(r"\bDONE\b")                         # …or model says DONE
    | MaxIterations(15)                                # …or safety cap
)

agent = Agent(
    model="oci:openai.gpt-5",
    tools=[search_vendors, submit_po],
    termination=termination,
)

result = agent.run_sync("Approve and submit the laptop PO.")
print(result.stop_reason)
# → ToolCalled('submit_po') and ConfidenceMet(0.92)
```

→ [Termination algebra](concepts/termination.md) ·
[Compose stop conditions like algebra](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_37_termination.py)

### Deploy in two lines of code

Turn any locus agent into a production API in two lines. You get streaming responses, per-user conversation history that no other user can access, and persistent threads across sessions — ready to run on any platform that supports Python.

```python
import os
from locus import Agent
from locus.memory.backends import oci_bucket_checkpointer
from locus.server import AgentServer

agent = Agent(
    model="oci:openai.gpt-5",
    tools=[lookup_invoice, refund],
    checkpointer=oci_bucket_checkpointer(
        bucket_name="support-threads",
        namespace="<your-tenancy>",
    ),
)

server = AgentServer(
    agent=agent,
    api_key=os.environ["LOCUS_SERVER_API_KEY"],
)
server.run(host="0.0.0.0", port=8080)

# $ curl -X POST http://localhost:8080/invoke \
#       -H "Authorization: Bearer $LOCUS_SERVER_API_KEY" \
#       -d '{"prompt":"Refund order ORD-42","thread_id":"user-c42"}'
# → {"message": "Refunded $129. Confirmation RF-19340.", "thread_id": "user-c42"}
```

→ [Agent Server — drop-in FastAPI app](concepts/server.md) ·
[Deploy a locus agent as a FastAPI service](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_28_agent_server.py)

## How every agent runs

Every locus agent runs the same four steps in a loop: decide what to do, do it, check the result, then decide whether to stop. This loop is identical whether you're running a single agent or a fleet of specialists working together.

![locus agent loop — Think → Execute → Reflect → Terminate, with idempotent dedupe at Execute, Reflexion and Causal at Reflect, and composable termination algebra at Terminate](img/agent-loop.svg)

| Node | What it does |
|---|---|
| **Think** | Model decides next action or final answer. Streams reasoning + tokens. |
| **Execute** | Runs tool calls in parallel. `@tool(idempotent=True)` dedupes on `(name, args)` — safe on retry or restart. |
| **Reflect** | Self-evaluates turn quality. **Grounding** scores claims vs tool results. **Causal** traces root cause from the evidence trail. |
| **Terminate?** | Typed stop conditions composed with `\|` and `&`. Inspectable, unit-testable, serialisable. |

```python
from locus.core.termination import MaxIterations, ToolCalled, ConfidenceMet

terminate = (
    ToolCalled("submit_po") & ConfidenceMet(0.9)
) | MaxIterations(10)
```

Every node emits a typed, **write-protected** event. The same stream
powers SSE in `AgentServer`, the OpenTelemetry telemetry hook, the
structured logging hook, and your `async for event in agent.run(...)`
consumer.

[Read the full architecture reference →](concepts/agent-loop.md)

## Eight ways to coordinate agents

From simple parallel research to multi-team handoffs across services. Pick one pattern or combine them — they all use the same `Agent` class and stream into the same event feed.

<div class="grid cards" markdown>

- :material-routes:{ .lg .middle } **Cognitive router**

    ---

    NL → typed `GoalFrame` → deterministic protocol selection →
    compiled `Agent` / `Pipeline` / `Orchestrator`. The LLM fills a
    schema; the registry picks the shape.

    [Cognitive router →](concepts/router.md)

- :material-account-supervisor:{ .lg .middle } **Orchestrator + Specialists**

    ---

    One coordinator decides which expert handles each sub-task.
    Specialists run in parallel.

    [Orchestrator →](concepts/multi-agent/orchestrator.md)

- :material-arrow-right-thick:{ .lg .middle } **Composition**

    ---

    Linear chain · fan-out + merge. The simplest shape — describe the
    flow as a function.

    [Composition →](concepts/multi-agent/composition.md)

- :material-bee-flower:{ .lg .middle } **Swarm**

    ---

    Peer-to-peer task pool with `SharedContext`. Nobody is in charge.
    For open-ended research.

    [Swarm →](concepts/multi-agent/swarm.md)

- :material-account-arrow-right:{ .lg .middle } **Handoff**

    ---

    Escalation desk. The conversation moves with full history; the
    previous owner is out of the loop.

    [Handoff →](concepts/multi-agent/handoff.md)

- :material-graph:{ .lg .middle } **StateGraph**

    ---

    Explicit nodes and edges. Cycles, conditional routing, subgraphs,
    per-node retry/cache.

    [StateGraph →](concepts/multi-agent/graph.md)

- :material-function-variant:{ .lg .middle } **Functional API**

    ---

    `@task` and `@entrypoint` decorators with `Send` / `SendBatch` for
    map/reduce. Pythonic.

    [Functional →](concepts/multi-agent/functional.md)

- :material-lan-connect:{ .lg .middle } **A2A protocol**

    ---

    Cross-process / cross-runtime. Agents advertise capability via
    `AgentCard`; discovered over HTTP.

    [A2A →](concepts/multi-agent/a2a.md)

- :material-puzzle:{ .lg .middle } **Agents as tools**

    ---

    Wrap any agent as a tool another agent can call. Recursive, no
    special API.

    [Composition →](concepts/multi-agent.md)

</div>

## What you get

### Orchestration

| | |
|---|---|
| **🧭 Multi-agent reasoning orchestrator** | Picks one of eight protocols (`direct_response`, `plan_execute_validate`, `specialist_fanout`, `debate`, `codegen_test_validate`, `approval_gated_execution`, `a2a_delegate`, `handoff_chain`) and instantiates the matching locus primitive. The LLM fills a schema; routing is deterministic. |
| **🤝 Multi-agent patterns** | Seven native patterns — Composition, Orchestrator, Swarm, Handoff, StateGraph, Functional, DeepAgent — plus cross-process A2A. Use them directly when you know what you need. |
| **📡 Observability** | Opt-in `EventBus` — one `run_context()` streams 40+ canonical events, no external broker. `TelemetryHook` exports OpenTelemetry traces + metrics to Grafana, Honeycomb, OCI APM. Zero overhead when unused. |

### Agent primitives

| | |
|---|---|
| **🧠 Reasoning** | Reflexion + Grounding as first-class loop nodes. `CausalChain` for root-cause chains. **GSAR** (`arXiv:2604.23366`): four-way claim partition + tiered replanning. |
| **🛂 Termination algebra** | `MaxIterations(10) \| TextMention("DONE") & ConfidenceMet(0.9)` — real Python `__or__`/`__and__` overloads. Greppable, unit-testable, serialisable. |
| **🛡 Idempotent tools** | `@tool(idempotent=True)` dedupes on `(name, args)` inside Execute. No double-charge on model retry or checkpoint resume. |
| **💾 Durable memory** | Four native checkpointers + five storage-backed (PostgreSQL, OpenSearch, Redis, SQLite, Oracle 26ai). |

### Deployment & integration

| | |
|---|---|
| **📡 Streaming + Server** | Typed events for `match` consumers · SSE · drop-in FastAPI `AgentServer`. |
| **🪝 Hooks** | Logging · Telemetry · ModelRetry · Guardrails · Steering. |
| **🔎 RAG** | Seven vector stores · OCI Cohere + OpenAI embeddings · multimodal. |
| **🪙 MCP both ways** | `MCPClient` consumes external servers. `LocusMCPServer` exposes locus tools. |
| **🌐 Multi-modal** | `web_search=`, `web_fetch=`, `image_generator=`, `speech_provider=` on `Agent(...)`. |
| **📊 Evaluation** | `EvalCase` / `EvalRunner` / `EvalReport` regression suites. |
| **🧰 Models** | OCI GenAI (V1 + SDK, 90+ models, OpenAI commercial + xAI Grok) · OpenAI · Anthropic · Ollama. One `get_model()` call, any provider. |

## Hello, agent

```python
from locus import Agent
from locus.tools.decorator import tool

@tool(idempotent=True)
def book_flight(flight_id: str, customer_id: str) -> dict:
    """Book a flight. Idempotent — re-fires return the cached receipt."""
    return billing.charge_and_book(flight_id, customer_id)

agent = Agent(
    model="oci:openai.gpt-5",
    tools=[book_flight],
    system_prompt="You are a travel concierge. Book the flight the user asks for.",
)

print(agent.run_sync("Book TK-12 for customer C-42").message)
```

```text
Booked TK-12 for customer C-42. Confirmation BK-58291.
```

That's the entire interface. The model picks the tool. The tool
charges once. The agent stops.

A three-agent vendor PO approval workflow against a live Oracle 26ai
catalogue — Procurement and Compliance debate, hand off to an Approval
Officer, the human approves, idempotent writes fire — runs end-to-end
in the multi-agent and idempotency tutorials under
[`examples/`](https://github.com/oracle-samples/locus/tree/main/examples).

## Source

locus is small enough to read end-to-end. No magic, no hidden registries, no import-time side-effects. A few entry points:

| What | Where |
|---|---|
| Agent + ReAct loop | [`loop/nodes.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/loop/nodes.py) — `ThinkNode:59`, `ExecuteNode:136`, `ReflectNode:260` |
| Cognitive router | [`router/runtime.py:42`](https://github.com/oracle-samples/locus/blob/main/src/locus/router/runtime.py#L42) → `protocol.py` → `policy.py` → `compiler.py` |
| Multi-agent shapes | [`multiagent/`](https://github.com/oracle-samples/locus/tree/main/src/locus/multiagent) — `orchestrator.py`, `swarm.py`, `handoff.py`, `graph.py`, `functional.py` |
| Observability | [`observability/event_bus.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/observability/event_bus.py) · [`agent/runtime_loop.py:61`](https://github.com/oracle-samples/locus/blob/main/src/locus/agent/runtime_loop.py#L61) (`@_bus_bridge`) |
| Idempotent tools | [`tools/decorator.py:113`](https://github.com/oracle-samples/locus/blob/main/src/locus/tools/decorator.py#L113) · `core/termination.py:39` |
| OCI model transport | [`models/providers/oci/openai_compat.py:163`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/providers/oci/openai_compat.py#L163) |

Full source map → [Capabilities](capabilities.md) · [API reference](api/agent.md)

## Learn locus in an afternoon

The [`examples/`](https://github.com/oracle-samples/locus/tree/main/examples)
tree is **55 progressive tutorials**. Every tutorial is one runnable
file and adds exactly one idea on top of the previous.

### Track 1 — basics (first hour)

| # | What you learn |
|---|---|
| [01 basic agent](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_01_basic_agent.py) | Make an `Agent`, give it a model, run a prompt. |
| [02 agent + tools](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_02_agent_with_tools.py) | Decorate a Python function with `@tool`. The model sees a typed contract. |
| [03 agent memory](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_03_agent_memory.py) | Conversations across runs — checkpointers, `thread_id`. |
| [04 streaming](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_04_agent_streaming.py) | Stream typed events as the agent thinks, calls tools, terminates. |
| [05 hooks](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_05_agent_hooks.py) | Lifecycle hooks — log every model call and every tool result. |

### Track 2 — graphs & state (06–10)

| # | What you learn |
|---|---|
| [06 basic graph](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_06_basic_graph.py) | `StateGraph` — explicit nodes and edges over implicit ReAct. |
| [07 conditional routing](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_07_conditional_routing.py) | Branch on state — `add_conditional_edges`. |
| [08 state reducers](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_08_state_reducers.py) | Custom reducers for accumulating fields across nodes. |
| [09 human in the loop](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_09_human_in_the_loop.py) | Pause the graph for human approval, resume on input. |
| [10 advanced patterns](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_10_advanced_patterns.py) | `Send`, broadcasts, subgraphs — map/reduce on agents. |

### Track 3 — multi-agent (11, 16–18, 25, 34, 36)

The six native patterns plus A2A:
[Swarm](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_11_swarm_multiagent.py) ·
[Handoff](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_16_agent_handoff.py) ·
[Orchestrator](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_17_orchestrator_pattern.py) ·
[Specialists](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_18_specialist_agents.py) ·
[Composition](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_25_composition.py) ·
[A2A](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_34_a2a_protocol.py) ·
[Functional](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_36_functional_api.py).

### Track 4 — reasoning, RAG, skills (13–15, 22–24, 32)

[Structured output](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_13_structured_output.py) ·
[Reasoning patterns](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_14_reasoning_patterns.py) ·
[Playbooks](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_15_playbooks.py) ·
[RAG basics](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_22_rag_basics.py) ·
[RAG providers](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_23_rag_providers.py) ·
[RAG agents](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_24_rag_agents.py) ·
[Skills](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_32_skills.py).

### Track 5 — production (12, 19–21, 26–30, 33, 35, 37–40)

[MCP](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_12_mcp_integration.py) ·
[Guardrails](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_19_guardrails_security.py) ·
[Checkpoint backends](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_20_checkpoint_backends.py) ·
[SSE streaming](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_21_sse_streaming.py) ·
[Evaluation](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_26_evaluation.py) ·
[Hooks advanced](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_27_hooks_advanced.py) ·
[Agent Server](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_28_agent_server.py) ·
[Model providers](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_29_model_providers.py) ·
[Guardrails advanced](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_30_guardrails_advanced.py) ·
[Plugins](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_31_plugins.py) ·
[Steering](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_33_steering.py) ·
[Graph advanced](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_35_graph_advanced.py) ·
[Termination](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_37_termination.py) ·
[Multi-modal providers](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_38_multimodal_providers.py) ·
[GSAR typed grounding](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_39_gsar_typed_grounding.py) ·
[OCI Dedicated AI Cluster (DAC)](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_40_oci_dac.py).

### Track 6 — cognitive router + observability (41, 51–55)

[DeepAgent](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_41_deepagent.py) ·
[Cognitive router](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_51_cognitive_router.py) ·
[Observability basics](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_52_observability_basics.py) ·
[Agent yield bridge](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_53_agent_yield_bridge.py) ·
[EventBus subscriber patterns](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_54_eventbus_subscribers.py) ·
[Full event catalogue](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_55_event_catalogue.py).

## Then deploy

When the agent is ready, ship it. `AgentServer` is a drop-in FastAPI
wrapper; no extra glue.

```python
from locus.server import AgentServer

server = AgentServer(agent=my_agent, cors_origins=["https://app.example.com"])
server.run(host="0.0.0.0", port=8080)
```

You get out of the box:

- `POST /invoke` — synchronous run, full `AgentResult` JSON.
- `POST /stream` — Server-Sent Events of every typed event.
- `GET / DELETE /threads/{id}` — conversation persistence (with a
  checkpointer attached).
- `GET /health` — liveness probe.

Deploys anywhere FastAPI runs:

- **OCI Functions** — serverless, scale to zero.
- **OKE / Container Instances** — `docker build` and ship.
- **OCI Compute** — `uvicorn locus.server:run --port 8080`.
- **Kubernetes / EKS / Cloud Run** — same Dockerfile.

[Read the deploy concept →](concepts/server.md)

---

**Built inside Oracle. Used in production. Open to everyone.**

locus turns hard agentic work — retries that don't double-charge,
state that survives restarts, multi-agent flows that fit the problem,
and reasoning that catches its own mistakes — into ordinary Python
you can reason about, test, and ship.
