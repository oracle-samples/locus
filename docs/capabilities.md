# Capabilities

Everything `locus` ships, what it does, and where to find it.

!!! oracle-distinctive "Distinctive to locus"
    These are architectural choices no other Python agent framework ships
    together in one coherent stack:

    - **Multi-agent reasoning orchestrator** — describe a task; a
      deterministic registry picks one of eight protocols and instantiates the
      matching locus primitive. The LLM fills a typed `GoalFrame`; routing is
      rule-based. Eight protocols: `direct_response` (single Agent),
      `plan_execute_validate` (SequentialPipeline), `specialist_fanout`
      (ParallelPipeline), `debate` (two debaters + judge),
      `codegen_test_validate` (LoopAgent), `approval_gated_execution`
      (Agent + interrupt), `a2a_delegate`, `handoff_chain`.
    - **Seven native multi-agent patterns plus A2A** — Composition
      (Sequential / Parallel / Loop), Orchestrator + Specialists, Swarm,
      Handoff, StateGraph, Functional API (`@task` / `@entrypoint`), DeepAgent,
      cross-process A2A. Use them directly, or let the reasoning orchestrator
      dispatch to them. Every pattern shares the same `Agent` class and event
      stream.
    - **In-process observability** — opt-in `EventBus` with agent yield
      bridge. One `run_context()` streams 60+ canonical events from every
      layer (agent, multi-agent, router, RAG, memory, A2A). Zero allocations
      when unused.
    - **Reasoning loop nodes** — Reflexion, Grounding, Causal as first-class
      Think → Execute → **Reflect** → Think nodes, not bolted-on libraries.
    - **GSAR** — typed-grounding safety layer from
      [arXiv:2604.23366](https://arxiv.org/abs/2604.23366): four-way claim
      partition (grounded / ungrounded / contradicted / complementary) + tiered
      replanning decisions.
    - **Termination algebra** — `MaxIterations(10) | TextMention("DONE") & ConfidenceMet(0.9)` is real Python (`__or__` / `__and__` overloads). Greppable, unit-testable, serialisable.
    - **Idempotent tools** — `@tool(idempotent=True)` dedupes on `(name, args)` inside the Execute node. No double-charge, double-book, double-page — even on model retry or checkpoint resume.
    - **OCI, OpenAI, and Anthropic-compatible providers** — OCI Generative AI
      day-zero (two transports, 90+ models including OpenAI commercial and xAI
      Grok, auto-routed by model id); OpenAI and Anthropic through their
      official SDKs; Ollama for local models. One `get_model()` call, any
      provider.

## Agent core

| Feature | What it does | Surface |
|---|---|---|
| **Agent** + `AgentConfig` + `AgentResult` | The Think → Execute → Reflect → Terminate loop | `locus.agent` · [Agent loop](concepts/agent-loop.md) |
| **Termination algebra** | Compose stop conditions with `&` and `\|` operator overloads | `locus.core.termination` · [Termination](concepts/termination.md) |
| **Idempotent tools** | `@tool(idempotent=True)` dedupes repeat calls inside the loop — exactly-once side effects | `locus.tools.decorator` · [Idempotency](concepts/idempotency.md) |
| **Reflexion** | Self-evaluation node in the ReAct cycle; rewrites the next turn when the last one was wrong | `Agent(reflexion=True)` · [Reasoning](concepts/reasoning.md) |
| **Grounding** | LLM-as-judge claim verification against tool results; below-threshold triggers replanning | `Agent(grounding=True)` · [Reasoning](concepts/reasoning.md) |
| **Causal chains** | Cause-effect graph builder with cycle/contradiction detection | `locus.reasoning.causal.CausalChain` · [Reasoning](concepts/reasoning.md) |
| **GSAR** | Typed-grounding safety layer (arXiv:2604.23366) — four-way claim partition + tiered replanning | `Agent(gsar=GSARConfig(...))` · [GSAR](concepts/gsar.md) |
| **Cancel** | Thread-safe abort during a run; emits `TerminateEvent` with reason | `agent.cancel()` · [Agent loop](concepts/agent-loop.md) |
| **Interrupts (HITL)** | Pause via `InterruptEvent`; resume with `agent.resume(...)` | `locus.core.interrupt` · [Interrupts](concepts/interrupts.md) |
| **Structured output** | Pass `output_schema=` (Pydantic), final answer is parsed into a typed instance | `locus.agent.config`, `locus.core.structured` · [Structured output](concepts/structured-output.md) |
| **Hooks** | before/after × invocation × tool × model lifecycle observation + steering | `locus.hooks.provider` · [Hooks](concepts/hooks.md) |
| **Plugins** | Bundle hooks + tools as one drop-in unit | `locus.hooks.plugin` · [Hooks](concepts/hooks.md) |

## Multi-agent

| Shape | What it does | Surface |
|---|---|---|
| **Composition** | Linear chain · fan-out + merge — the simplest multi-agent shape | `locus.multiagent.composition` · [Composition](concepts/multi-agent/composition.md) |
| **Orchestrator** | One coordinator dispatches specialists in parallel | `locus.multiagent.orchestrator` · [Orchestrator](concepts/multi-agent/orchestrator.md) |
| **Swarm** | Open-ended peer-to-peer collaboration | `locus.multiagent.swarm` · [Swarm](concepts/multi-agent/swarm.md) |
| **Handoff** | Specialist-to-specialist context transfer with chain-of-custody | `locus.multiagent.handoff` · [Handoff](concepts/multi-agent/handoff.md) |
| **StateGraph** | Cycles, conditional edges, subgraphs — when DAG isn't enough | `locus.multiagent.graph` · [StateGraph](concepts/multi-agent/graph.md) |
| **Functional API** | Map / reduce over agents with `@task` and `@entrypoint` | `locus.multiagent.functional` · [Functional](concepts/multi-agent/functional.md) |
| **A2A** | Cross-process agent meshes — `AgentCard` discovery + HTTP/SSE transport | `locus.a2a` · [A2A](concepts/multi-agent/a2a.md) |

## Cognitive Router

Most agent frameworks force a choice: hand-code the topology (predictable
but brittle) or let the LLM pick it (flexible but unpredictable). The
cognitive router takes a third path — **bounded graph generation**. The LLM fills exactly
one typed `GoalFrame`; a deterministic registry selects from eight
named protocols; a compiler instantiates real locus primitives. The
output is always one of the eight proven shapes — never an ad-hoc topology
the model invented.

| Feature | What it does | Surface |
|---|---|---|
| **`Router`** | `dispatch(NL)` → extract GoalFrame → select protocol → compile → execute | `locus.router.Router` · [Router](concepts/router.md) |
| **`GoalFrame`** | Typed schema the LLM extractor fills — 13 `TaskType`s, `Risk`, `Complexity`, domain, capabilities | `locus.router.GoalFrame` |
| **`ProtocolRegistry`** | Deterministic filter (`handles ∋ goal`, `risk_max ≥ frame.risk`) + four-tier ranking (distance · canonical · cost · specificity) | `locus.router.ProtocolRegistry` |
| **`PolicyGate`** | Two thresholds: `max_risk` (hard deny) and `require_approval_above` (human-in-the-loop gate) | `locus.router.PolicyGate` |
| **`CognitiveCompiler`** | Instantiates real locus primitives from frame + protocol; emits a `Runnable` adapter | `locus.router.CognitiveCompiler` |
| **`builtin_protocols()`** | 8 v1 protocols: `direct_response` · `plan_execute_validate` · `specialist_fanout` · `debate` · `codegen_test_validate` · `approval_gated_execution` · `a2a_delegate` · `handoff_chain` | `locus.router.builtin_protocols` |
| **`CapabilityIndex`** | Domain + risk overlay on `ToolRegistry` — no parallel storage | `locus.router.CapabilityIndex` |
| **`SkillIndex`** | Domain-tagged view of installed `Skill` packs; scoped catalog attached to every emitted Agent | `locus.router.SkillIndex` |
| Custom protocols | `Protocol(id=…, handles=[…], builder=fn)` registered via `ProtocolRegistry.register()` | `locus.router.Protocol` |
| Error types | `FrameExtractionError` · `NoMatchingProtocolError` · `PolicyDeniedError` | `locus.router.runtime/protocol/policy` |

## Observability

| Feature | What it does | Surface |
|---|---|---|
| **`EventBus`** | Singleton in-process pub/sub — per-run + global subscribers, bounded queues, history replay, drop accounting | `locus.observability.EventBus` · [Observability](concepts/observability.md) |
| **`run_context()`** | ContextVar-based opt-in gate — zero allocations when inactive | `locus.observability.run_context` |
| **Agent yield bridge** | `@_bus_bridge` on `Agent.run` transparently republishes 9 `LocusEvent` types as `agent.*` SSE events | `locus.agent.runtime_loop` |
| **`EventBusHook`** | `HookProvider` that bridges all agent lifecycle hooks onto the bus (for non-async / pre-built agents) | `locus.observability.EventBusHook` |
| **Canonical event catalogue** | 60+ `EV_*` constants across 10 prefixes (`agent.*`, `multiagent.*`, `composition.*`, `router.*`, `research.*`, `rag.*`, `memory.*`, `a2a.*`, `skills.*`, `deepagent.*`) | `locus.observability.emit` · [SSE event catalogue](concepts/sse-events.md) |

## Reasoning

| Feature | What it does | Surface |
|---|---|---|
| **Reflexion** | After each turn, the agent self-evaluates and re-plans on wrong premises | `Agent(reflexion=True)` · [Reasoning](concepts/reasoning.md) |
| **Grounding** | LLM-as-judge over claims vs the tool results that produced them | `Agent(grounding=True)` · [Reasoning](concepts/reasoning.md) |
| **Causal** | Build a cause-effect graph from the trace; surface contradictions | `build_causal_chain()` · [Reasoning](concepts/reasoning.md) |
| **GSAR** | Typed claim partition (grounded / ungrounded / contradicted / complementary) + `proceed`/`regenerate`/`replan`/`abstain` decision | `Agent(gsar=GSARConfig(...))` · [GSAR](concepts/gsar.md) |

## Tools

| Feature | What it does | Surface |
|---|---|---|
| `@tool` decorator | Function → JSON-Schema-typed tool the model can call | `locus.tools.decorator` · [Tools](concepts/tools.md) |
| Idempotent dedup | `@tool(idempotent=True)` skips repeat calls (same args) in the loop | `locus.tools.decorator` · [Idempotency](concepts/idempotency.md) |
| **Sequential executor** | Run tool calls one at a time | `locus.tools.executor` · [Executors](concepts/executors.md) |
| **Concurrent executor** | Run tool calls in parallel | `locus.tools.executor` · [Executors](concepts/executors.md) |
| **CircuitBreaker executor** | Auto-disable a tool after N failures | `locus.tools.executor` · [Executors](concepts/executors.md) |
| Result-store offload | Move large tool results to object storage; agent sees a pointer | `locus.tools.result_storage` |
| Path / URL safety | Validate filesystem and network access from tool args | `locus.tools.path_safety`, `locus.tools.url_safety` · [Safety](concepts/safety.md) |
| **MCP — client + server** | Talk to / be talked to by Anthropic-spec MCP servers | `locus.integrations.fastmcp` · [MCP](concepts/mcp.md) |

## Memory — checkpointer backends

| Backend | Best for | Surface |
|---|---|---|
| `MemoryCheckpointer` | Tests, REPL — in-process dict | `locus.memory.backends.memory` · [Checkpointers](concepts/checkpointers.md) |
| `FileCheckpointer` | Local dev — JSON files on disk | `locus.memory.backends.file` |
| `HTTPCheckpointer` | A remote checkpoint service you already run | `locus.memory.backends.http` |
| **`OCIBucketBackend`** | OCI-native, lifecycle policies, region replication | `locus.memory.backends.oci_bucket` |
| `SQLiteBackend` | Single-process durability | `locus.memory.backends.sqlite` |
| `RedisBackend` | Multi-replica, fast, TTLs | `locus.memory.backends.redis` |
| `PostgreSQLBackend` | Production DB with metadata queries | `locus.memory.backends.postgresql` |
| `OpenSearchBackend` | Full-text search across past runs | `locus.memory.backends.opensearch` |
| `OracleBackend` | Oracle DB with JSON queries | `locus.memory.backends.oracle` |

## Memory — context management

| Feature | What it does | Surface |
|---|---|---|
| `SlidingWindowManager` | Keeps the last N messages; drops the rest | `locus.memory.compactor` · [Conversation management](concepts/conversation-management.md) |
| `SummarizingManager` | LLM rollup of older turns | `locus.memory.compactor` |
| **`LLMCompactor`** | Budget-aware compaction with head + tail protection | `locus.memory.compactor` |
| Long-term key-value store | Cross-run user prefs / results with optimistic-locking `version` counter | `locus.memory.store` |

## Hooks (built-in)

| Hook | What it does | Import |
|---|---|---|
| `LoggingHook` / `StructuredLoggingHook` | Stdlib / structured-JSON logs of every event | `locus.hooks.builtin` · [Observability](concepts/observability.md) |
| **`TelemetryHook`** | OpenTelemetry traces + metrics (counters, histograms) | `locus.hooks.builtin` |
| `NoOpTelemetryHook` | Opt-out variant for tests | `locus.hooks.builtin` |
| `ModelRetryHook` | Auto-retry model calls on throttle/empty with exponential back-off | `locus.hooks.builtin` · [Retry](concepts/retry.md) |
| **`GuardrailsHook`** | Block dangerous tools, redact PII, enforce content/topic policies | `locus.hooks.builtin` · [Safety](concepts/safety.md) |
| `ContentFilterHook` | Standalone content moderation | `locus.hooks.builtin` |
| **`SteeringHook`** | LLM-as-judge approval gate on every tool call | `locus.hooks.builtin` · [Safety](concepts/safety.md) |

## Streaming + Server

| Feature | What it does | Surface |
|---|---|---|
| **Typed events** | Frozen Pydantic events for `match`-statement consumers | `locus.core.events` · [Events](concepts/events.md) |
| `StructuredStream` | Incremental Pydantic-partial parsing during streaming | `locus.core.structured` |
| Console + SSE handlers | Render to terminal or stream over Server-Sent Events | `locus.core.events` · [Streaming](concepts/streaming.md) |
| **`AgentServer`** | Drop-in FastAPI app: `/invoke`, `/stream`, `/threads/{id}`, `/health` | `locus.server` · [Agent Server](concepts/server.md) |
| Per-principal threads | Bearer-token auth + thread-id namespacing prevents cross-tenant leaks | `AgentServer(api_key=...)` · [Agent Server](concepts/server.md) |
| Graph streaming | Multi-agent state-graph event streams | `locus.multiagent.graph` · [Graph streaming](concepts/graph-streaming.md) |

## RAG

| Component | Options | Surface |
|---|---|---|
| Vector stores | Oracle 26ai · OpenSearch · pgvector · Qdrant · Pinecone · Chroma · in-memory | `locus.rag.stores` · [RAG](concepts/rag.md) |
| Embeddings | `OCIEmbeddings` (Cohere) · `OpenAIEmbeddings` | `locus.rag.embeddings` |
| Multimodal processors | Text · PDF (text + OCR) · Image (OCR) · Audio (transcription) | `locus.rag.multimodal` |
| Tool wiring | `create_rag_tool(retriever)` exposes the retriever as a `@tool` | `locus.rag.tools` |

## Models

| Provider | Models | Surface |
|---|---|---|
| **OCI Generative AI — V1 transport** | `openai.*`, `meta.*`, `xai.*`, `google.*`, `mistral.*` on OCI | `locus.models.providers.oci.openai_compat` · [OCI](concepts/providers/oci.md) |
| **OCI Generative AI — SDK transport** | Cohere `command-r-*` series — proprietary chat shape | `locus.models.providers.oci.OCIModel` · [OCI](concepts/providers/oci.md) |
| OpenAI | All commercial models (gpt-5.5, o-series, etc) | `locus.models.providers.openai` · [OpenAI](concepts/providers/openai.md) |
| Anthropic | Claude 4 / 4.5 / 4.7 / 4.8 — direct API | `locus.models.providers.anthropic` · [Anthropic](concepts/providers/anthropic.md) |
| Ollama | Local models | `locus.models.providers.ollama` · [Ollama](concepts/providers/ollama.md) |
| Auto-routing | `get_model("oci:openai.gpt-5.5")` picks transport from id | `locus.models.registry.get_model` |
| Decorators | Failover · pooled · cached · rate-limited wrappers over any provider | `locus.models.decorators` |

## Skills + Playbooks

| Feature | What it does | Surface |
|---|---|---|
| **Skills** | AgentSkills.io progressive disclosure (catalog → instructions → resources) | `locus.skills.SkillsPlugin` · [Skills](concepts/skills.md) |
| `Skill.from_directory()` | Load a folder of `SKILL.md` bundles | `locus.skills.models.Skill` |
| **Playbooks** | Numbered execution plans with per-step `PlaybookEnforcer` | `locus.playbooks` · [Playbooks](concepts/playbooks.md) |
| YAML / JSON / Python loaders | Author playbooks in any of three formats | `locus.playbooks.loader` |

## Evaluation

| Class | What it does | Surface |
|---|---|---|
| `EvalCase` | A single test case — expected tools / output / iteration / duration budgets | `locus.evaluation` · [Evaluation](concepts/evaluation.md) |
| `EvalRunner` | Runs a list of cases against an agent, returns `EvalReport` | `locus.evaluation` |
| `EvalResult` | Per-case pass / score / duration + diagnostic checks | `locus.evaluation` |
| `EvalReport` | Aggregate stats with `summary()` + JSON serialisation | `locus.evaluation` |

## Where to next

- **For first-time visitors**: [Quickstart](how-to/quickstart.md) ships a working agent in five minutes.
- **For architecture**: [Agent loop](concepts/agent-loop.md) is the canonical reference.
- **For depth on any feature**: every row in this matrix links to its concept page. Source lives at [`src/locus/`](https://github.com/oracle-samples/locus/tree/main/src/locus); canonical entry is [`src/locus/__init__.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/__init__.py).
