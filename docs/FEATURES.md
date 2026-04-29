# Locus feature matrix

What ships in `locus`, grouped by area.

## Agent core

| Feature | Surface |
|---|---|
| `Agent` + `AgentConfig` + `AgentResult` | `locus.agent` |
| Composable termination algebra (`MaxIterations \| ToolCalled & ConfidenceMet`) | `locus.core.termination` |
| Idempotent tools — `@tool(idempotent=True)` dedupes repeat calls | `locus.tools.decorator` |
| Reflexion (`reflexion=True`) + Grounding (`grounding=True`) | `locus.reasoning` |
| Causal chains (standalone graph builder) | `locus.reasoning.causal.CausalChain` |
| Cancel signal (thread-safe `agent.cancel()`) | `Agent.cancel` |
| Interrupts + resume (HITL) | `agent.run` yields `InterruptEvent`; `agent.resume(...)` |
| Structured output (`output_schema=` Pydantic) | `locus.agent.config`, `locus.core.structured` |
| Hooks lifecycle (before/after × invocation × tool × model + iteration) | `locus.hooks.provider` |
| Plugin bundling (hooks + tools as one unit) | `locus.hooks.plugin` |

## Memory

| Feature | Backends |
|---|---|
| Native checkpointers | `MemoryCheckpointer`, `FileCheckpointer`, `HTTPCheckpointer`, `OCIBucketBackend` |
| Storage-backed (auto-wrapped via `StorageBackendAdapter`) | `SQLiteBackend`, `RedisBackend`, `PostgreSQLBackend`, `OpenSearchBackend`, `OracleBackend` |
| Conversation managers | `SlidingWindowManager`, `SummarizingManager`, `LLMCompactor` |
| Long-term key-value store with optimistic locking (`version` counter) | `locus.memory.store` |

## Tools

| Feature | Surface |
|---|---|
| `@tool` decorator with auto JSON-Schema | `locus.tools.decorator` |
| Sequential / Concurrent / CircuitBreaker executors | `locus.tools.executor` |
| Tool-result store offload (large outputs) | `locus.tools.result_storage` |
| MCP — client + server | `locus.integrations.fastmcp` |
| Path/URL safety helpers | `locus.tools.path_safety`, `locus.tools.url_safety` |

## Hooks (built-in)

`LoggingHook`, `StructuredLoggingHook`, `TelemetryHook` (OpenTelemetry),
`NoOpTelemetryHook`, `ModelRetryHook`, `GuardrailsHook`,
`ContentFilterHook`, `SteeringHook` — all import from
`locus.hooks.builtin`.

## Multi-agent

`SequentialPipeline` / `ParallelPipeline` / `LoopAgent`
(plus `sequential()`, `parallel()`, `loop()` helpers); `Orchestrator` +
`Specialist`; `Swarm` + `SharedContext`; `Handoff` + `HandoffAgent`;
`StateGraph` (cycles, conditional edges, subgraphs); Functional API
(`@task` / `@entrypoint`); `A2AServer` + `A2AClient` + `AgentCard`.

## RAG

Seven vector stores under `locus.rag.stores`: Chroma, in-memory,
OpenSearch, Oracle 26ai, pgvector, Pinecone, Qdrant. Embeddings:
`OCIEmbeddings`, `OpenAIEmbeddings`. Multimodal processors:
`TextProcessor`, `ImageProcessor`, `PDFProcessor`, `AudioProcessor`,
`MultimodalProcessor`.

## Streaming + Server

Typed events (`ThinkEvent`, `ModelChunkEvent`, `ToolStartEvent`,
`ToolCompleteEvent`, `ReflectEvent`, `GroundingEvent`, `InterruptEvent`,
`TerminateEvent`); `StructuredStream` (incremental Pydantic partials);
console + SSE handlers; `AgentServer` with `/invoke`, `/stream`,
`GET /threads/{id}`, `DELETE /threads/{id}`, `/health` and
bearer-principal-scoped thread namespaces.

## Skills + Playbooks

Three-tier skill disclosure (`SkillsPlugin`); `PlaybookEnforcer` with
YAML / JSON / Python loaders; `Skill.from_directory()` activation.

## Models

`OpenAIModel`, `AnthropicModel`, `OllamaModel`, `OCIModel` (native SDK
transport for Cohere R-series), `OCIOpenAIModel` (`/openai/v1` for
openai.*/ meta.* / xai.*/ google.* / mistral.* on OCI). `get_model()`
auto-routes by model id. Failover, pooled, caching, rate-limit
decorators included.

## Evaluation

`EvalCase`, `EvalRunner`, `EvalReport`, `EvalResult` — pass/score/duration
reporting, custom evaluators, `expected_tools` / `expected_output_contains`
matchers.

## Source pointers

For depth on any feature, the README headlines link to its source
directory; canonical entry is `src/locus/__init__.py`.
