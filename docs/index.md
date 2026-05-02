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
over **A2A**. They share one event stream. Each agent advertises an
`AgentCard` that lists its capability tags; the calling agent fetches
the card from a known URL and decides whether to delegate. You ship
one agent at a time, on your team's schedule, in your team's repo —
and they still talk.

### Agents that ship to your users on day one

`AgentServer` is a drop-in FastAPI app: `POST /invoke` for synchronous
runs, `POST /stream` for SSE-streamed events, `GET` / `DELETE
/threads/{id}` for per-thread persistence (scoped to the bearer
principal so two API keys can't read each other's conversations).
Native to Oracle Generative AI — every model the day OCI ships it.
Two transports, one auth surface, zero glue between laptop and
production.

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
| **🧠 Reasoning** | Reflexion + Grounding — one line on `Agent(...)` (`reflexion=True`, `grounding=True`). `CausalChain` for explicit cause-effect chains. **GSAR** typed-grounding layer for safety-critical pipelines: four-way claim partition + three-tier decision (`arXiv:2604.23366`). |
| **🤝 Multi-agent** | Composition · Orchestrator · Swarm · Handoff · StateGraph · Functional — six in-process patterns, plus A2A for cross-process meshes. |
| **🛡 Idempotent tools** | `@tool(idempotent=True)`. The model can't double-charge. |
| **💾 Durable memory** | Four native checkpointers (OCI Object Storage, in-memory, file, HTTP) plus five storage-backed (PostgreSQL, OpenSearch, Redis, SQLite, Oracle 26ai) auto-wrapped via `*_checkpointer()` factories. |
| **🔎 RAG on your data** | Seven vector stores · OCI Cohere + OpenAI embeddings · multimodal (PDF + OCR + audio). |
| **🧩 Skills + Playbooks** | Filesystem-first capability disclosure + declarative step plans. |
| **📡 Streaming + Server** | Typed events for `match` consumers · SSE · drop-in FastAPI `AgentServer`. |
| **🪝 Hooks** | Logging · Telemetry · ModelRetry · Guardrails · Steering. |
| **🪙 MCP both ways** | `MCPClient` consumes external servers. `LocusMCPServer` exposes locus tools. |
| **🌐 Multi-modal providers** | `web_search=`, `web_fetch=`, `image_generator=`, `speech_provider=` on `Agent(...)` auto-register matching tools. Built-in OpenAI + httpx implementations, four Protocols for bring-your-own. |
| **📊 Evaluation** | `EvalCase` / `EvalRunner` / `EvalReport` regression suites. |
| **🛂 Termination algebra** | Eight composable stop conditions. `Or` and `And` compose them. |
| **🧰 Models** | OCI GenAI native (V1 + SDK) · OpenAI · Anthropic · Ollama. |
| **🏗 OCI Dedicated AI Cluster** | Pass an `ocid1.generativeaiendpoint....` OCID, get `DedicatedServingMode` with real SSE streaming. Live-tested on Qwen / London. |

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
Officer, the human approves, idempotent writes fire — runs end-to-end
in the multi-agent and idempotency tutorials under
[`examples/`](https://github.com/oracle-samples/locus/tree/main/examples).

## Introspect

locus is small enough to read end-to-end. Every capability has its own
concept page on this site, and every page links straight to its source
path. No magic, no hidden registries, no import-time side-effects.

| Capability | Source — class or section that does the work |
|---|---|
| Loop nodes — Think | [`ThinkNode` in `loop/nodes.py:59`](https://github.com/oracle-samples/locus/blob/main/src/locus/loop/nodes.py#L59-L135) |
| Loop nodes — Execute (idempotent dedup) | [`ExecuteNode` in `loop/nodes.py:136`](https://github.com/oracle-samples/locus/blob/main/src/locus/loop/nodes.py#L136-L259) |
| Loop nodes — Reflect | [`ReflectNode` in `loop/nodes.py:260`](https://github.com/oracle-samples/locus/blob/main/src/locus/loop/nodes.py#L260-L361) |
| Termination algebra (`__or__` / `__and__` overloads) | [`TerminationCondition` in `core/termination.py:39`](https://github.com/oracle-samples/locus/blob/main/src/locus/core/termination.py#L39-L117) |
| Tool decorator + idempotent flag | [`tool()` in `tools/decorator.py:113`](https://github.com/oracle-samples/locus/blob/main/src/locus/tools/decorator.py#L113-L165) · [`Tool` model `:26`](https://github.com/oracle-samples/locus/blob/main/src/locus/tools/decorator.py#L26-L112) |
| Memory — example backend | [`OCIBucketBackend` in `memory/backends/oci_bucket.py:57`](https://github.com/oracle-samples/locus/blob/main/src/locus/memory/backends/oci_bucket.py#L57) (sibling backends in [`memory/backends/`](https://github.com/oracle-samples/locus/tree/main/src/locus/memory/backends)) |
| Multi-agent — entry exports | [`multiagent/__init__.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/multiagent/__init__.py) (per-pattern files: `swarm.py`, `orchestrator.py`, `handoff.py`, `graph.py`, `functional.py`, `specialist.py`) |
| A2A — server + client | [`A2AServer` in `a2a/protocol.py:84`](https://github.com/oracle-samples/locus/blob/main/src/locus/a2a/protocol.py#L84-L294) · [`A2AClient` `:295`](https://github.com/oracle-samples/locus/blob/main/src/locus/a2a/protocol.py#L295) |
| Models — OCI two-transport | [`OCIOpenAIModel` in `models/providers/oci/openai_compat.py:163`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/providers/oci/openai_compat.py#L163) |
| RAG — retriever | [`RAGRetriever` in `rag/retriever.py:72`](https://github.com/oracle-samples/locus/blob/main/src/locus/rag/retriever.py#L72) · [`OCIEmbeddings` `embeddings/oci.py:85`](https://github.com/oracle-samples/locus/blob/main/src/locus/rag/embeddings/oci.py#L85) · [`OracleVectorStore` `stores/oracle.py:90`](https://github.com/oracle-samples/locus/blob/main/src/locus/rag/stores/oracle.py#L90) |
| Reasoning — Reflexion | [`Reflector` in `reasoning/reflexion.py:70`](https://github.com/oracle-samples/locus/blob/main/src/locus/reasoning/reflexion.py#L70) |
| Reasoning — Grounding (LLM-as-judge) | [`GroundingEvaluator` in `reasoning/grounding.py:106`](https://github.com/oracle-samples/locus/blob/main/src/locus/reasoning/grounding.py#L106) |
| Reasoning — Causal | [`CausalChain` in `reasoning/causal.py:160`](https://github.com/oracle-samples/locus/blob/main/src/locus/reasoning/causal.py#L160) |
| Hooks — built-in providers | [`hooks/builtin/__init__.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/hooks/builtin/__init__.py) (re-exports `LoggingHook`, `StructuredLoggingHook`, `TelemetryHook`, `GuardrailsHook`) · [`SteeringHook` `builtin/steering.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/hooks/builtin/steering.py) · [`ModelRetryHook` `builtin/retry.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/hooks/builtin/retry.py) |
| Streaming — typed events | [`core/events.py:17` `LocusEvent`](https://github.com/oracle-samples/locus/blob/main/src/locus/core/events.py#L17) (frozen Pydantic models — `ThinkEvent`, `ToolStartEvent`, `ToolCompleteEvent`, `ReflectEvent`, `TerminateEvent`, `ModelChunkEvent`) |
| Server — FastAPI wrapper | [`AgentServer` in `server/app.py:89`](https://github.com/oracle-samples/locus/blob/main/src/locus/server/app.py#L89) |
| Skills — AgentSkills.io | [`SkillsPlugin` in `skills/plugin.py:24`](https://github.com/oracle-samples/locus/blob/main/src/locus/skills/plugin.py#L24) |
| Playbooks — enforcer | [`PlaybookEnforcer` in `playbooks/enforcer.py:52`](https://github.com/oracle-samples/locus/blob/main/src/locus/playbooks/enforcer.py#L52) |
| Evaluation harness | [`EvalCase` `evaluation/framework.py:22`](https://github.com/oracle-samples/locus/blob/main/src/locus/evaluation/framework.py#L22) · [`EvalRunner` `:119`](https://github.com/oracle-samples/locus/blob/main/src/locus/evaluation/framework.py#L119) |
| MCP — server + client | [`LocusMCPServer` in `integrations/fastmcp.py:275`](https://github.com/oracle-samples/locus/blob/main/src/locus/integrations/fastmcp.py#L275) · [`MCPClient` `:414`](https://github.com/oracle-samples/locus/blob/main/src/locus/integrations/fastmcp.py#L414) |
| MCP client + server | [`src/locus/integrations/fastmcp.py`](https://github.com/oracle-samples/locus/tree/main/src/locus/integrations/fastmcp.py) |
| A2A protocol | [`src/locus/a2a/`](https://github.com/oracle-samples/locus/tree/main/src/locus/a2a) |

Read the [concepts](concepts/agent.md) for the *why*; read the
[API reference](api/agent.md) for the *what*.

## Learn locus in an afternoon

The [`examples/`](https://github.com/oracle-samples/locus/tree/main/examples)
tree is **40 progressive tutorials**. Every tutorial is one runnable
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
