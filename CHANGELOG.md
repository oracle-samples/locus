# Changelog

All notable changes to Locus will be documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and — from 1.0
onward — [Semantic Versioning](https://semver.org). See
[`DEPRECATION.md`](DEPRECATION.md) for the deprecation and breaking-change
policy.

## [Unreleased]

### Fixed (0.2.0b6) — OCI Responses live-shakedown follow-ups

Caught by running the in-PR Responses code against real OCI for
streaming, multi-turn, and tool round-trip. All three fixes are
scoped to `OCIResponsesModel` + `_responses_parse.py` — no other
transport is affected.

- **Zero Data Retention (ZDR) tenancies:** OCI tenancies with ZDR
  enabled reject `previous_response_id` with `"Previous response
  cannot be used for this organization due to Zero Data Retention."`
  This broke the multi-turn value prop in every enterprise OCI
  tenancy. Added an opt-in `store: bool = True` parameter to
  `OCIResponsesModel`; setting `store=False` switches the model to
  stateless mode — it sends `store: false` in every request body,
  drops `previous_response_id`, and advertises `server_stateful=False`
  so the agent runtime sends the full message history each turn (like
  chat/completions). ZDR tenants still benefit from access to
  Responses-only models (e.g. `openai.gpt-5.5-pro`).

- **Tool round-trip via Agent:** assistant messages with tool calls
  were emitting only `message` items in the Responses input but no
  `function_call` items. When the next turn included a
  `function_call_output` (the tool result), the server returned 400
  because there was no `call_id` anchor in the input. Now emits one
  `function_call` item per tool call, in order, in
  `_responses_parse.build_request_body`. Verified live: Agent +
  `@tool` + `OCIResponsesModel(store=False)` → tool fires → result
  posted back → model produces final answer using the tool output.

- **`server_stateful` is now a per-instance property** (was
  `ClassVar`), reflecting `config.store`. Lets the same class behave
  statelessly when ZDR mode is on without forcing two classes.
  Runtime loop check switched from class-level (`type(...)`) to
  instance-level (`getattr(self._model, ...) is True`) — still
  MagicMock-safe because `Mock object is True → False`.

Live wire-format coverage now includes: streaming end-to-end against
gpt-5 (events, content deltas, completed event), two-turn stateless
continuation (recalls user-shared facts from full history), and tool
round-trip with real OCI returning a final answer derived from tool
output.

### Added

- `OCIResponsesModel` — third OCI transport, opt-in, for the OCI
  Generative AI **Responses API** (`/openai/v1/responses`). Server-
  stateful: the OCI side holds the conversation thread between turns
  and Locus references it via `previous_response_id`. Use it for
  Responses-only OCI models (e.g. `openai.gpt-5.5-pro`) and for runs
  where re-sending the full history each turn is wasteful. Auth surface
  identical to `OCIOpenAIModel` (`profile=` for API key / session,
  `auth_type="instance_principal" | "resource_principal"` for workload
  identity). **Project OCID stays optional** — only required when a
  specific Responses feature demands it, in which case
  `OCIProjectRequiredError` points the caller at the constructor kwarg.
  Expired/unknown continuation tokens raise `OCIResponsesStateLostError` so
  resuming agents fail loud instead of silently dropping conversation.
  See [`docs/concepts/oci-responses.md`](docs/concepts/oci-responses.md).
- **Plumbing for server-stateful providers:** new
  `ModelResponse.provider_state` and `AgentState.provider_state` fields
  thread an opaque continuation token between turns. Stateless
  providers ignore them — default `None`, zero behavior change. The
  runtime loop detects `model.server_stateful` and sends only the
  message slice added since the last assistant turn, skipping
  `ConversationManager` strategies (which have nothing to operate on
  when the history is server-side). Every other Locus primitive —
  memory injection, Reflexion, GSAR, grounding, idempotency dedup,
  tool/model/invocation hooks, checkpointer, output schema, streaming,
  termination conditions — works identically on both transports.

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
