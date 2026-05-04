---
hide:
  - navigation
  - toc
---

<div class="locus-hero" markdown>
<div class="locus-hero__copy" markdown>

# Production-grade multi-agent workflows on <span class="accent">Oracle Generative AI.</span>

**Stream events. Branch on state. Pause for human review.
Resume across days, weeks, or queues.**

Seven first-class workflow primitives — composable in a single Python
process, scalable across an agent mesh. **Compose** linear pipelines.
**Orchestrate** specialists in parallel. **Swarm** for peer-to-peer
research. **Handoff** for escalation desks. **StateGraph** for bounded
retry loops. **Functional** for map-style composition. **A2A** for
cross-process meshes.

[See what you can build](#six-things-you-can-ship){ .md-button .md-button--primary }
[GitHub](https://github.com/oracle-samples/locus){ .md-button }

```bash
pip install "locus[oci]"
```

*Built inside Oracle. Used in production. Open to everyone.*

</div>

<div class="locus-hero__code" markdown>

```python
from locus import Agent
from locus.core.send import Send
from locus.multiagent.graph import END, START, StateGraph

REVIEWERS = ["security", "performance", "style"]

def reviewer(role):
    return Agent(model="oci:openai.gpt-5", system_prompt=f"You're a {role} reviewer.")

async def split(state):
    # Fan out: one Send per (file, role). The graph runs them in parallel.
    return [Send("review", {"file": f, "role": r})
            for f in state["files"] for r in REVIEWERS]

async def review(state):
    out = reviewer(state["role"]).run_sync(state["file"])
    return {"finding": {"file": state["file"], "role": state["role"], "text": out.message}}

async def synthesize(state):
    findings = [v["finding"] for v in state.values()
                if isinstance(v, dict) and "finding" in v]
    return {"report": "\n".join(f"[{f['role']}] {f['file']}: {f['text']}" for f in findings)}

graph = StateGraph()
graph.add_node("split", split)
graph.add_node("review", review)
graph.add_node("synthesize", synthesize)
graph.add_edge(START, "split")
graph.add_edge("split", "synthesize")
graph.add_edge("synthesize", END)

result = await graph.execute({"files": ["auth.py", "billing.py", "search.py"]})
print(result.final_state["report"])
# → 9 reviewers ran in parallel. Findings reduced into one report.
```

</div>
</div>

## Six things you can ship

### Claims grounded. Citations real. Hallucinations dropped

**Reflexion** evaluates every turn and feeds the next Think a sharper
plan. **Grounding** scores each claim against the tool result it came
from; below-threshold claims get dropped or sent back for re-research.
**Causal** traces root cause from symptom in incident-triage runs.

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
print(result.message)
print(f"grounding score: {result.grounding_score:.2f}")
# → grounding score: 0.94 — three claims grounded, one dropped (revenue mix)
```

→ [Reasoning inside the loop](concepts/reasoning.md) ·
[Turn on Reflexion + Grounding in one line](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_14_reasoning_patterns.py)

### Side effects fire once. Even when the model retries

The model can re-emit the same call after seeing an ambiguous result,
after a network glitch, after a checkpointed restart. With
**`@tool(idempotent=True)`** the body fires exactly once per
`(name, arguments)` hash. Booking, billing, paging — safe by design.

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

**Handoff** transfers context, tool history, and confidence from
specialist to specialist. The customer sees one continuous reply;
each team ships their specialist on its own schedule, in its own repo.

```python
from locus.multiagent.handoff import (
    create_handoff_agent, create_handoff_manager, HandoffReason,
)

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

### Agent meshes across teams and processes

Each agent publishes an **`AgentCard`** at `/agent-card`. Your research
agent fetches the card from the Finance team's URL, reads the skills
list, and decides whether to delegate. HTTP+SSE under the hood, no
shared infrastructure required.

```python
import asyncio
from locus.a2a import A2AClient

async def main():
    # The Finance team publishes their agent at this URL.
    finance = A2AClient(url="https://finance.example.com")

    # Discover capabilities (name, description, skills).
    card = await finance.get_agent_card()
    print(f"Calling {card.name} — {card.description}")
    print(f"Skills: {card.skills}")

    # Delegate.
    answer = await finance.invoke(
        "Pull Q3 OPEX vs forecast for line items 4100-4250."
    )
    print(answer)
    # → Q3 OPEX: $47M vs forecast $51M (-8%, supply-chain delays).

asyncio.run(main())
```

→ [A2A — agents across processes](concepts/multi-agent/a2a.md) ·
[Call another team's agent over A2A](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_34_a2a_protocol.py)

### Stop conditions you can compose

Compose stop conditions with Python's `&` and `|` operators on typed
classes — `__and__` / `__or__` overloads. Inspectable, unit-testable,
serialisable. You can grep your codebase for *exactly when* an agent
decides to stop. The loop ends when the work is done.

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
print(result.termination_reason)
# → ToolCalled('submit_po') and ConfidenceMet(0.92)
```

→ [Termination algebra](concepts/termination.md) ·
[Compose stop conditions like algebra](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_37_termination.py)

### Day-one production deployment

**`AgentServer`** wraps any agent as a FastAPI app: `POST /invoke`,
`POST /stream` for SSE, `GET`/`DELETE /threads/{id}` with per-principal
persistence — two API keys can't read each other's threads. Ship to
OKE, Container Instances, OCI Functions, or anywhere FastAPI runs.

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
