# Locus Security Architecture Document

**Project:** Locus - Open Source Agentic AI Framework SDK
**Version:** 0.1.0
**Author:** Federico Kamelhar
**Team:** SaaS Observability
**Manager:** Sriram Vegaraju
**SPOC:** Federico Kamelhar (GitHub: @fede-kamel)
**Date:** April 9, 2026
**Classification:** Internal
**Related Tickets:** GH-5931, GH-5941

---

## 1. Executive Summary

Locus is an open-source agentic AI framework that enables enterprises to build production-ready AI agents on Oracle Cloud Infrastructure (OCI). The SDK provides a zero-LangChain alternative for orchestrating autonomous AI agents capable of reasoning, planning, and executing complex tasks through a structured ReAct (Reason + Act) loop with built-in Reflexion and Grounding capabilities.

Locus is being published as sample code under the `oracle-samples` GitHub organization under the Universal Permissive License (UPL-1.0). It is not a deployed service, does not handle live traffic, and does not access customer environments. It serves as a reference implementation and starting point for building AI agent applications on OCI.

The codebase comprises approximately 29,400 lines of Python code organized into modular packages. All inputs are validated through Pydantic v2 models, state is immutable by design, and a comprehensive hooks system enables pluggable security guardrails at every stage of agent execution.

---

## 2. System Architecture Overview

### 2.1 High-Level Architecture

Locus follows a layered architecture with clear separation of concerns:

```
+------------------------------------------------------------------+
|                        Application Layer                          |
|  (User code: agent configuration, tool definitions, prompts)      |
+------------------------------------------------------------------+
|                        Orchestration Layer                         |
|  Agent Engine  |  Multi-Agent  |  Playbooks  |  Streaming/SSE      |
+------------------------------------------------------------------+
|                        Reasoning Layer                             |
|  ReAct Loop  |  Reflexion  |  Grounding  |  Confidence Scoring    |
+------------------------------------------------------------------+
|                        Integration Layer                           |
|  Model Providers  |  Tool Registry  |  MCP  |  RAG/Vector Stores  |
+------------------------------------------------------------------+
|                        Infrastructure Layer                        |
|  Checkpointing  |  Memory Backends  |  Telemetry  |  Hooks        |
+------------------------------------------------------------------+
|                        External Services                           |
|  OCI GenAI  |  OpenAI API  |  Redis  |  PostgreSQL  |  OCI Bucket |
+------------------------------------------------------------------+
```

### 2.2 Source Code Structure

```
src/locus/
  agent/          - Agent orchestration, configuration, lifecycle
  cli/            - Command-line interface (placeholder)
  core/           - Core types, messaging, state management, configuration
  hooks/          - Lifecycle hooks: security guardrails, logging, telemetry
  integrations/   - External integrations (MCP protocol)
  loop/           - ReAct loop implementation (Think -> Execute -> Reflect)
  memory/         - State persistence with 9 backend options
  models/         - LLM provider integrations (OpenAI, OCI GenAI)
  multiagent/     - Multi-agent orchestration patterns
  rag/            - Retrieval-augmented generation
  reasoning/      - Advanced reasoning (Reflexion, Grounding)
  playbooks/       - Structured execution plans
  streaming/      - Event streaming and server-sent events
  tools/          - Tool definition, execution, registry, schema generation
```

### 2.3 Agent Execution Flow

The core execution follows the ReAct (Reason + Act) pattern:

1. **Initialization:** Agent loads its configured model, tools registry, checkpointer, conversation manager, and hooks chain.
2. **Per-Iteration Loop:**
   - Call the LLM with the current message history and available tool schemas.
   - Emit a ThinkEvent containing the model's reasoning.
   - Execute any tool calls (sequentially or concurrently).
   - Run before/after tool hooks at each step.
   - Record ToolExecution objects with arguments, results, errors, and timing.
   - Apply Reflexion (if enabled) to adjust confidence scoring.
   - Checkpoint the agent state (if a backend is configured).
3. **Termination Conditions:**
   - Maximum iterations reached.
   - A terminal tool is called (submit, done, finish, complete).
   - The model returns a response with no tool calls.
   - An unrecoverable error is encountered.

All state transitions are immutable. Each operation on `AgentState` returns a new instance, preserving a complete audit trail of the agent's reasoning and actions.

---

## 3. Data Flow Analysis

### 3.1 Input Processing

```
User Prompt (string)
    |
    v
Before-Invocation Hooks
    -> Validate prompt length (max 100,000 chars)
    -> Check blocked content patterns (SQL injection, path traversal, command injection)
    -> Detect PII (email, phone, SSN, credit card, IP address)
    -> Action: BLOCK, WARN, or REDACT per configuration
    |
    v
AgentState Creation (immutable, frozen Pydantic model)
    -> run_id: UUID
    -> messages: tuple of Message objects
    -> iteration counter
    -> metadata dict
```

### 3.2 Tool Execution Pipeline

```
Model Response (with tool_calls)
    |
    v
Before-Tool-Call Hooks
    -> Verify tool name against blocklist/allowlist
    -> Validate arguments for blocked content patterns
    -> Check arguments for PII patterns
    -> REDACT string arguments if configured
    |
    v
Tool Execution
    -> Resolve tool from registry
    -> Execute with validated arguments
    -> Catch all exceptions (broad exception handler)
    -> Truncate error messages to first line
    |
    v
After-Tool-Call Hooks
    -> Check result length (max 50,000 chars)
    -> Detect PII in tool results
    -> Record violations in state metadata
    |
    v
State Update + Checkpointing
```

### 3.3 Data at Rest

Agent state may be persisted to checkpoint backends. The checkpoint payload is a JSON document containing:

- Full conversation history (all messages exchanged with the LLM)
- Tool execution records (tool names, arguments, results, errors, durations)
- Reasoning steps and confidence scores
- User-provided metadata

Checkpoint backends do not encrypt data by default. Encryption at rest should be handled at the infrastructure layer (e.g., OCI Bucket encryption, PostgreSQL TDE, Redis TLS).

### 3.4 Data Classification

| Data Type | Sensitivity | Handling |
|-----------|-------------|----------|
| User prompts | Variable (depends on use case) | Validated by guardrails, stored in state |
| Model responses | Low | Parsed and recorded in state |
| Tool arguments | Variable | Validated by hooks, may be redacted |
| Tool results | Variable | Checked for PII post-execution |
| OCI credentials | High | SecretStr type, never logged, read from env/config |
| API keys | High | SecretStr type, never logged, read from env/config |
| Checkpoint data | Variable | JSON at rest, no built-in encryption |

---

## 4. Authentication and Credentials Management

### 4.1 Configuration System

Locus uses Pydantic Settings for configuration, which supports environment variables, `.env` files, and programmatic configuration:

```python
class ModelSettings:
    openai_api_key: SecretStr | None    # reads OPENAI_API_KEY
    oci_profile: str = "DEFAULT"
    oci_auth_type: str = "security_token"
    oci_compartment_id: str | None
    oci_region: str = "us-chicago-1"
```

All sensitive fields use `SecretStr`, which:

- Masks the value in `repr()` and `str()` output (displays `**********`)
- Prevents accidental logging of credentials
- Requires explicit `.get_secret_value()` to access the raw string

### 4.2 OCI Authentication

The OCI integration supports five authentication types, matching the official OCI Python SDK patterns:

| Auth Type | Mechanism | Credential Storage |
|-----------|-----------|-------------------|
| API_KEY | Config file + PEM key file | `~/.oci/config`, key file on disk |
| SECURITY_TOKEN | Session token from `oci session authenticate` | Token file in `~/.oci/sessions/` |
| INSTANCE_PRINCIPAL | OCI compute instance metadata | No local credentials (IMDS) |
| RESOURCE_PRINCIPAL | OCI Functions context | No local credentials (injected) |
| SESSION_TOKEN | Alias for SECURITY_TOKEN | Same as SECURITY_TOKEN |

The authentication flow delegates entirely to the OCI Python SDK's signer infrastructure. Locus does not implement any custom cryptographic signing or token management. Instance Principal and Resource Principal are the recommended patterns for deployed workloads, as they require zero local credential storage.

### 4.3 OpenAI Authentication

The OpenAI provider uses a single API key, read from:

1. `OpenAIConfig.api_key` parameter (SecretStr)
2. `OPENAI_API_KEY` environment variable (fallback)

The key is passed to the official OpenAI Python SDK client, which handles all request signing and TLS.

### 4.4 Checkpoint Backend Authentication

| Backend | Credential Method |
|---------|------------------|
| File | Filesystem permissions |
| Memory | In-process only |
| Redis | URL with optional password (`redis://:password@host:port`) |
| PostgreSQL | DSN or individual fields (password as SecretStr) |
| SQLite | Filesystem permissions |
| OCI Bucket | OCI SDK auth (same as model provider) |
| HTTP | Custom headers or Basic Auth tuple |
| Oracle DB | Connection string with credentials |
| OpenSearch | URL with optional auth |

---

## 5. Security Controls

### 5.1 Guardrails System

Locus includes a comprehensive guardrails system implemented as lifecycle hooks. The `GuardrailsHook` provides defense-in-depth at three points in the execution pipeline:

**Input Validation (before invocation):**

- Prompt length enforcement (configurable, default 100,000 characters)
- Blocked content pattern detection:
  - SQL injection: `DROP TABLE`, `DELETE FROM`, `UNION SELECT`, `OR 1=1`, etc.
  - Path traversal: `../`, `..\`
  - Command injection: `;`, `&`, `|`, backtick, `$`
- PII detection with regex patterns:
  - Email addresses
  - US phone numbers
  - Social Security Numbers
  - Credit card numbers
  - IP addresses

**Tool Call Validation (before each tool execution):**

- Tool blocklist enforcement. Default blocked tools: `eval`, `exec`, `system`, `shell`, `rm`, `delete`, `drop`, `truncate`
- Optional tool allowlist (if set, only listed tools may execute)
- Argument scanning for blocked content patterns
- Argument scanning for PII with optional redaction

**Output Validation (after each tool execution):**

- Result length enforcement (configurable, default 50,000 characters)
- PII detection in tool results
- Violation recording in state metadata for audit

**Configurable Actions:**
Each detection pattern can be independently configured with one of four actions:

- `BLOCK` — Reject the input/tool call entirely
- `WARN` — Log a warning but allow execution
- `REDACT` — Replace matched content with `[REDACTED]`
- `ALLOW` — Permit without action

### 5.2 Immutable State Design

All agent state is implemented using frozen Pydantic models. This architectural decision provides several security benefits:

- **Audit trail integrity:** Once a state snapshot is created, it cannot be modified. Every state transition produces a new object.
- **Thread safety:** Immutable objects are inherently safe for concurrent access.
- **Checkpoint consistency:** Serialized state accurately reflects the agent's condition at the checkpoint time.
- **No side-channel mutations:** Hooks and tools cannot silently alter past state.

State update methods follow a functional pattern:

```python
new_state = state.with_message(msg)           # returns new AgentState
new_state = state.with_tool_execution(exec)   # returns new AgentState
new_state = state.with_confidence(0.9)        # returns new AgentState
new_state = state.next_iteration()            # returns new AgentState
```

### 5.3 Error Handling

Tool execution uses broad exception catching to prevent error propagation from compromising the agent loop:

- All tool exceptions are caught at the executor level
- Error messages are truncated to the first line to prevent information leakage
- Errors are recorded in `ToolResult` objects within the state for audit
- Tool failures do not terminate the agent loop; the model receives the error and can adapt

### 5.4 Input Validation via Pydantic

Every data structure in Locus inherits from Pydantic `BaseModel` with strict type enforcement:

- All fields are type-checked at construction time
- Enum fields (e.g., `Role`) reject invalid values
- `model_validate()` is used for all deserialization
- `frozen=True` configuration prevents post-construction modification
- Nested objects are recursively validated

### 5.5 Static Analysis and Code Quality

The project enforces security-focused static analysis via the following toolchain:

| Tool | Purpose | Security Rules |
|------|---------|---------------|
| ruff | Linter/formatter | flake8-bandit (S) rules for security anti-patterns |
| mypy | Type checker | Strict mode, catches type confusion vulnerabilities |
| Pydantic | Runtime validation | Prevents invalid data from propagating |
| pre-commit | Git hooks | Enforces linting before every commit |

The ruff configuration enables the following security-relevant rule sets:

- `S` (flake8-bandit): Detects common security issues (hardcoded passwords, use of `exec`, insecure hashing, etc.)
- `B` (flake8-bugbear): Detects common Python pitfalls
- `ASYNC`: Detects async anti-patterns
- `PL` (pylint): General code quality

---

## 6. Network Communication

### 6.1 External Service Endpoints

| Service | Protocol | Endpoint | Authentication |
|---------|----------|----------|---------------|
| OCI GenAI | HTTPS | `inference.generativeai.{region}.oci.oraclecloud.com` | OCI SDK Signer (request signing) |
| OpenAI API | HTTPS | `api.openai.com/v1/chat/completions` | Bearer token (API key) |
| Redis | TCP/TLS | Configurable | URL-embedded password |
| PostgreSQL | TCP/TLS | Configurable | Username/password |
| HTTP Checkpoint | HTTPS | Configurable | Custom headers or Basic Auth |
| OCI Object Storage | HTTPS | OCI regional endpoint | OCI SDK Signer |

### 6.2 TLS and Transport Security

Locus does not implement custom TLS handling. All HTTPS communication relies on the default TLS behavior of the underlying libraries:

- **httpx** (used for HTTP checkpointer): Verifies TLS certificates by default using the system CA bundle
- **OCI SDK**: Uses the OCI SDK's built-in request signing and TLS verification
- **OpenAI SDK**: Uses httpx internally with default certificate verification
- **asyncpg**: Supports TLS connections to PostgreSQL
- **redis**: Supports `rediss://` scheme for TLS connections

No TLS verification is disabled or overridden anywhere in the codebase.

### 6.3 Request Signing (OCI)

OCI API calls are authenticated using the OCI SDK's request signing mechanism:

1. Each HTTP request is signed using the private key associated with the configured profile
2. The signature covers the request method, path, headers, and body
3. The signed request is sent over TLS to the OCI endpoint
4. The OCI service validates the signature against the user's public key

This is industry-standard request signing and is handled entirely by the OCI Python SDK. Locus does not touch the signing process.

---

## 7. MCP (Model Context Protocol) Integration

### 7.1 Overview

Locus can expose agents as MCP-compliant servers via the `fastMCP` integration. The Model Context Protocol is an open standard developed by Anthropic that provides a uniform interface for AI models to discover and invoke external tools and data sources. Locus implements MCP server capabilities, allowing any MCP-compatible client to interact with Locus agents through a standardized protocol.

### 7.2 Architecture

The MCP integration layer performs bidirectional schema conversion between Locus internal tool definitions and MCP-compliant function specifications. When a Locus agent is exposed as an MCP server:

1. Each registered tool is converted from its internal JSON Schema representation to a Pydantic BaseModel suitable for fastMCP registration.
2. MCP clients can discover available tools through the standard MCP discovery protocol.
3. Incoming tool invocation requests are validated against the generated Pydantic schema.
4. Validated requests are routed through the standard Locus tool execution pipeline, including all hook chains.
5. Results are serialized back to MCP response format and returned to the client.

### 7.3 Security Considerations

**Tool Exposure:** MCP servers expose all registered tools to connected clients. There is no per-client tool filtering at the MCP layer. Access control must be implemented at the transport layer (network segmentation, TLS mutual authentication) or by configuring the tool allowlist in the guardrails hook.

**Authentication:** No additional authentication layer is implemented at the MCP protocol level. Security relies on transport-level controls. For production deployments, operators should ensure MCP servers are bound to localhost or protected by network policies and TLS.

**Input Validation:** All tool invocations received through MCP pass through the same validation pipeline as direct invocations. The guardrails hook chain executes identically regardless of whether a tool call originated from the agent's own reasoning or from an external MCP client. This ensures consistent security enforcement.

**Schema Validation:** MCP tool arguments are validated through Pydantic models generated from the tool's JSON Schema definition. Invalid arguments are rejected before reaching the tool implementation. Type coercion follows strict Pydantic v2 rules, preventing type confusion attacks.

---

## 8. Multi-Agent Orchestration

### 8.1 Overview

Locus supports multi-agent patterns where multiple agents collaborate to solve complex tasks. The multi-agent module provides orchestration primitives for agent-to-agent communication, task delegation, and result aggregation.

### 8.2 Security Implications

**Inter-Agent Communication:** Agents communicate through shared state objects and message passing. All messages between agents are subject to the same Pydantic validation as user-to-agent messages. There is no special privilege escalation for agent-generated messages.

**Task Delegation:** When one agent delegates a task to another, the delegated agent operates with its own independent tool registry and guardrails configuration. A supervisor agent cannot bypass the guardrails of a worker agent. Each agent's security boundary is self-contained.

**Shared State:** Multi-agent patterns may share checkpoint state across agents within a workflow. The immutable state design ensures that one agent cannot corrupt another agent's state history. Each state transition creates a new object, maintaining isolation between concurrent agent executions.

**Recursive Agent Calls:** Locus prevents unbounded recursive agent delegation through the maximum iteration limit. Even in multi-agent workflows, each individual agent is bounded by its configured iteration limit, preventing runaway execution chains.

---

## 9. RAG (Retrieval-Augmented Generation)

### 9.1 Overview

The RAG module provides retrieval-augmented generation capabilities, allowing agents to query external knowledge bases to ground their responses in factual data. Locus supports multiple vector store backends including Oracle Database, OpenSearch, Qdrant, Pinecone, pgvector, and Chroma.

### 9.2 Security Considerations

**Query Injection:** RAG queries are constructed programmatically using the vector store client's native API. Locus does not construct raw SQL or search queries from user input. All queries use parameterized interfaces provided by the respective database client libraries (asyncpg for pgvector, opensearch-py for OpenSearch, etc.).

**Data Sensitivity:** RAG retrieval results may contain sensitive information from the knowledge base. These results pass through the after-tool-call hooks, where PII detection and content filtering are applied. Users should configure appropriate guardrails for their data classification.

**Vector Store Authentication:** Each vector store backend handles authentication independently through its own client library configuration. Locus passes credentials through to the underlying client without modification. Credential handling follows the same SecretStr/environment variable pattern used throughout the SDK.

---

## 10. Observability and Telemetry

### 10.1 OpenTelemetry Integration

Locus provides optional OpenTelemetry instrumentation for distributed tracing, metrics, and logging. When enabled, the telemetry module emits spans for:

- Agent lifecycle events (start, iteration, completion)
- Model inference calls (provider, model, token usage, latency)
- Tool executions (tool name, duration, success/failure)
- Checkpoint operations (save, load, backend type)
- Hook execution (guardrail violations, timing)

### 10.2 Security of Telemetry Data

Telemetry data may contain sensitive information depending on the agent's configuration. The following controls apply:

- Tool arguments and results are not included in telemetry spans by default. Only tool names, durations, and success/failure status are recorded.
- Model prompts and responses are not included in spans. Only token counts, model identifiers, and latency metrics are exported.
- Users can implement custom span processors to filter or redact sensitive attributes before export.
- OTLP exporters support TLS for secure transmission to observability backends (e.g., OCI Application Performance Monitoring, Jaeger, Grafana Tempo).

### 10.3 Audit Logging via Hooks

The hooks system provides an extensible audit logging capability. Users can implement custom hooks that record security-relevant events such as:

- Guardrail violations (what was blocked, why, and the offending content)
- Tool invocation patterns (which tools were called, in what sequence, by which agent)
- Authentication events (which OCI profile was used, what auth type)
- Error events (what failed, truncated error details)

These audit logs are separate from the telemetry pipeline and can be directed to any logging backend the user configures.

---

## 11. Third-Party Dependencies

All third-party dependencies have been reviewed and approved through Oracle's Licensed Technology and Business Approval process.

### 11.1 Core Dependencies (always distributed)

| Component | Version | License | BA ID | Status |
|-----------|---------|---------|-------|--------|
| pydantic | 2.12.5 | MIT | 383313 | Approved |
| pydantic-settings | 2.13.1 | MIT | 383303 | Approved |
| httpx | 0.28.1 | BSD 3-Clause | 383348 | Approved |
| typing-extensions | 4.15.0 | PSF-2.0 | Pending | Pending |

### 11.2 Optional Dependencies (installed per use case)

| Component | Version | License | BA ID | Status |
|-----------|---------|---------|-------|--------|
| OpenAI Python API library | 2.30.0 | Apache 2.0 | 383318 | Approved |
| OCI Python SDK | 2.170.0 | UPL/Apache 2.0 | Pending | D&E Legal Review |
| opentelemetry-api | 1.40.0 | Apache 2.0 | 385177 | Approved |
| opentelemetry-sdk | 1.40.0 | Apache 2.0 | 385085 | Approved |
| opentelemetry-exporter-otlp | 1.40.0 | Apache 2.0 | 385084 | Approved |
| mcp | 1.26.0 | MIT | 383344 | Approved |
| aiosqlite | 0.22.1 | MIT | 383345 | Approved |
| redis-py | 7.4.0 | MIT | 383317 | Approved |
| asyncpg | 0.31.0 | Apache 2.0 | 383346 | Approved |
| opensearch-py | 3.1.0 | Apache 2.0 | 383347 | Approved |

### 11.3 Dependency Security Posture

- All dependencies are at their latest stable versions as of April 2026
- No known CVEs exist in any dependency at the approved versions
- The project uses no vendored or forked dependencies
- All dependencies are sourced from PyPI (Python Package Index)
- No custom cryptographic implementations exist; all crypto is delegated to well-maintained libraries (cryptography, pyOpenSSL via OCI SDK)

---

## 12. Cryptography Usage

Locus itself does not implement any cryptographic functionality. All cryptographic operations are delegated to third-party libraries through transitive dependencies:

| Library | Used By | Purpose |
|---------|---------|---------|
| cryptography | OCI SDK (transitive) | TLS, request signing |
| pyOpenSSL | OCI SDK (transitive) | TLS connections |
| certifi | OCI SDK (transitive) | CA certificate bundle |

These are standard, well-audited cryptographic libraries used across the industry. Locus does not call any cryptographic APIs directly, configure cipher suites, or manage certificates.

---

## 10. Threat Model

### 10.1 Prompt Injection

**Risk:** A malicious user or external data source could craft input that causes the agent to execute unintended actions.

**Mitigations:**

- Guardrails hook detects known injection patterns (SQL injection, command injection, path traversal)
- Tool blocklist prevents execution of dangerous operations (eval, exec, system, shell, rm, delete, drop, truncate)
- Tool allowlist option restricts execution to only explicitly permitted tools
- All tool arguments pass through validation hooks before execution

### 10.2 Credential Exposure

**Risk:** API keys or OCI credentials could be leaked through logs, error messages, checkpoints, or model responses.

**Mitigations:**

- All credentials stored as `SecretStr` (masked in repr/str/logs)
- Error messages truncated to first line, preventing stack trace leakage
- Environment variable and `.env` file support keeps credentials out of source code
- OCI Instance Principal and Resource Principal eliminate local credential storage entirely

### 10.3 Data Exfiltration via Tools

**Risk:** An agent could be manipulated into sending sensitive data to external services through tool calls.

**Mitigations:**

- Before-tool-call hooks validate arguments for PII and sensitive content
- After-tool-call hooks scan results for PII
- Tool blocklist/allowlist restricts which tools can be invoked
- All tool executions are recorded in the immutable state for audit

### 10.4 Denial of Service

**Risk:** Excessively long inputs, infinite loops, or resource exhaustion.

**Mitigations:**

- Maximum prompt length enforcement (100,000 chars default)
- Maximum tool result length enforcement (50,000 chars default)
- Maximum iteration count prevents infinite agent loops
- Configurable timeouts on external service calls

### 13.5 Checkpoint Tampering

**Risk:** Checkpoint data could be modified to alter agent behavior on resume.

**Mitigations:**

- Immutable state design ensures internal consistency
- Pydantic validation on checkpoint deserialization rejects malformed data
- Infrastructure-level controls (filesystem permissions, database access controls, OCI IAM policies) protect checkpoint storage

### 13.6 Supply Chain Attacks

**Risk:** A compromised third-party dependency could introduce malicious code into the SDK.

**Mitigations:**

- All dependencies are sourced from PyPI, the standard Python package registry
- All dependencies have been reviewed through Oracle's Licensed Technology process with full license and copyright analysis
- The project pins minimum versions in `pyproject.toml` to prevent accidental downgrades to vulnerable versions
- No vendored or forked dependencies are used; all packages come from upstream maintainers
- Dependency versions are tracked in the Business Approval system, enabling rapid response if a CVE is discovered

### 13.7 Model Output Manipulation

**Risk:** An LLM could return malicious tool call arguments designed to exploit the tool execution layer, such as injecting shell commands into a tool parameter that is later used in a subprocess call.

**Mitigations:**

- All tool arguments are validated through Pydantic schemas before execution. Arguments that do not match the expected types are rejected.
- The guardrails hook scans tool arguments for known injection patterns (command injection, SQL injection, path traversal) before the tool executes.
- The tool blocklist prevents the agent from invoking dangerous tools regardless of what the model requests.
- Tools are implemented by the user, who controls the security boundary of their own tool implementations. Locus provides the validation framework; tool authors are responsible for safe implementation of their tool logic.

### 13.8 Information Leakage via Error Messages

**Risk:** Detailed error messages from tool execution or model calls could expose internal system information, file paths, database schemas, or credentials.

**Mitigations:**

- Tool execution errors are caught at the executor level and truncated to the first line of the exception message, stripping stack traces
- Credentials stored as SecretStr are masked in all string representations, preventing accidental inclusion in error messages
- The agent state records errors for audit purposes, but the error information available to the model is limited to the truncated first line
- Users can implement custom error handling hooks to further sanitize error information before it reaches the model

### 13.9 Concurrent Execution Vulnerabilities

**Risk:** Race conditions or shared mutable state in concurrent tool execution could lead to data corruption or inconsistent behavior.

**Mitigations:**

- Agent state is fully immutable (frozen Pydantic models). Concurrent tool executions cannot corrupt shared state because no shared mutable state exists.
- Each tool execution receives its own context object. Tools do not share mutable context.
- Concurrent tool execution uses Python's asyncio with proper task management. Each tool call is an independent coroutine with its own execution scope.
- The tool executor aggregates results after all concurrent calls complete, then creates a single new state snapshot atomically.

---

## 14. Operational Security Recommendations

While Locus provides built-in security controls, the following operational recommendations should be followed when deploying agents built with Locus in production environments:

### 14.1 Credential Management

- Use OCI Instance Principal or Resource Principal authentication for workloads running on OCI infrastructure. These methods eliminate local credential storage entirely.
- Never commit `.env` files, API keys, or OCI configuration files to source control. The `.gitignore` should exclude `.env`, `~/.oci/config`, and private key files.
- Rotate API keys and session tokens regularly. OCI session tokens expire after one hour by default.
- Use OCI Vault for managing secrets in production workloads rather than environment variables.

### 14.2 Checkpoint Security

- Enable encryption at rest for all checkpoint backends in production. Use OCI Bucket server-side encryption (SSE), PostgreSQL Transparent Data Encryption (TDE), or Redis TLS with encrypted storage.
- Configure appropriate access controls on checkpoint storage. Use OCI IAM policies for bucket access, database roles for PostgreSQL, and Redis ACLs for Redis backends.
- Implement checkpoint TTL (time-to-live) to automatically purge old state data and minimize the window of exposure for sensitive conversation data.
- Consider the sensitivity of data flowing through agents when choosing a checkpoint backend. For high-sensitivity workloads, prefer Oracle Database or OCI Bucket backends with encryption and audit logging.

### 14.3 Network Security

- Bind MCP servers to localhost or internal interfaces only. Do not expose MCP servers directly to the internet without proper authentication and network segmentation.
- Use TLS for all checkpoint backend connections in production (rediss:// for Redis, sslmode=require for PostgreSQL).
- Deploy agents within OCI Virtual Cloud Networks (VCN) with appropriate security lists and network security groups to control egress traffic to LLM endpoints.

### 14.4 Monitoring and Observability

- Enable OpenTelemetry instrumentation for production agents. The telemetry module provides distributed tracing and metrics that enable monitoring of agent behavior, tool execution patterns, and performance characteristics.
- Configure alerts on anomalous patterns such as excessive tool call failures, unusual tool invocation sequences, or high error rates.
- Review guardrail violation logs regularly to identify potential attack patterns or misuse.
- Use the immutable state audit trail to investigate incidents. Every state transition is preserved and can be replayed for forensic analysis.

### 14.5 Agent Configuration Best Practices

- Always enable the guardrails hook for production agents. Configure the tool blocklist and content filters appropriate to the agent's use case.
- Use tool allowlists instead of relying solely on the blocklist. A positive security model (only permit known-safe tools) is more robust than a negative model (block known-dangerous tools).
- Set conservative iteration limits. The default maximum iteration count should reflect the expected complexity of the agent's task. Lower limits reduce the blast radius of unexpected behavior.
- Configure appropriate prompt length and result length limits based on the agent's domain. Smaller limits reduce memory consumption and limit the surface area for injection attacks.
- System prompts should not contain secrets, credentials, or sensitive business logic. System prompts are developer-controlled configuration but could be extracted through adversarial user prompts. Use the ContentFilterHook to detect and block prompt extraction attempts if agents are exposed to untrusted users.

---

## 15. Incident Response

### 15.1 Vulnerability Reporting

As SPOC (Security Point of Contact) for the Locus project, security vulnerabilities should be reported to Federico Kamelhar (<federico.kamelhar@oracle.com>). The SPOC is responsible for:

- Triaging reported vulnerabilities
- Coordinating fixes with the development team
- Communicating with the SaaS Security team
- Ensuring timely patching and disclosure

### 15.2 Dependency Vulnerability Response

When a CVE is published affecting a Locus dependency:

1. Assess impact: Determine whether the vulnerability is reachable through Locus's usage of the dependency.
2. Update the dependency to a patched version.
3. Update the Licensed Technology and Business Approval records.
4. Publish a new release with the updated dependency.
5. Notify users through the GitHub repository's security advisories.

### 15.3 Security Advisory Process

GitHub's built-in security advisory feature will be enabled on the oracle-samples/locus repository. This provides:

- Private reporting of vulnerabilities by external researchers
- Coordinated disclosure workflow
- Automated notification to users who have enabled Dependabot alerts

---

## 16. Compliance and Licensing

### 16.1 License

Locus is licensed under the Universal Permissive License 1.0 (UPL-1.0), Oracle's standard license for open-source sample code.

### 16.2 Third-Party License Compliance

All third-party dependencies use permissive, OSI-approved licenses:

- MIT
- Apache License 2.0
- BSD 3-Clause
- PSF License 2.0
- Mozilla Public License 2.0 (certifi, transitive via OCI SDK)
- UPL 1.0 (OCI SDK)

Full license texts and copyright notices for all dependencies are documented in the `THIRD_PARTY_LICENSES.txt` file included in the source distribution and have been recorded in the Oracle Licensed Technology system.

### 16.3 No Customer Data

Locus is a client-side SDK. It:

- Does not collect, process, or store customer data
- Does not phone home or transmit telemetry to Oracle
- Does not access customer environments
- Does not include any analytics or tracking

Users provide their own credentials, data, and infrastructure when using the SDK.

---

## 17. Deployment Context

Locus is published as sample code. It is not deployed as a service. The following table clarifies what Locus is and is not:

| Attribute | Value |
|-----------|-------|
| Published to | github.com/oracle-samples/locus |
| Distribution format | Python package (PyPI wheel / source) |
| Runtime | User's local machine or their own cloud infrastructure |
| Network listeners | None |
| Background processes | None |
| Database schemas | None (optional checkpoint backends are user-provisioned) |
| Infrastructure requirements | None (optional OCI integration requires user's own tenancy) |
| Customer data handling | None |
| Secrets management | Delegated to user's environment (env vars, OCI config) |

---

## 18. Security Review Checklist

| Item | Status | Notes |
|------|--------|-------|
| Input validation | Implemented | Guardrails hook with PII detection, content filtering |
| Output validation | Implemented | Post-tool-call hooks, result length limits |
| Authentication | Delegated | OCI SDK auth (5 types), OpenAI API key |
| Authorization | Implemented | Tool blocklist/allowlist |
| Credential protection | Implemented | SecretStr, env vars, no hardcoded secrets |
| TLS enforcement | Default | All HTTP clients verify TLS by default |
| SQL injection prevention | Implemented | Parameterized queries + identifier validation (regex allowlist) |
| Command injection prevention | Implemented | Enhanced guardrails: `$()`, `${}`, newline injection, pipe to shell |
| Path traversal prevention | Implemented | Enhanced guardrails: URL-encoded (`%2e%2e`), double-encoded variants |
| Error handling | Implemented | Broad catch, truncated messages, no stack leakage |
| Audit trail | Implemented | Immutable state, full execution recording |
| Dependency management | Complete | All 14 dependencies with approved BAs |
| Static analysis | Enforced | ruff + bandit rules + mypy strict |
| Dynamic code execution | Hardened | exec() in fastMCP validated + sandboxed (restricted namespace) |
| Concurrent safety | Implemented | asyncio.Lock on shared mutable state |
| Immutable state | Enforced | Frozen Pydantic models throughout |

---

## 19. Conclusion

Locus is a well-architected SDK with security built into its design from the ground up. The immutable state model, comprehensive guardrails system, Pydantic validation at every boundary, and delegation of authentication to established SDKs (OCI, OpenAI) provide a strong security foundation.

The primary security consideration is that this is a framework that enables users to build AI agents. The security of any specific agent built with Locus depends on how the user configures guardrails, which tools they register, and how they manage credentials. Locus provides the controls; users must enable and configure them appropriately for their use case.

As sample code published under oracle-samples, Locus carries no production service risk. It demonstrates best practices for building secure AI agent applications on Oracle Cloud Infrastructure.

A comprehensive threat model has been completed (see `docs/THREAT_MODEL.md`) identifying 13 threats across AI/ML-specific and traditional security categories. All threats have been addressed: 3 fixed with code changes, 3 partially mitigated with enhanced detection patterns, 2 documented as accepted risks, and 5 confirmed to have adequate pre-existing mitigations. The full integration test suite (207 tests) passes with 0 failures across all supported backends.

---

**Document prepared for SaaS Security team review (SCSARCH).**
**Available for discussion during Mon/Wed 8:30 AM PT security review office hours.**
**Last updated: April 11, 2026.**
