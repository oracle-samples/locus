# Changelog

All notable changes to Locus will be documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and — from 1.0
onward — [Semantic Versioning](https://semver.org). See
[`DEPRECATION.md`](DEPRECATION.md) for the deprecation and breaking-change
policy.

## [Unreleased]

## [0.2.0b13] - 2026-05-16

### Fixed — OCI instance-principal token now auto-refreshes on both openai-style HTTP transports

`OCIOpenAIModel` (behind every `oci:openai.<model>` / `oci:google.<model>` id)
**and** `OCIResponsesModel` (the `/v1/responses` transport) were both
constructing their `OCIRequestSigner` without passing a `refresh_signer`
callback. `OCIRequestSigner.auth_flow` has a refresh-on-401 branch *and*
a periodic-refresh branch — both early-return when `refresh_signer is None`,
which meant the federation token captured at process start was used
forever. On OKE, instance-principal tokens expire on the order of 15–30
minutes, so any agent pod older than that would 401 on every GenAI call
until restarted.

Production symptom: chats silently fall through to `reason=error` after
~15 minutes of pod uptime, with httpx logs showing
`HTTP/1.1 401 Unauthorized` on every `chat.completions` /
`/v1/responses` call. Pod restart was the only known workaround.

The fix wires the signer's own `refresh_security_token` method (present
on `InstancePrincipalsSecurityTokenSigner`, `get_resource_principals_signer()`
returns a signer with the same contract, and any `DelegationTokenSigner`
variant that follows the OCI SDK convention) into the wrapper via a new
`_refresh_callable_for(signer)` helper exported from `openai_compat.py`
and reused by `responses.py`. Static signers (user-principal API key)
have no `refresh_security_token` attribute and the helper returns
`None`, so the refresh path stays dormant for them.
`refresh_interval` is tightened from the upstream 3600 s default to
600 s — short enough that proactive refresh beats the typical 15–30
minute federation-token TTL even if a 401 doesn't fire first.

**Scope of the fix.** Two transports use the httpx + `OCIRequestSigner`
wrapper and are both patched here. Other OCI transports route signing
through `oci.generative_ai_inference.GenerativeAiInferenceClient`,
which delegates to the OCI Python SDK's built-in HTTP client and
already refreshes federation tokens internally — those are unaffected
by this bug:

| Transport | File | Status |
|---|---|---|
| `OCIOpenAIModel` (Chat Completions) | `src/locus/models/providers/oci/openai_compat.py` | Fixed |
| `OCIResponsesModel` (`/v1/responses`) | `src/locus/models/providers/oci/responses.py` | Fixed |
| `OCIModel` (native OCI SDK) | `src/locus/models/providers/oci/client.py` | Unaffected (OCI SDK refresh) |
| `OracleGenAIEmbeddings` (RAG) | `src/locus/rag/embeddings/oci.py` | Unaffected (OCI SDK refresh) |

No public-API change; the wiring is internal.

- `src/locus/models/providers/oci/openai_compat.py` — new
  `_refresh_callable_for(signer)` helper; `OCIOpenAIModel.client` now
  passes `refresh_signer=_refresh_callable_for(signer)` and
  `refresh_interval=600.0` when constructing `OCIRequestSigner`.
- `src/locus/models/providers/oci/responses.py` — `OCIResponsesModel._http_client`
  imports `_refresh_callable_for` from `openai_compat` and uses the
  same `refresh_signer=_refresh_callable_for(signer)` +
  `refresh_interval=600.0` wiring so the Responses-API transport
  gets the same long-lived federation-token handling.
- `tests/unit/test_oci_openai_compat.py` — `TestRefreshCallableFor`
  (3 cases) and `TestClientWiresRefreshSigner` (2 cases) cover the
  helper and the openai-compat wiring.
- `tests/unit/test_oci_responses_model.py` — `TestHttpClientWiresRefreshSigner`
  (2 cases) covers the `OCIResponsesModel` wiring with the same contract.

## [0.2.0b12] - 2026-05-16

### Added — `datastores=` parity on `create_research_workflow`

`create_research_workflow` now accepts the same `datastores={name: {retriever, description, top_k, threshold}}`
mapping as `create_deepagent`. Both factories share a `wire_datastores(...)`
helper so the execute agent of either path gets an identical `search_<name>`
tool surface plus a per-store routing block prepended to the system prompt.

This closes the only remaining surface gap between the two research
factories — recipes that ran on `create_deepagent(datastores=...)`
translate to the StateGraph-with-grounding-loop variant verbatim.

```python
workflow = create_research_workflow(
    model=...,
    tools=[],
    output_schema=Report,
    datastores={"medical": {"retriever": medical_retriever, "top_k": 6}},
    grounding_threshold=0.65,
)
```

- `src/locus/deepagent/factory.py` — extracted the auto-wiring logic
  into a new public `wire_datastores(datastores, datastore_top_k) ->
  (tools, routing_block)` helper. `create_deepagent` now calls it
  (semantics unchanged from b11).
- `src/locus/deepagent/workflow.py` — `create_research_workflow` gains
  `datastores=` and `datastore_top_k=` kwargs; the execute node sees
  the merged tool list and the prepended routing block.
- `docs/concepts/deepagent.md` — workflow `datastores=` example +
  cross-reference under "When to use each".
- `tests/unit/test_research_workflow_datastores.py` — 8 cases covering
  `None`/empty input, bare-retriever vs dict form, multi-store routing,
  `TypeError` on bad value types, and end-to-end workflow construction
  with a configured datastore.

## [0.2.0b11] - 2026-05-16

### Added — `create_deepagent(datastores=...)` + seven deep-research locus demos

`create_deepagent` now accepts a `datastores={name: {retriever, description, top_k, threshold}}`
mapping and auto-wires a `search_<name>` tool for each entry, plus a per-store routing block
prepended to the system prompt so the model picks the right store per query. Mirrors the
`langchain-oci.create_deep_research_agent(datastores=...)` shape so existing recipes translate 1:1.
Closes [#202](https://github.com/oracle-samples/locus/issues/202).

- **API surface.** `from locus.deepagent import create_deepagent` —
  `datastores=` accepts either a bare `RAGRetriever` or the dict form
  `{retriever, description, top_k, threshold}`. The store name
  interpolates into both the tool name (`search_medical`) and the
  routing block in the system prompt.
- **`OracleVectorStore` column overrides.** `id_column`, `content_column`,
  `embedding_column`, `metadata_column`, `created_at_column` (set to
  `None` to skip), and `auto_create_table=False` for attaching to
  existing tables written by other ingestion pipelines (e.g.
  `langchain_oracledb.vectorstores.OracleVS` writes `text` instead of
  `content`). Lets locus read a foreign-schema ADB table without
  re-ingestion.
- **`cohere.embed-v4.0` dimension auto-detect.** The embedding-model
  registry now treats `MODEL_DIMENSION_HINTS` as a hint table — models
  not present in it discover their dimension via a one-shot probe call
  at first use. New models work without an explicit entry.
- **Defensive `float`/`int` coercion in the retrieval path.** Some
  providers (notably `gpt-5.x`) JSON-encode tool args as strings —
  `"min_score": "0.5"` rather than `0.5`. `RAGRetriever.retrieve` and
  `OracleVectorStore.search` now coerce defensively so the downstream
  `score < threshold` comparison never sees a string and never raises
  `TypeError`.

### Added — `examples/projects/deep-research/`

Seven runnable demos that mirror upstream langchain-oci deep-research
gists 1:1 on locus primitives, covering every retrieval backend locus
supports:

| Demo | Backend | Notes |
|---|---|---|
| `demo_hello_world.py` | none — `@tool` functions | Sanity check for `create_deepagent` |
| `demo_smoke.py` | `InMemoryVectorStore` | No-DB end-to-end RAG smoke |
| `demo_iron_metabolism.py` | Oracle Autonomous DB (241-doc corpus) | `gpt-5.1 @ 65K`; prints retrieved snippets and citation density |
| `demo_memory_multi_turn.py` | ADB + `locus.memory.InMemoryStore` | Two-turn agent with response capture |
| `demo_multi_datastore.py` | Two ADB vector tables | Cross-domain routing via `datastores={medical, news}` |
| `demo_opensearch_multi_index.py` | Two OpenSearch indices | Same shape against `OpenSearchVectorStore` |
| `demo_object_storage.py` | OCI Object Storage `@tool` wrappers | `list_bucket_objects` / `read_bucket_object` / `search_bucket_data` |

The README documents the langchain-oci → locus translation table,
runtime gotchas (`InMemoryStore` is async; `AsyncOpenSearch` clients
need awaited operations; from inside an event loop use
`async for event in agent.run(...)` instead of `agent.run_sync(...)`),
and verified output stats from a real ADB run.

### Added — documentation

- `docs/concepts/deepagent.md` — new "Datastore auto-wiring" section
  with an Oracle Autonomous DB example and the provider-quirk +
  async-loop notes.
- `docs/tutorials/tutorial_41_deepagent.md` — topic 6 cross-references
  the deep-research project for the multi-backend variants.
- `docs/workbench.md` and `workbench/README.md` — cross-references
  under "What you can run" so workbench users discover the project
  examples.
- `examples/tutorial_41_deepagent.py` — new `part5_datastores()` that
  exercises `create_deepagent(datastores=...)` against an in-memory
  `RAGRetriever`, so the workbench picks the tutorial up and demos
  the auto-wiring without external dependencies.

### Fixed — embedding-config rename, ratchet refresh, docs audit

- `MODEL_DIMENSIONS` constant renamed to `MODEL_DIMENSION_HINTS` (keys
  are now model_id strings rather than enum members). Old internal
  callers updated; `test_model_dimensions` aligned.
- Coverage ratchet baseline refreshed for `src/locus/rag/embeddings/oci.py`
  (99.35% → 98.73%) to accept the intentional auto-detect branch.
- `docs/concepts/deepagent.md`: Quickstart now uses `result.parsed`
  (the actual Pydantic-typed structured-output field on `AgentResult`);
  previously referenced a non-existent `result.structured_output`. The
  Datastore auto-wiring section now points at
  `locus.rag.tools.create_rag_tool` (the factory's actual call), not
  `RAGRetriever.as_tool` (a thin wrapper that doesn't accept the
  per-store `top_k`/`threshold` overrides).

## [0.2.0b10] - 2026-05-15

### Fixed — /invoke + auth rough edges surfaced by an OCI GenAI e2e build

Four small fixes and one error-message improvement, each of which
independently blocked a real end-to-end build (orchestrator + specialists
on `oci:openai.gpt-5` in `us-chicago-1`, exposed via an `AgentServer`
behind a Fastify proxy). Each fix is gated by unit tests; the full suite
stays green (4564 passed, 3 skipped). Closes
[#191](https://github.com/oracle-samples/locus/issues/191).

- **`[oci]` extra now pulls `openai>=1.50`.** The OCI provider
  lazy-imports `openai` at request time (`OCIOpenAIModel.client`
  property); without it in the extra, a fresh
  `pip install "locus-sdk[oci]"` boots cleanly but the first
  `.complete()` raises `ModuleNotFoundError: No module named 'openai'`.
  The OCI Generative AI service speaks the OpenAI Chat Completions wire
  protocol, so this dependency is mandatory for any consumer of the
  `[oci]` extra. Pinned alongside the `[openai]` extra.

- **`Agent.add_tool()` / `Agent.add_tools()` post-construct API.**
  `Agent.__init__` compiles `config.tools` into the runtime
  `_tool_registry` once, but the dataclass field stays writable —
  meaning post-construct mutation of `agent.config.tools` was a silent
  no-op (the model never saw the added tool). The new methods register
  on the live registry and mirror into `config.tools` so a re-init
  reconstructs the same shape. Common shape: orchestrator constructs
  first, then `Agent.as_tool(specialist)` wrappers are attached
  afterwards. The silent-mutation behaviour is now pinned by an explicit
  regression test so a future "helpful" patch can't quietly re-break it.

- **`InvokeResponse.duration_ms` is real wall time.** Previously
  hardcoded `0.0`; the `agent.run(...)` async iteration is now wrapped
  in `time.perf_counter()`. Every client-side latency metric reading the
  field was getting zeros.

- **`InvokeResponse.success` is derived from `stop_reason`.** Previously
  hardcoded `True` regardless of outcome — runs that terminated with
  `reason="error"`, `"max_iterations"`, or `"tool_loop"` came back as
  `success=true`. Now backed by a module-level
  `_INVOKE_SUCCESS_REASONS = {"complete", "confidence_met",
  "terminal_tool"}` set and an `_invoke_success(reason)` helper, both
  unit-tested. Callers can branch on the boolean without parsing the
  reason string.

- **`OCIOpenAIModel` auth-mode error is self-fixing.** The constructor
  `ValueError` for zero or two auth modes now names both valid call
  shapes (`profile='<section_from_~/.oci/config>'` for the API-key path
  vs. `auth_type='instance_principal'|'resource_principal'|
  'security_token'|'delegation_token'` together with `compartment_id=`)
  and echoes the actual `profile=` / `auth_type=` values back. Saves the
  next user a doc round-trip.

## [0.2.0b9] - 2026-05-14

### Feat — opt-in LLM protocol picker + workbench cognitive routing

- **`LLMProtocolPicker`** — second selection mode for the cognitive
  router. Pass an instance to
  `CognitiveCompiler(protocol_picker=...)` and the model picks the
  protocol from the *filtered* candidate set (`handles ∋
  primary_goal ∧ risk_max ≥ frame.risk ∧ requires_capabilities ⊆
  caps`) instead of the rule-based `_rank_key()` tuple comparison.
  Default behaviour is **unchanged** — opt in per compiler instance.
- **Filter-then-pick invariant.** The compiler filters candidates
  with the new public `ProtocolRegistry.filter_candidates()` *before*
  the picker sees anything. If zero survive, raises
  `NoMatchingProtocolError` without an LLM call. If exactly one
  survives, returns it without an LLM call (token saving). If
  multiple survive, the picker disambiguates.
- **Safe fallback.** If the picker raises (`PickerError` /
  arbitrary exception) or returns an id not in the candidate set,
  the compiler falls back to `_rank_key()` and emits a new
  `router.protocol.picker_fallback` event. Emergent mode never
  reduces availability vs the rule-based path.
- **Observability:** `router.protocol.selected` event gains two
  fields — `method` (one of `rule_based`, `single_candidate`,
  `llm_picked`, `rule_based_fallback`) and `rationale` (the picker's
  one-sentence justification when LLM-picked). Additive — existing
  SSE consumers ignore unknown keys.
- **Workbench pattern: Cognitive routing.** New
  `/api/run/cognitive_routing` endpoint in the FastAPI runner. The
  patterns UI shows a Selection-mode segmented control (Rule-based
  ⬌ LLM picker), runs the dispatch in-process, captures the
  `method` + `rationale` off the event bus, and renders a chip
  with the protocol id + method badge + rationale callout above
  the reply.
- **UX fix:** sidebar tabs (`Tutorials | Skills | Protocols |
  Patterns`) now wrap onto a second row at narrow viewport widths
  via `flex-wrap: wrap` — the rightmost tab no longer clips off
  invisible.
- **Docs:** new `concepts/router.md#emergent-picker-opt-in-second-mode`
  section explains the filter-then-pick invariant, fallback
  contract, and `method` enum. New tutorial 59 (`Emergent routing`)
  runs both modes side-by-side. Updated `workbench.md` catalogue
  (8 → 9 patterns) with a dedicated "Cognitive routing pattern"
  subsection.
- **OG / social card wiring.** The branded
  `docs/img/og-card.png` (1280×640) shipped with the repo but was
  never injected into the docs site's head. The mkdocs Material
  `extrahead` override now emits the canonical OG + Twitter Card
  meta tag set per page, so sharing a `locusagents.oracle.com` URL
  on Slack / X / LinkedIn / Discord / Teams unfurls with the
  locus brand card and a tailored per-page title + description.
  (The GitHub repo URL's social preview is a separate setting
  that requires a one-time manual upload at the repo's Settings →
  Social preview.)

## [0.2.0b8] - 2026-05-14

### Fix — DALL-E 3 deprecation + home-page enterprise voice

- **`OpenAIImageProvider`** default model changed from `"dall-e-3"`
  (deprecated by OpenAI) to `"gpt-image-1"`. Existing callers that pin
  `model=` continue to work; only the default changed.
- Live integration test (`test_openai_image_provider_round_trip`)
  switched to `gpt-image-1` to match.
- **`docs/index.md`** rewritten in enterprise buyer voice. New
  hero copy ("Multi-agent workflows built for production."), three
  outcome-focused bullets covering production deployment,
  self-critiquing/grounded agents, and full causal traceability.
  Stat strip uses `<span style="white-space:nowrap">` wrappers on each
  protocol chip so the eight-pattern row never breaks awkwardly across
  lines.

## [0.2.0b7] - 2026-05-14

### Docs — OCI Responses surfaced across existing pages + voice pass

- **`concepts/providers/oci.md`** now lists three transports
  (`OCIOpenAIModel`, `OCIResponsesModel`, `OCIModel`) and includes
  the Responses architecture diagram + a "when to pick which" section
  cross-linked to [`concepts/oci-responses.md`](docs/concepts/oci-responses.md).
- **`how-to/oci-models.md`** transport table gains a Responses row
  plus a new "Responses transport — `OCIResponsesModel` (opt-in)"
  section covering both `store=True` (server-state) and `store=False`
  (ZDR-safe) modes.
- Both pages cross-link [tutorial 00](docs/tutorials/tutorial_00_oci_transports.md)
  (transports side-by-side), [tutorial 57](docs/tutorials/tutorial_57_oci_openai_chat.md)
  (OCIOpenAIModel deep dive) and
  [tutorial 58](docs/tutorials/tutorial_58_oci_responses.md)
  (OCIResponsesModel deep dive).
- **Voice pass** — locus is an *agentic* framework. Removed every
  occurrence of "deterministic" and "automatic" from user-facing
  docs (~50 instances across 27 files) and rewrote in active-voice
  prose. `ProtocolRegistry` is now a "typed registry / typed filter
  - rank" (still rule-based and auditable); previously "automatic"
  behaviours read as concrete subjects-and-verbs (e.g.
  "Locus picks them up natively" instead of "Locus picks them up
  automatically").
- `mkdocs build --strict` passes clean with the updated pages.

## [0.2.0b6] - 2026-05-14

### Fixed — OCI Responses live-shakedown follow-ups

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

## [0.2.0b1 → 0.2.0b5] - 2026-05-07 → 2026-05-14

Cumulative entries from the first five betas, kept together because the
release tags did not have one-to-one CHANGELOG sections at the time.
Individual MR numbers in parentheses anchor each item to its source change.

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

[Unreleased]: https://github.com/oracle-samples/locus/compare/v0.2.0b10...main
[0.2.0b10]: https://github.com/oracle-samples/locus/compare/v0.2.0b9...v0.2.0b10
[0.2.0b9]: https://github.com/oracle-samples/locus/compare/v0.2.0b7...v0.2.0b9
[0.2.0b8]: https://github.com/oracle-samples/locus/compare/v0.2.0b7...v0.2.0b9
[0.2.0b7]: https://github.com/oracle-samples/locus/compare/v0.2.0b6...v0.2.0b7
[0.2.0b6]: https://github.com/oracle-samples/locus/compare/v0.2.0b5...v0.2.0b6
[0.2.0b1 → 0.2.0b5]: https://github.com/oracle-samples/locus/compare/v0.1.0...v0.2.0b5
[0.1.0]: https://github.com/oracle-samples/locus/releases/tag/v0.1.0
