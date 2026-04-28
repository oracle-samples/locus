<p align="center">
  <img src="docs/img/logo.svg" alt="Locus" width="480">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/License-UPL--1.0-green.svg" alt="License">
  <img src="https://img.shields.io/badge/built%20by-Oracle-orange.svg" alt="Built by Oracle">
  <img src="https://img.shields.io/badge/mypy-strict-brightgreen.svg" alt="mypy">
  <img src="https://img.shields.io/badge/ruff-clean-brightgreen.svg" alt="ruff">
  <img src="https://img.shields.io/badge/OCI%20GenAI-day%200-orange.svg" alt="OCI GenAI day-0">
</p>

<p align="center">
  <strong>Oracle Generative AI · Multi-Agent · Reasoning · Orchestrator SDK.</strong>
</p>

<p align="center">
  <em>Build agents that show their work.</em>
</p>

<p align="center">
  Idempotent tools so they don't double-charge.<br>
  Reflexion so they don't loop on a wrong premise.<br>
  Durable memory so they survive restarts. Eval so you can prove they shipped.
</p>

<p align="center">
  Built on OCI GenAI · Oracle 26ai · OCI Object Storage. Day-0 model support.<br>
  Built inside Oracle. Used in production. Open to everyone.
</p>

<p align="center">
  <a href="#hello-agent">Hello, agent</a> ·
  <a href="#what-you-get">What you get</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="examples/">Examples</a> ·
  <a href="docs/">Docs</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

---

## Hello, agent

A booking agent. One tool. Idempotent so the model can't double-charge:

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

Output:

```text
Booked TK-12 for customer C-42. Confirmation BK-58291.
```

That's the whole thing. No registry to set up. No graph to wire. The model picks the
tool, the tool charges once, the agent stops.

**Going further.** A three-agent vendor PO approval workflow against a live Oracle 26ai
catalogue — Procurement and Compliance debate, hand off to an Approval Officer, the
human approves, idempotent writes fire — is in
[`examples/demos/po_approval/`](examples/demos/po_approval/).

## What you get

| | |
|---|---|
| **🧠 Reasoning** | Reflexion (self-evaluate), Grounding (LLM-as-judge claim verification), Causal (cause-effect chains). Each is one line on `Agent(...)`. |
| **🤝 Multi-agent** | Composition · Orchestrator + Specialists · Swarm · Handoff · StateGraph · Functional — six in-process patterns sharing one event type, plus A2A for cross-process meshes. |
| **🛡 Idempotent tools** | `@tool(idempotent=True)` — the ReAct loop dedupes repeat calls. The model can't double-charge, double-book, or double-page. |
| **💾 Durable memory** | Nine native checkpointer backends — OCI Object Storage, Oracle 26ai, PostgreSQL, OpenSearch, Redis, SQLite, HTTP, file, in-memory. One contract, every backend implements it directly. |
| **🔎 RAG on your data** | Seven vector stores, OCI Cohere + OpenAI embeddings, multimodal (PDF text + OCR, image OCR, audio transcription). Oracle 26ai is the day-1 native target. |
| **🧩 Skills + Playbooks** | AgentSkills.io filesystem-first skills + declarative YAML/Python playbooks with a `PlaybookEnforcer`. |
| **📡 Streaming + Server** | Typed events for `match`-statement consumers · SSE · drop-in FastAPI `AgentServer` with `X-Session-ID` thread persistence. |
| **🪝 Hooks** | Logging · Telemetry · ModelRetry · Guardrails (TopicPolicy, content blocks) · Steering (LLM-as-judge tool approval). |
| **🪙 MCP both ways** | `MCPClient` consumes external Anthropic-spec MCP servers. `LocusMCPServer` exposes locus tools as MCP. Round-trip. |
| **📊 Evaluation** | `EvalCase` / `EvalRunner` / `EvalReport` — regression suites, custom evaluators, pass-rate / latency / token cost reporting. |
| **🛂 Termination algebra** | Eight composable stop conditions. `Or(MaxIterations(10), And(ToolCalled("send"), ConfidenceMet(0.9)))` is the code. |
| **🧰 Models** | OCI GenAI native (V1 + SDK transport, 90+ models, day-0) · OpenAI · Anthropic · Ollama. One auth surface for OCI: profile, session token, instance / resource principal. |

## Quick start

```bash
pip install "locus[oci]"
export OCI_PROFILE=DEFAULT   # any profile in ~/.oci/config
```

```python
from locus import Agent, tool
from locus.tools.builtins import get_today_date

@tool(idempotent=True)
def book_meeting(date: str, attendees: list[str]) -> dict:
    return calendar.book(date, attendees)

agent = Agent(
    model="oci:openai.gpt-5.5",
    tools=[get_today_date, book_meeting],
    system_prompt="You are a scheduling assistant.",
)

print(agent.run_sync("Book a 30-min sync next Friday with alice@ and bob@.").message)
```

```text
Booked a 30-min sync for next Friday, 2026-05-01, with alice@ and bob@.
Event ID: evt-001.
```

Three iterations, two tool calls. Any OCI GenAI model id works — pass a
profile name and the SDK handles the rest.

## Capabilities, in detail

Each capability has its own mini-pattern. Click through for code, or browse the
runnable [`examples/`](examples/) tree.

### Memory & checkpointing — 9 native backends

The checkpointer is a first-class `Agent` argument. Pass any backend directly.
`BaseCheckpointer` is the contract; every backend implements
`save / load / list_threads / list_with_metadata / branching / vacuum`
natively, so the same code runs in tests and in production.

| Backend | When you use it | Class |
|---|---|---|
| **OCI Object Storage** | Cloud-native; lifecycle policies handle retention | `OCIBucketBackend` |
| **Oracle 26ai** | Your durable store *is* your DB; JSON columns, vacuum, full-text | `OracleCheckpointer` |
| **PostgreSQL** | Already running PG (often alongside `pgvector` for RAG) | `PostgreSQLBackend` |
| **OpenSearch** | Search-stack-native; metadata queries by index | `OpenSearchBackend` |
| **Redis** | Hot conversations, low latency, TTL semantics | `RedisBackend` |
| **SQLite** | Single-process, embedded | `SQLiteBackend` |
| **HTTP** | Delegate to a custom checkpoint service | `HTTPBackend` |
| **File** | Local dev, deterministic tests | `FileBackend` |
| **In-memory** | Unit tests | `InMemoryBackend` |

Source: [`src/locus/memory/`](src/locus/memory/) · concept doc:
[`docs/concepts/checkpointers.md`](docs/concepts/checkpointers.md).

### Multi-agent — six in-process patterns plus A2A

Locus does not pick a single multi-agent metaphor. Different problems want
different shapes — six in-process patterns plus A2A for cross-process meshes,
all sharing the same `Agent` and event types:

| Pattern | What it's for | Where it lives |
|---|---|---|
| **Pipeline** (Sequential / Parallel) | Linear chains; fan-out + merge | [`src/locus/agent/composition.py`](src/locus/agent/composition.py) |
| **Orchestrator + Specialist** | Router decides which expert handles each sub-task | [`src/locus/multiagent/orchestrator.py`](src/locus/multiagent/orchestrator.py) |
| **Swarm** | Peer-to-peer task queue with `SharedContext` | [`src/locus/multiagent/swarm.py`](src/locus/multiagent/swarm.py) |
| **Handoff** | Explicit role transfers carrying conversation history | [`src/locus/multiagent/handoff.py`](src/locus/multiagent/handoff.py) |
| **StateGraph** | DAG with cycles, conditional edges, subgraphs | [`src/locus/multiagent/graph.py`](src/locus/multiagent/graph.py) |
| **Functional** | `Send` / `SendBatch` for map/reduce | [`src/locus/multiagent/functional.py`](src/locus/multiagent/functional.py) |
| **A2A protocol** | Cross-runtime messaging via `AgentCard` | [`src/locus/a2a/`](src/locus/a2a/) |

### RAG — 7 vector stores, multimodal

```python
from locus.rag import RAGRetriever, OCIEmbeddings, OracleVectorStore

retriever = RAGRetriever(
    embedder=OCIEmbeddings(model_id="cohere.embed-english-v3.0"),
    store=OracleVectorStore(dsn="mydb_high", user="ADMIN", password=..., dimension=1024),
)
await retriever.add_file("manual.pdf")
results = await retriever.retrieve("How do I rotate API keys?", limit=5)

agent = Agent(model=..., tools=[retriever.as_tool()])
```

Stores: Oracle 26ai (native `VECTOR`), OpenSearch, Qdrant, Pinecone, pgvector,
Chroma, in-memory. Multimodal: PDF text + OCR, image OCR, audio transcription.
Embeddings: Cohere on OCI GenAI, OpenAI.

### Reasoning — agents that self-correct

```python
agent = Agent(
    model="oci:openai.gpt-5.5",
    tools=[search, summarize, validate_claim],
    reflexion=True,        # self-evaluate per turn
)
```

Reflexion ([Shinn et al., 2023](https://arxiv.org/abs/2303.11366)) — the agent
evaluates its own last step *before* stacking another tool call on top of a
wrong premise. Plus Grounding (LLM-as-judge claim verification) and Causal
(cause-effect chains). Source: [`src/locus/reasoning/`](src/locus/reasoning/).

### Hooks — observability + guardrails + steering

Five built-in hook providers, plus your own. Hooks fire on
`before / after × invocation × tool × iteration`:

- **`LoggingHook`** / **`StructuredLoggingHook`** — agent + tool traces.
- **`TelemetryHook`** — counters, latencies, OpenTelemetry-compatible.
- **`ModelRetryHook`** — retry on transient model failures.
- **`GuardrailsHook`** — `TopicPolicy`, content blocks, regex denylist.
- **`SteeringHook`** — LLM-as-judge tool approval. The agent's about to call
  `send_email`? A second model gets to vote.

Source: [`src/locus/hooks/`](src/locus/hooks/).

### Streaming + Server

```python
from locus.core.events import ThinkEvent, ToolStartEvent, TerminateEvent

async for event in agent.run("Plan a trip to Paris."):
    match event:
        case ThinkEvent(reasoning=r) if r:    print(f"💭 {r}")
        case ToolStartEvent(tool_name=n):     print(f"🔧 {n}")
        case TerminateEvent(final_message=m): print(f"✅ {m}")
```

Typed events stream as the agent runs. For HTTP streaming over SSE, locus
ships a reference [`AgentServer`](src/locus/server/) (FastAPI) with
`/invoke` + `/stream` endpoints.

### Tools — idempotent, MCP both ways

```python
@tool(idempotent=True)
def transfer(from_acct: str, to_acct: str, amount: float) -> dict: ...
```

- **`@tool`** auto-derives a JSON schema from your typed Python function
  signature — the model sees a contract, not a docstring.
- **`@tool(idempotent=True)`** dedupes repeat calls with identical arguments
  inside a single run.
- **MCP** in both directions: `MCPClient` consumes external MCP servers;
  `LocusMCPServer` exposes locus tools as an MCP server.

### Skills + Playbooks · Evaluation · Termination

- **Skills** ([AgentSkills.io](https://agentskills.io)) — filesystem-first capability disclosure.
- **Playbooks** — declarative step-by-step execution (YAML / JSON / Python) with a `PlaybookEnforcer`.
- **Evaluation** — `EvalCase` / `EvalRunner` / `EvalReport`. Regression suites, custom evaluators, pass-rate / latency / token cost reports.
- **Termination algebra** — `MaxIterations`, `TokenLimit`, `TimeLimit`, `TextMention`, `ToolCalled`, `ConfidenceMet`, `NoToolCalls`, `CustomCondition` — composable with `And` / `Or`.

## Installation extras

```bash
pip install "locus[openai]"          # OpenAI native
pip install "locus[anthropic]"       # Anthropic native
pip install "locus[ollama]"          # local LLMs
pip install "locus[oci]"             # OCI GenAI

pip install "locus[sqlite]"          # SQLite checkpointer
pip install "locus[redis]"           # Redis checkpointer
pip install "locus[postgresql]"      # PostgreSQL checkpointer
pip install "locus[opensearch]"      # OpenSearch checkpointer

pip install "locus[models]"          # all model providers
pip install "locus[checkpoints]"     # all checkpointer backends
pip install "locus[all]"             # everything
```

## More examples

[`examples/`](examples/) has 37 progressive tutorials, each a single runnable file.
Highlights:

- [`tutorial_01_basic_agent.py`](examples/tutorial_01_basic_agent.py) — start here
- [`tutorial_05_agent_hooks.py`](examples/tutorial_05_agent_hooks.py) — hook system
- [`tutorial_11_swarm_multiagent.py`](examples/tutorial_11_swarm_multiagent.py) — swarm
- [`tutorial_14_reasoning_patterns.py`](examples/tutorial_14_reasoning_patterns.py) — reflexion / grounding / causal
- [`tutorial_22_rag_basics.py`](examples/tutorial_22_rag_basics.py) — RAG over a vector store
- [`tutorial_27_hooks_advanced.py`](examples/tutorial_27_hooks_advanced.py) — guardrails + steering
- [`tutorial_34_a2a_protocol.py`](examples/tutorial_34_a2a_protocol.py) — Agent-to-Agent protocol

End-to-end demos:

- [`examples/demos/po_approval/`](examples/demos/po_approval/) — three-agent vendor PO approval on Oracle 26ai (live RAG, idempotent writes, human consent gate).
- [`examples/demos/trip_team/`](examples/demos/trip_team/) — same multi-agent shape on a Tokyo travel corpus.

## Repo layout

```
src/locus/
├── agent/          Agent runtime, config, composition pipelines
├── core/           AgentState, Message, events, termination algebra
├── loop/           ReAct nodes (Think, Execute, Reflect)
├── memory/         BaseCheckpointer + 9 backends
├── models/         Provider registry + OCI native, OpenAI, Anthropic, Ollama
├── tools/          @tool decorator, registry, builtins, executors, schema
├── hooks/          Hook events, registry, 5 built-ins
├── streaming/      AsyncIterator events, SSE, console handler
├── reasoning/      Reflexion, grounding, causal analysis
├── rag/            7 vector stores, embeddings, multimodal retrieval
├── multiagent/     Swarm, orchestrator, handoff, graph, functional pipelines
├── skills/         AgentSkills.io progressive disclosure
├── playbooks/      Declarative step-by-step execution
├── evaluation/     EvalCase, EvalRunner, EvalReport
├── integrations/   MCP (fastmcp) — both directions
├── server/         FastAPI HTTP wrapper (reference app)
└── a2a/            Agent-to-Agent protocol
```

## Testing

```bash
hatch run test          # 2987 unit tests, no services required (~6 s)
hatch run typecheck     # mypy strict
hatch run lint          # ruff + format check
hatch run all           # everything
```

Integration tests live in [`tests/integration/`](tests/integration/) and skip
cleanly when their service isn't available — see
[`tests/integration/conftest.py`](tests/integration/conftest.py) for the env-var
matrix and [`TESTING_LOCAL.md`](TESTING_LOCAL.md) for the full local setup.

## Trusted in production

Locus powers internal agentic workloads at Oracle. Every commit runs the full
test matrix against real OCI GenAI, Oracle 26ai, OCI Object Storage, OpenSearch,
Redis, and PostgreSQL — not mocks.

## Documentation

The [`docs/`](docs/) tree is the source of the project documentation site (built
with Material for MkDocs). It currently covers concepts, how-tos, API
references, and the feature matrix. Build locally with:

```bash
hatch run docs:serve
```

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Short version:

1. Sign the [Oracle Contributor Agreement](https://oca.opensource.oracle.com).
2. Branch from `main`. Use [Conventional Commits](https://conventionalcommits.org).
3. `hatch run all` must pass.
4. Open a merge request.

We treat new model providers, new checkpointer / RAG backends, hooks, evaluators,
docs, and tests as first-class contributions.

## Security

See [`SECURITY.md`](SECURITY.md) for vulnerability reporting.

Built-in: error-message sanitization (strips credentials, paths, OCIDs),
tool-argument validation against declared schemas, SQL identifier validation
in DB backends, write-protected hook events, and optional LLM-powered steering
for real-time tool approval.

## License

Copyright (c) 2025, 2026 Oracle and/or its affiliates. Released under the
[Universal Permissive License v1.0](LICENSE).

## Links

- [How-to: OCI GenAI models](docs/how-to/oci-models.md)
- [Oracle 26ai vector search](https://docs.oracle.com/en/database/oracle/oracle-database/23/vecse/)
- [OCI GenAI documentation](https://docs.oracle.com/en-us/iaas/Content/generative-ai/home.htm)
- [AgentSkills.io specification](https://agentskills.io)
- [Oracle Contributor Agreement](https://oca.opensource.oracle.com)
