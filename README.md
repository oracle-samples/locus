<p align="center">
  <img src="https://raw.githubusercontent.com/oracle-samples/locus/main/docs/img/og-card.png?v=2" alt="locus — Multi-Agent SDK · pip install locus-sdk · Built by Oracle · github.com/oracle-samples/locus" width="720">
</p>

<p align="center">
  <strong>Oracle Generative AI · Multi-Agent Reasoning Orchestrator SDK</strong><br>
  <em>Built inside Oracle. Used in production. Open to everyone.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/locus-sdk/"><img src="https://img.shields.io/pypi/v/locus-sdk.svg?label=PyPI&color=blue" alt="PyPI version"></a>
  <img src="https://img.shields.io/badge/Python-3.11%E2%80%933.14-blue.svg" alt="Python 3.11–3.14">
  <img src="https://img.shields.io/badge/License-UPL--1.0-green.svg" alt="License">
  <img src="https://img.shields.io/badge/mypy-strict-brightgreen.svg" alt="mypy strict">
  <img src="https://img.shields.io/badge/ruff-clean-brightgreen.svg" alt="ruff clean">
  <img src="https://img.shields.io/badge/OCI%20GenAI-day%200-orange.svg" alt="OCI GenAI day-0">
</p>

<p align="center">
  <a href="https://oracle-samples.github.io/locus/">Documentation</a> ·
  <a href="https://oracle-samples.github.io/locus/concepts/router/">Cognitive Router</a> ·
  <a href="https://oracle-samples.github.io/locus/concepts/multi-agent/">Multi-agent</a> ·
  <a href="https://oracle-samples.github.io/locus/concepts/deepagent/">DeepAgent</a> ·
  <a href="examples/">63 Notebooks</a> ·
  <a href="https://oracle-samples.github.io/locus/workbench/">Workbench</a>
</p>

<p align="center">
  <strong>Try every locus pattern in your browser →</strong>
  <a href="https://oracle-samples.github.io/locus/workbench/"><strong>Workbench guide</strong></a><br>
  <em>Step-by-step setup for the browser playground — run it on localhost in three terminals, or in a single Docker container. Wire up an OCI profile, or bring your own OpenAI / Anthropic key.</em>
</p>

<p align="center">
  <em>Oracle 26ai is wired in as a first-class backend — native <code>VECTOR(N, FLOAT32)</code> RAG and durable agent threads in ADB, at parity with the LangChain Oracle integrations.</em>
</p>

---

## Your first agent — 5 lines

```python
from locus.agent import Agent
agent = Agent(model="oci:openai.gpt-5")
print(agent.run_sync("What is the capital of France?").text)
# → Paris
```

That's it. `Agent` handles the model call, the response, and any retries.
Swap `"oci:openai.gpt-5"` for `"openai:gpt-4o"` or `"anthropic:claude-sonnet-4-6"` — the interface stays the same.

## Add a tool

Tools are plain Python functions. The model sees the docstring and decides when to call them.

```python
from locus.agent import Agent
from locus.tools import tool
@tool
def get_weather(city: str) -> str:
    """Return the current weather for a city."""
    return weather_api.fetch(city)

agent = Agent(
    model="oci:openai.gpt-5",
    tools=[get_weather],
    system_prompt="You are a helpful travel assistant.",
)

print(agent.run_sync("Should I bring an umbrella to Tokyo tomorrow?").text)
```

The agent loops — Think → call tool → Think → answer — until it's done.
Add `@tool(idempotent=True)` to any tool that must not fire twice (bookings, payments, alerts).
The loop dedupes on `(name, args)` so retries are safe by design.

## Install

```bash
pip install "locus-sdk[oci]"           # OCI GenAI (90+ models, day-0)
pip install "locus-sdk[openai]"        # OpenAI
pip install "locus-sdk[anthropic]"     # Anthropic
pip install "locus-sdk[sdk]"           # everything
```

No mandatory cloud account to start — `MockModel` lets every notebook run offline.

---

## The cognitive router — describe what you need, get the right shape

Once you know agents, the next step is knowing *which* shape to use.
The cognitive router takes a natural-language task, fills a typed
`GoalFrame` from an LLM extractor, deterministically picks one of eight
built-in coordination protocols, and the `CognitiveCompiler` emits the
matching runtime primitive (`Agent`, `SequentialPipeline`,
`ParallelPipeline`, `LoopAgent`, an `A2AClient` call, or an
approval-gated agent) — without you hand-coding the topology.

```python
from locus.agent import Agent
from locus.router import (
    CapabilityIndex, CognitiveCompiler, GoalFrame, PolicyGate,
    ProtocolRegistry, Router, SkillIndex, builtin_protocols,
)
from locus.tools.registry import create_registry

# 1. Capabilities the router can bind to specialists.
registry = create_registry([kb_search, get_metric, list_alerts])

# 2. All 8 built-in protocols (answer / plan / specialist-fanout / debate
#    / codegen-loop / approval / a2a-delegate / handoff-chain).
protocols = ProtocolRegistry()
for p in builtin_protocols():
    protocols.register(p)

# 3. The Router wires an Agent(output_schema=GoalFrame) extractor + the
#    deterministic protocol picker + a CognitiveCompiler over the registry.
router = Router(
    frame_extractor=Agent(model=get_model(), output_schema=GoalFrame),
    protocols=protocols,
    capabilities=CapabilityIndex.from_registry(registry),
    skills=SkillIndex(),
    gate=PolicyGate(),
    compiler=CognitiveCompiler(),
)

# 4. Dispatch — the router picks the protocol + compiles the shape.
result = await router.dispatch(
    "We just got a sev-1 latency alert on the checkout service. "
    "Investigate and recommend remediation."
)
print(f"protocol={result.protocol_id} shape={result.runtime_shape}")
print(result.output)
```

The same `router.dispatch(...)` call resolves a one-shot lookup to a
single `Agent`, a multi-step incident triage to a `SequentialPipeline`
of planner→executor→validator, and a write-affecting action to an
approval-gated agent — chosen by protocol selection, not by the model.

→ [Cognitive router concept](https://oracle-samples.github.io/locus/concepts/router/) ·
[`examples/tutorial_52_cognitive_router.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_52_cognitive_router.py)

---

## Seven coordination patterns

When one agent isn't enough, locus gives you seven in-process shapes plus cross-process A2A.
Every pattern uses the same `Agent` class and the same event stream.

| Pattern | When to use |
|---|---|
| **SequentialPipeline** | A → B → C in order; each output feeds the next |
| **ParallelPipeline** | Fan out to N agents simultaneously, merge results |
| **LoopAgent** | Refine until a condition fires (PASS/FAIL, confidence, iteration cap) |
| **Orchestrator + Specialists** | One coordinator routes to domain experts in parallel |
| **Swarm** | Open-ended research; peers share a task queue and context |
| **Handoff** | Escalation desk; conversation moves with full history to the next specialist |
| **StateGraph** | Explicit DAG with conditional edges, cycles, and human-in-the-loop gates |
| **A2A** | Cross-process meshes over HTTP; agents advertise capabilities via AgentCard |

```python
from locus.agent import Agent, SequentialPipeline
researcher = Agent(model=model, system_prompt="Find three key facts about the topic.")
critic     = Agent(model=model, system_prompt="Identify any gaps or errors in the research.")
writer     = Agent(model=model, system_prompt="Write a clear one-paragraph summary.")

result = await SequentialPipeline(agents=[researcher, critic, writer]).run(
    "Explain quantum entanglement to a high-schooler."
)
print(result.text)
```

→ [All patterns](https://oracle-samples.github.io/locus/concepts/multi-agent/)

---

## What you get

| | |
|---|---|
| **[🧭 Cognitive router](https://oracle-samples.github.io/locus/concepts/router/)** | Describe a task → eight named protocols → right primitive compiled automatically. LLM fills a typed schema; routing is deterministic. |
| **[🤝 Multi-agent](https://oracle-samples.github.io/locus/concepts/multi-agent/)** | Seven native patterns + cross-process A2A. One `Agent` class. One event stream. |
| **[🔬 DeepAgent](https://oracle-samples.github.io/locus/concepts/deepagent/)** | `create_deepagent` (single agent, per-turn grounding) and `create_research_workflow` (StateGraph with post-hoc grounding eval + two-level recovery). |
| **[📡 Observability](https://oracle-samples.github.io/locus/concepts/observability/)** | Opt-in `EventBus` — one `run_context()` streams 40+ canonical events from every layer, no external broker. `TelemetryHook` for OpenTelemetry/OTLP. |
| **[🧠 Reasoning](https://oracle-samples.github.io/locus/concepts/reasoning/)** | `reflexion=True` · `grounding=True` · `CausalChain` · **GSAR** typed grounding layer (`arXiv:2604.23366`). |
| **[🛡 Idempotent tools](https://oracle-samples.github.io/locus/concepts/idempotency/)** | `@tool(idempotent=True)` — dedupes on `(name, args)`. The model can't double-charge, double-book, or double-page. |
| **[💾 Durable memory](https://oracle-samples.github.io/locus/concepts/checkpointers/)** | 8 backends — OCI Object Storage, PostgreSQL, Redis, Oracle 26ai, OpenSearch, in-memory, file, HTTP. |
| **[🔎 RAG](https://oracle-samples.github.io/locus/concepts/rag/)** | 7 vector stores · OCI Cohere + OpenAI embeddings · multimodal (PDF, image OCR, audio). |
| **[📡 Streaming + Server](https://oracle-samples.github.io/locus/concepts/server/)** | Typed events · SSE · `AgentServer` (FastAPI, per-principal thread isolation). |
| **[🪝 Hooks](https://oracle-samples.github.io/locus/concepts/hooks/)** | Logging · OpenTelemetry · ModelRetry · Guardrails · Steering (LLM-as-judge). |
| **[🪙 MCP](https://oracle-samples.github.io/locus/concepts/mcp/)** | `MCPClient` consumes MCP servers. `LocusMCPServer` exposes locus tools as MCP. |
| **[🌐 Multi-modal](https://oracle-samples.github.io/locus/concepts/multi-modal-providers/)** | `Agent(web_search=…, web_fetch=…, image_generator=…, speech_provider=…)` auto-registers tools. |
| **[📊 Evaluation](https://oracle-samples.github.io/locus/concepts/evaluation/)** | `EvalCase` / `EvalRunner` / `EvalReport` regression suites. |
| **[🧰 Models](https://oracle-samples.github.io/locus/concepts/models/)** | OCI GenAI (90+ models, V1 + SDK) · OpenAI · Anthropic · Ollama. |

---

## The agent loop

Every locus agent runs the same four-node loop —
**Think → Execute → Reflect → Terminate** — with one immutable state flowing through.

<p align="center">
  <img src="docs/img/agent-loop.svg" alt="Locus agent loop: Think → Execute → Reflect → Terminate" width="100%">
</p>

- **Think** — model decides the next action or final answer.
- **Execute** — runs tool calls in parallel; `@tool(idempotent=True)` dedupes on `(name, args)`.
- **Reflect** — Reflexion, Grounding, Causal on cadence or on error.
- **Terminate?** — typed stop conditions: `MaxIterations(10) | ToolCalled("submit") & ConfidenceMet(0.9)`.

Every node emits a write-protected typed event — same stream powers SSE, telemetry hooks, and your own `async for event in agent.run(…)` consumer.

---

## 63 notebooks

[`examples/`](examples/) has 63 progressive notebooks, numbered in suggested
reading order. Notebooks default to **Oracle Cloud Infrastructure (OCI)
Generative AI** when an OCI profile is available, and fall back to a
bundled mock model when one isn't — every example runs offline with no
credentials needed.

The first seven notebooks land the **Oracle 26ai** primitives end-to-end:
OCI transports, OCI inference deep-dives, Dedicated AI Cluster, Cohere
Reranker V4, native `VECTOR` RAG, and durable agent threads in the
database.

```bash
git clone https://github.com/oracle-samples/locus.git
cd locus && pip install -e .

python examples/tutorial_01_oci_transports.py        # start here — three OCI transports
python examples/tutorial_06_oracle_26ai_rag.py       # native VECTOR RAG on Oracle 26ai
python examples/tutorial_07_oracle_26ai_checkpointer.py  # durable agent threads in ADB
python examples/tutorial_08_basic_agent.py           # your first agent
python examples/tutorial_29_deepagent.py             # deep-research factory
python examples/tutorial_63_research_workflow.py     # full research pipeline
```

| Track | Range | What you learn |
|---|---|---|
| **OCI Generative AI** | 01–05 | OCI transports, OCIOpenAIModel, Responses, Dedicated AI Cluster, Cohere Reranker V4 |
| **Oracle Database 26ai** | 06–07 | Native `VECTOR(N, FLOAT32)` RAG + durable conversation checkpointer in ADB |
| **Foundations** | 08–15 | Agent, tools, memory, streaming, hooks, termination |
| **Graphs & composition** | 16–23 | StateGraph, conditional routing, reducers, HITL, composition, functional API |
| **Multi-agent** | 24–34 | Swarm, handoff, orchestrator, A2A, DeepAgent, debate, emergent routing |
| **Reasoning & structured** | 35–37 | Pydantic schemas, reasoning patterns, GSAR typed grounding |
| **RAG** | 38–40 | Basics, providers, RAG agents |
| **Skills, playbooks, plugins** | 41–45 | MCP, playbooks, plugins, skills, steering |
| **Production** | 46–51 | Guardrails, checkpoints, evaluation, providers, multi-modal |
| **Cognitive router + observability** | 52–56 | Routing, EventBus, yield bridge, event catalogue |
| **Real-world workflows** | 57–61 | Incident response, procurement, contract review, audio |
| **Server & full pipelines** | 62–63 | Agent server (FastAPI), full research workflow |

→ [Full notebooks index](https://oracle-samples.github.io/locus/tutorials/)

---

## Workbench

A browser-based playground for every locus pattern. Two clicks to a
running agent — no CLI install, no editor setup. Three model slots
(A / B / C) so multi-agent notebooks can mix a fast triage model
with a deeper specialist. Four sidebar tabs: **Notebooks** (every
runnable `tutorial_*.py`), **Skills** (SKILL.md packages),
**Protocols** (the eight cognitive-router shapes with cost / latency
metadata), and **Patterns** (the nine first-class
runtimes — including [Cognitive routing](docs/workbench.md#cognitive-routing-pattern)
with a Rule-based ⬌ LLM-picker toggle).

Two ways to run it. Pick whichever fits.

### Run locally (from source)

```bash
git clone https://github.com/oracle-samples/locus.git && cd locus
pip install -e ".[server,oci,openai,anthropic]"

# Three terminals, one per tier:
cd workbench/bff     && npm install && npm run dev   # BFF on :3101
cd workbench/web     && npm install && npm run dev   # Vite on :5173
cd workbench/backend && python -m uvicorn --app-dir . runner:app --port 8100
```

Open <http://localhost:5173>, click **Provider settings**, pick a
provider, fill in the credentials, save. OCI options work out of the
box because the backend reads your local `~/.oci/config`.

### Run in Docker

```bash
git clone https://github.com/oracle-samples/locus.git && cd locus
docker build -t locus-workbench -f workbench/Dockerfile .
docker run --rm -p 5173:5173 -p 3101:3101 -p 8100:8100 locus-workbench
# open http://localhost:5173
```

OpenAI and Anthropic work as-is — paste the key into *Provider settings*.
For the OCI providers (api-key or session token), bind-mount your `~/.oci`
into the container at the same host path and pass `HOME` so the OCI SDK
finds both the config and the `key_file` paths it references:

```bash
docker run --rm -p 5173:5173 -p 3101:3101 -p 8100:8100 \
  -v "$HOME/.oci:$HOME/.oci:ro" \
  -e "HOME=$HOME" \
  locus-workbench
```

→ Full walkthrough: [Workbench guide](docs/workbench.md) · [Provider settings](docs/workbench.md#provider-settings) · [Cognitive routing pattern](docs/workbench.md#cognitive-routing-pattern) · [Troubleshooting](docs/workbench.md#troubleshooting)

---

## Deploy

```bash
pip install "locus-sdk[oci,server]"
```

`AgentServer` is a drop-in FastAPI app: `POST /invoke`, `POST /stream`, `GET/DELETE /threads/{id}`, `GET /health`.

```python
from locus.server import AgentServer

server = AgentServer(agent=my_agent, api_key=os.environ["API_KEY"])
server.run(host="0.0.0.0", port=8080)
```

The repo ships a multi-stage `Dockerfile` ready to drop into your own image
pipeline. Deploy anywhere FastAPI runs — OCI Functions, Container Instances,
OKE, Compute, or any cloud equivalent.

→ [Deploy guide](https://oracle-samples.github.io/locus/how-to/deploy/)

---

## Repo layout

```text
src/locus/
├── agent/          Agent runtime, config, SequentialPipeline / ParallelPipeline / LoopAgent
├── core/           AgentState, Message, events, termination algebra, Send
├── loop/           ReAct nodes (Think, Execute, Reflect)
├── router/         Cognitive router — GoalFrame, ProtocolRegistry, PolicyGate, CognitiveCompiler
├── deepagent/      create_deepagent + create_research_workflow + 6 node primitives
├── observability/  EventBus, run_context, agent yield bridge, EV_* constants
├── memory/         BaseCheckpointer + 9 backends
├── models/         Provider registry + OCI, OpenAI, Anthropic, Ollama
├── multiagent/     Orchestrator, Swarm, Handoff, StateGraph, Functional
├── a2a/            Cross-process Agent-to-Agent protocol
├── reasoning/      Reflexion, Grounding, Causal, GSAR
├── rag/            Embeddings + 7 vector stores + retrievers
├── providers/      Multi-modal: web search, web fetch, image, speech
├── tools/          @tool decorator, registry, builtins, executors
├── hooks/          Logging, telemetry, retry, guardrails, steering
├── skills/         AgentSkills.io filesystem-first capability disclosure
├── playbooks/      Declarative step plans + PlaybookEnforcer
├── server/         FastAPI AgentServer with thread persistence
├── evaluation/     EvalCase + EvalRunner + EvalReport
└── integrations/   MCP (client + server)

workbench/          Browser playground — Notebooks / Skills / Protocols tabs,
                    three model slots, SSE event stream, Docker-ready.
examples/           63 progressive notebooks, each a single runnable file.
tests/unit/         Deterministic, no external deps. Runs in CI on every PR.
tests/integration/  Live OCI / OpenAI / Oracle Database 26ai. Gated on credentials.
```

---

## Contributing

```bash
git clone https://github.com/oracle-samples/locus.git
cd locus && pip install -e ".[dev,all]"
hatch run check        # ruff + mypy
hatch run test         # unit tests across Python 3.11–3.14
pre-commit install
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Every PR runs format, lint, mypy, unit tests, DCO sign-off.

---

## Citing GSAR

```bibtex
@article{kamelhar2026gsar,
  title   = {GSAR: Typed Grounding for Hallucination Detection and Recovery in Multi-Agent LLMs},
  author  = {Kamelhar, Federico A.},
  journal = {arXiv preprint arXiv:2604.23366},
  year    = {2026},
}
```

---

## Security

Please consult the [security guide](./SECURITY.md) for our responsible security vulnerability disclosure process.

---

## License

Copyright (c) 2026 Oracle and/or its affiliates.

Released under the Universal Permissive License v1.0 as shown at
<https://oss.oracle.com/licenses/upl/>.
