---
hide:
  - navigation
  - toc
---

<div class="locus-hero" markdown>
<div class="locus-hero__copy" markdown>

# Build AI workflows that <span class="accent">actually ship</span>

**Oracle Generative AI · Multi-Agent · Reasoning · Orchestrator SDK.**

Spin up a **swarm** of specialists. Hand a conversation off across an
**escalation desk**. Run an **orchestrator** of experts in parallel.
Wire up a **state graph** that loops until confident. Mesh agents
**across processes** with A2A. Or just ship one self-correcting agent
that knows when to stop.

Six multi-agent shapes. One Oracle-native runtime. Every model on OCI
the day it lands. The agent stack you'd actually let near a credit
card.

[See what you can build](#what-you-can-build){ .md-button .md-button--primary }
[GitHub](https://github.com/oracle-samples/locus){ .md-button }

```bash
pip install "locus[oci]"
```

*Built inside Oracle. Used in production. Open to everyone.*

</div>

<div class="locus-hero__code" markdown>

```python title="travel_concierge.py"
from locus import Agent
from locus.tools.decorator import tool
from locus.memory.backends import OCIBucketBackend
from locus.core.termination import (
    MaxIterations, ToolCalled, ConfidenceMet,
)

@tool
def search_flights(origin: str, destination: str, date: str) -> list[dict]:
    """Search the GDS for available flights."""
    return gds.search(origin, destination, date)

@tool(idempotent=True)
def book_flight(flight_id: str, customer_id: str) -> dict:
    """Book a flight. Re-fires return the cached receipt."""
    return billing.charge_and_book(flight_id, customer_id)

agent = Agent(
    model="oci:openai.gpt-5.5",
    tools=[search_flights, book_flight],
    system_prompt="You are a travel concierge. Find a flight, then book it.",
    reflexion=True,                                 # self-correct mid-run
    checkpointer=OCIBucketBackend(                  # survive every restart
        bucket="locus-threads",
        namespace="<your-namespace>",
    ),
    termination=(
        ToolCalled("book_flight") & ConfidenceMet(0.9)
    ) | MaxIterations(8),
)

result = agent.run_sync(
    "Book a flight from JFK to NRT on 2026-05-04 for customer C-42.",
    thread_id="th-c42-jfk-nrt",                     # resumable conversation
)
print(result.message)
# → Booked AA-181 (JFK→NRT, 2026-05-04). Confirmation BK-58291.
```

</div>
</div>

## What you can build

Six concrete workflows. All of them ship in production with locus
today. None of them require a graph editor, a YAML DAG, or a
separate orchestration platform.

### Approval workflows that don't double-fire

A vendor PO comes in. Procurement and Compliance debate it against
your live Oracle 26ai catalogue. They reach a recommendation. A human
clicks `[y/N]`. The Approval Officer fires `submit_po` and
`email_cfo` — once, even if the model retries the same call three
times.

> *Procurement and Compliance disagree on three of nine vendors. The
> human approves two. Submit + email fire exactly once. Your CFO is
> happy.*

### Research crews that catch their own mistakes

An agent reads, summarises, and fact-checks. **Grounding**
auto-verifies every claim against the source it cited. When a claim
fails grounding the agent goes back and re-reads. **Reflexion**
spots loops on wrong premises before they cost you ten turns of
tokens. You get cited, grounded answers — not hallucinated narratives.

### Customer support that survives every deploy

Triage decides whether the conversation needs Billing or Shipping.
The whole transcript hands over. The customer sees one continuous
reply. The conversation thread is checkpointed to OCI Object Storage,
so a redeploy mid-chat doesn't lose context. The customer doesn't
have to re-explain.

### Autonomous workflows that stop when they should

Compose stop conditions like algebra:

```python
terminate = (ToolCalled("submit") & ConfidenceMet(0.9)) | MaxIterations(15)
```

The loop stops when the work is actually done — not when the budget
runs out, not when the agent gives up halfway. Inspect, unit-test,
audit; termination is just data.

### Multi-agent meshes across teams and processes

Your research agent calls a finance agent on another team's service
over **A2A**. They share one event stream. They discover each other
by capability tag, not URL. You ship one agent at a time, on your
team's schedule, in your team's repo — and they still talk.

### Agents that ship to your users on day one

`AgentServer` is a drop-in FastAPI app: `POST /invoke` for synchronous
runs, `POST /stream` for SSE-streamed events, `X-Session-ID` for
per-user conversations. Native to Oracle Generative AI — every model
the day OCI ships it. Two transports, one auth surface, zero glue
between laptop and production.

## The locus agent loop

Every locus agent runs the same four-node loop —
**Think → Execute → Reflect → Terminate** — with one router deciding
transitions and one immutable state value flowing through.

![locus agent loop — Think → Execute → Reflect → Terminate, with idempotent dedupe at Execute, Reflexion and Causal at Reflect, and composable termination algebra at Terminate](img/agent-loop.svg)

- **Think** — the model decides the next action or the final answer.
  Streams reasoning + tokens.
- **Execute** — runs the tool calls Think returned, in parallel.
  Tools tagged `@tool(idempotent=True)` are deduped against the
  run's tool-execution history, so retries return the cached
  receipt instead of re-firing the body. Booking, billing, paging —
  safe by design.
- **Reflect** — runs on cadence, on tool error, or when loop-detection
  trips. Reflexion evaluates the agent's last step; **Grounding**
  scores claims against tool results; **Causal** builds a
  cause-effect graph from the trace. The router routes Reflect's
  judgment back into the next Think.
- **Terminate?** — typed stop conditions composable with `|` and `&`.
  Inspect, unit-test, log; termination is just data.

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

## Workflows you can build

Six coordination patterns in-process — plus **A2A** for cross-process
agent meshes. The same `Agent` class composes into all of them. Mix
them in one process; stream events from any of them in the same
`match` block.

<div class="grid cards" markdown>

- :material-arrow-right-thick:{ .lg .middle } **Composition**

    ---

    Linear chain · fan-out + merge. The simplest shape — describe the
    flow as a function.

    [Composition →](concepts/multi-agent/composition.md)

- :material-account-supervisor:{ .lg .middle } **Orchestrator + Specialists**

    ---

    One coordinator decides which expert handles each sub-task.
    Specialists run in parallel.

    [Orchestrator →](concepts/multi-agent/orchestrator.md)

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

| | |
|---|---|
| **🧠 Reasoning** | Reflexion · Grounding · Causal — one line on `Agent(...)`. |
| **🤝 Multi-agent** | Composition · Orchestrator · Swarm · Handoff · StateGraph · Functional — six in-process patterns, plus A2A for cross-process meshes. |
| **🛡 Idempotent tools** | `@tool(idempotent=True)`. The model can't double-charge. |
| **💾 Durable memory** | Nine native checkpointer backends — OCI Object Storage, Oracle 26ai, PostgreSQL, OpenSearch, Redis, SQLite, HTTP, file, in-memory. |
| **🔎 RAG on your data** | Seven vector stores · OCI Cohere + OpenAI embeddings · multimodal (PDF + OCR + audio). |
| **🧩 Skills + Playbooks** | Filesystem-first capability disclosure + declarative step plans. |
| **📡 Streaming + Server** | Typed events for `match` consumers · SSE · drop-in FastAPI `AgentServer`. |
| **🪝 Hooks** | Logging · Telemetry · ModelRetry · Guardrails · Steering. |
| **🪙 MCP both ways** | `MCPClient` consumes external servers. `LocusMCPServer` exposes locus tools. |
| **📊 Evaluation** | `EvalCase` / `EvalRunner` / `EvalReport` regression suites. |
| **🛂 Termination algebra** | Eight composable stop conditions. `Or` and `And` compose them. |
| **🧰 Models** | OCI GenAI native (V1 + SDK) · OpenAI · Anthropic · Ollama. |

## Hello, agent

```python
from locus import Agent
from locus.tools.decorator import tool

@tool(idempotent=True)
def book_flight(flight_id: str, customer_id: str) -> dict:
    """Book a flight. Idempotent — re-fires return the cached receipt."""
    return billing.charge_and_book(flight_id, customer_id)

agent = Agent(
    model="oci:openai.gpt-5.5",
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
Officer, the human approves, idempotent writes fire — is in
[`examples/demos/po_approval/`](https://github.com/oracle-samples/locus/tree/main/examples/demos/po_approval).

## Introspect

locus is small enough to read end-to-end. Every capability has its own
concept page on this site, and every page links straight to its source
path. No magic, no hidden registries, no import-time side-effects.

| Capability | Source |
|---|---|
| Loop nodes (Think · Execute · Reflect) | [`src/locus/loop/`](https://github.com/oracle-samples/locus/tree/main/src/locus/loop) |
| Termination algebra | [`src/locus/core/termination.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/core/termination.py) |
| Tools, decorator, registry | [`src/locus/tools/`](https://github.com/oracle-samples/locus/tree/main/src/locus/tools) |
| Memory · 9 backends | [`src/locus/memory/`](https://github.com/oracle-samples/locus/tree/main/src/locus/memory) |
| Multi-agent · 6 in-process patterns | [`src/locus/multiagent/`](https://github.com/oracle-samples/locus/tree/main/src/locus/multiagent) |
| A2A · cross-process protocol | [`src/locus/a2a/`](https://github.com/oracle-samples/locus/tree/main/src/locus/a2a) |
| Models · provider registry | [`src/locus/models/`](https://github.com/oracle-samples/locus/tree/main/src/locus/models) |
| RAG · embedders + stores | [`src/locus/rag/`](https://github.com/oracle-samples/locus/tree/main/src/locus/rag) |
| Reasoning · Reflexion + Grounding + Causal | [`src/locus/reasoning/`](https://github.com/oracle-samples/locus/tree/main/src/locus/reasoning) |
| Hooks · 5 built-ins | [`src/locus/hooks/`](https://github.com/oracle-samples/locus/tree/main/src/locus/hooks) |
| Streaming · events + SSE | [`src/locus/streaming/`](https://github.com/oracle-samples/locus/tree/main/src/locus/streaming) |
| Server · FastAPI wrapper | [`src/locus/server/`](https://github.com/oracle-samples/locus/tree/main/src/locus/server) |
| Skills · AgentSkills.io | [`src/locus/skills/`](https://github.com/oracle-samples/locus/tree/main/src/locus/skills) |
| Playbooks · enforcer | [`src/locus/playbooks/`](https://github.com/oracle-samples/locus/tree/main/src/locus/playbooks) |
| Evaluation harness | [`src/locus/evaluation/`](https://github.com/oracle-samples/locus/tree/main/src/locus/evaluation) |
| MCP client + server | [`src/locus/integrations/mcp/`](https://github.com/oracle-samples/locus/tree/main/src/locus/integrations/mcp) |
| A2A protocol | [`src/locus/a2a/`](https://github.com/oracle-samples/locus/tree/main/src/locus/a2a) |

Read the [concepts](concepts/agent.md) for the *why*; read the
[API reference](api/agent.md) for the *what*.

## Learn locus in an afternoon

The [`examples/`](https://github.com/oracle-samples/locus/tree/main/examples)
tree is **37 tutorials** plus **3 end-to-end demos**. Every tutorial
is one runnable file and adds exactly one idea on top of the previous.

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

The six in-process patterns plus A2A:
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

### Track 5 — production (12, 19–21, 26–30, 33, 35, 37)

[MCP](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_12_mcp_integration.py) ·
[Guardrails](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_19_guardrails_security.py) ·
[Checkpoint backends](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_20_checkpoint_backends.py) ·
[SSE streaming](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_21_sse_streaming.py) ·
[Evaluation](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_26_evaluation.py) ·
[Hooks advanced](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_27_hooks_advanced.py) ·
[Agent Server](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_28_agent_server.py) ·
[Model providers](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_29_model_providers.py) ·
[Guardrails advanced](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_30_guardrails_advanced.py) ·
[Steering](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_33_steering.py) ·
[Graph advanced](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_35_graph_advanced.py) ·
[Termination](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_37_termination.py).

### End-to-end demos

| Demo | What it shows |
|---|---|
| [`po_approval/`](https://github.com/oracle-samples/locus/tree/main/examples/demos/po_approval) | Three agents (Procurement / Compliance / Approval Officer) debate a vendor PO against a live Oracle 26ai catalogue. Idempotent writes. Human consent gate. |
| [`oracle_26ai/`](https://github.com/oracle-samples/locus/tree/main/examples/demos/oracle_26ai) | Full Oracle stack — OCI GenAI + Oracle 26ai vectors + skills + Reflexion + idempotent submit + checkpoints to OCI Object Storage. |
| [`trip_team/`](https://github.com/oracle-samples/locus/tree/main/examples/demos/trip_team) | Same multi-agent shape on a Tokyo travel corpus — three personas, one orchestrator, one durable thread. |

## Then deploy

When the agent is ready, ship it. `AgentServer` is a drop-in FastAPI
wrapper; no extra glue.

```python
from locus.server import AgentServer

server = AgentServer(agent=my_agent, cors_origins=["https://app.example.com"])
server.run(host="0.0.0.0", port=8080)
```

You get out of the box:

- `POST /invoke` — synchronous run, full `RunResult` JSON.
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
