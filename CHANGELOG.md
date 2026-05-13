# Changelog

All notable changes to Locus will be documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and — from 1.0
onward — [Semantic Versioning](https://semver.org). See
[`DEPRECATION.md`](DEPRECATION.md) for the deprecation and breaking-change
policy.

## [Unreleased]

### Added

- `AfterToolCallEvent.tool_call_id` and `AfterToolCallEvent.arguments` —
  read-only fields on the after-tool-call hook event. Lets a single
  `on_after_tool_call` hook correlate with the matching
  `BeforeToolCallEvent` and observe the exact arguments the tool ran
  with (post-hook mutation). Closes the gap between locus and peer
  frameworks (Claude Code `PostToolUse`, OpenAI Agents `on_tool_end`,
  Vercel `onStepFinish`, Strands `AfterToolCallEvent`) — see
  [`docs/concepts/hooks.md`](docs/concepts/hooks.md#on_after_tool_call--what-the-event-carries).
  Primary use case: mirroring tool calls into a host-side action queue
  (e.g. MCP integrations whose real side effect runs out of process).
  Additive — existing constructors / hook implementations keep working
  without changes; new fields are keyword-only with defaults of `""`
  and `{}`.

- `OCIOpenAIModel` — second OCI transport against the OpenAI-compatible
  `/openai/v1/chat/completions` endpoint. Wraps the standard `openai` SDK,
  inherits `OpenAIModel` for parsing/streaming/tool conversion, signs
  requests with an inline `httpx.Auth` wrapper around the existing OCI
  signers (no new dependencies). Real SSE streaming, day-0 model support,
  OpenAI-standard request shape; covers OpenAI / Meta / xAI / Mistral /
  Gemini families. Auth modes: `profile=` (laptop / CI),
  `auth_type="instance_principal" | "resource_principal"` (OCI workload
  identity). Compartment auto-derived from the profile's tenancy. No
  Responses API and no GenAI Project OCID — locus owns conversation state
  and tool execution. `OCIModel` (OCI SDK transport) remains the path for
  Cohere R-series. The string factory `model="oci:..."` auto-routes by
  family. See [`docs/how-to/oci-models.md`](docs/how-to/oci-models.md).
  (MR !70)
- `@tool(idempotent=True)` — declarative deduplication in the Execute
  node. When the model re-issues the same `(name, arguments)` tuple
  within a run, the prior result is reused instead of the tool firing
  again. (MR !46)
- `get_today_date` — built-in tool that returns today, tomorrow, the
  next seven weekdays, and week offsets as ISO dates, so models can
  resolve relative dates without asking. (MR !46)
- `anthropic` and `ollama` optional-dependency extras were missing from
  `pyproject.toml` even though the provider modules shipped. Added both
  plus a `models` bundle (`openai,anthropic,ollama,oci`); the `all`
  bundle now transitively pulls through `models`. (MR !49)
- `oci_bucket_config` session-scoped conftest fixture for integration
  tests; documents each `OCI_*` env var consumers must set. (MR !48)
- End-to-end `TestAgentWithOCIBucketBackend` — runs an `Agent` turn,
  throws the instance away, creates a brand-new `Agent` against the
  same `thread_id`, and asserts the conversation resumes from the
  bucket. (MR !48)

### Changed

- `examples/config.py` and the `oci:` string-factory entry in
  `locus.models.registry` now route OCI model ids by family —
  `cohere.command-r-*` flows through `OCIModel`, everything else
  through `OCIOpenAIModel`. Existing tutorials inherit the new
  transport without edits. Override with
  `LOCUS_OCI_TRANSPORT=v1|sdk`. (MR !70)
- `OpenAIModel` reasoning-family detection now tolerates OCI-style
  namespace prefixes (`openai.gpt-5.5` → recognised as `gpt-5*`,
  `max_completion_tokens` used). (MR !70)
- `OpenAIModel` no longer sends `presence_penalty` /
  `frequency_penalty` when they're at their default `0.0` — xAI Grok
  rejects either parameter outright. Server defaults are 0.0 anyway,
  so omission is functionally equivalent for providers that accept
  them. (MR !70)
- `OpenAIModel._parse_response` and `OpenAIModel.stream` now guard
  against `choice.message=None`, `message.content=None`, and
  `choice.delta=None`, which Gemini emits for filtered or empty
  responses. (MR !70)
- `OCIBucketBackend` now implements `BaseCheckpointer` directly and
  can be passed to `Agent(checkpointer=...)` without
  `StorageBackendAdapter` wrapping. The native object layout is
  `{prefix}/{thread_id}/{checkpoint_id}.json` plus a `.meta.json`
  sibling and a `_latest` pointer. (MR !48)
- README rewritten for accuracy: badges match measured test counts
  (2500+ unit / 270+ integration); the misleading `mypy-100%` claim
  replaced with `mypy-checked`; feature matrix moved to
  `docs/FEATURES.md`. (MR !50)

### Removed

- `src/locus/cli/` — the 14-line stub whose `main()` printed
  `"Locus CLI - coming soon"`. Dead code masquerading as SDK surface.
  Along with it: `[project.scripts]`, ruff/mypy/coverage overrides
  that only existed to silence the stub. (MR !49)

### Fixed

- Multi-turn Cohere conversations on OCI now preserve historical
  `tool_results` in `chat_history` so the model sees prior tool
  outputs instead of re-asking for data it already has. (MR !45)
- `no_tools` termination no longer fires on an unanswered user
  message — the loop now recognises an unreplied user turn as a
  signal to continue, not to stop. (MR !45)

## [0.1.0] — initial publishable cut

First internal-review version. Core shape established:

- `Agent`, `@tool`, `AgentState`, `Message`, `Role`, typed streaming
  events (`ThinkEvent`, `ToolStartEvent`, `ToolCompleteEvent`,
  `ReflectEvent`, `TerminateEvent`).
- ReAct loop (Think / Execute / Reflect) with planning, reflexion,
  grounding, and completion-mode controls.
- `BaseCheckpointer` abstraction and `MemoryCheckpointer`,
  `FileCheckpointer`, `HTTPCheckpointer` implementations.
- Storage backends (still dict-shaped in 0.1.0, migrated to native
  `BaseCheckpointer` in subsequent MRs): SQLite, Redis, PostgreSQL,
  OpenSearch, Oracle, OCI Object Storage — wrapped via
  `StorageBackendAdapter`.
- Model providers: OCI GenAI (Cohere, Meta, OpenAI, xAI, Google,
  Mistral), OpenAI, Anthropic, Ollama.
- Multi-agent: Swarm, orchestrator/specialist, handoff, graph
  (DAG + cyclic), composition (sequential/parallel/loop), functional
  API (`@entrypoint` / `@task`).
- Graph features: conditional edges, subgraphs, Send API (map-reduce),
  per-node `RetryPolicy` and `CachePolicy`, Mermaid + ASCII
  visualization.
- RAG: 8 vector stores, embeddings (OCI Cohere, OpenAI), multimodal
  retrieval.
- Hooks: write-protected events, cancel/retry control flow, reverse
  ordering, plugin system; five built-in hooks (logging, retry,
  guardrails, steering, telemetry).
- Guardrails depth: PII detection, SQL/XSS/command-injection detection,
  topic policy, content safety, output filtering.
- Steering: LLM-powered real-time tool approval.
- Skills: AgentSkills.io-compatible `SKILL.md` with progressive
  disclosure.
- Evaluation: `EvalCase`, `EvalRunner`, `EvalReport`.
- Composable termination: `|` (OR) and `&` (AND) operators on
  termination conditions.
- `AgentServer`: FastAPI deployment reference.
- A2A protocol: cross-framework agent-to-agent interop.
- Tool hot-reload for local development.
- Cancel signal + callback handler.
- Observability: OpenTelemetry spans and metrics, structured logging.
- Streaming: `AsyncIterator[LocusEvent]`, SSE, console handler.

[Unreleased]: https://orahub.oci.oraclecorp.com/saas-observ-eng/locus/-/compare/v0.1.0...main
[0.1.0]: https://orahub.oci.oraclecorp.com/saas-observ-eng/locus/-/tree/v0.1.0
