# Locus Security Remediation Summary

**Project:** Locus - Open Source Agentic AI Framework SDK
**Date:** April 11, 2026
**Author:** Federico Kamelhar
**SPOC:** Federico Kamelhar (GitHub: @fede-kamel)

---

## Overview

A comprehensive security assessment was conducted on the Locus SDK codebase. The assessment identified 14 threats across AI/ML-specific and traditional security categories. All threats have been addressed through code fixes, enhanced detection patterns, or documented as accepted risks with pre-existing mitigations.

**Test Results:** 207 integration tests, 0 skipped, 0 failures across all supported backends (Redis, PostgreSQL, pgvector, Qdrant, Chroma, OpenSearch, OCI Bucket, Oracle ADB, OCI GenAI, OpenAI).

---

## Code Fixes Applied

### 1. SQL Identifier Injection (T-SEC-01) -- CRITICAL

**Problem:** The PostgreSQL and SQLite checkpoint backends constructed SQL statements using f-string interpolation for table and schema names. If these values came from untrusted input, SQL injection was possible.

**Files changed:**

- `src/locus/memory/backends/postgresql.py`
- `src/locus/memory/backends/sqlite.py`

**Fix:** Added `_SAFE_SQL_IDENTIFIER` regex validation (`^[a-zA-Z_][a-zA-Z0-9_]{0,62}$`) that runs in `model_post_init()` for both `PostgreSQLConfig` and `SQLiteConfig`. Any table or schema name that doesn't match the pattern is rejected with a `ValueError` at configuration time, before any SQL is executed.

**Verification:** Unsafe identifiers like `DROP TABLE--`, `; DELETE`, `../etc` are rejected. Safe identifiers like `checkpoints`, `public`, `my_table_123` are accepted.

---

### 2. Dynamic Code Execution Hardening (T-SEC-02) -- CRITICAL

**Problem:** The fastMCP integration used `exec()` to dynamically create wrapper functions for MCP tool exposure. The description escaping was incomplete -- a crafted description could potentially break out of the docstring context.

**File changed:** `src/locus/integrations/fastmcp.py`

**Fix:** Four layers of defense applied to the `exec()` call:

1. **Identifier validation:** All tool names and parameter names validated against `^[a-zA-Z_][a-zA-Z0-9_]*$` regex before being interpolated into the generated code.
2. **Description sanitization:** All quote characters (`'`, `"`, `'''`, `"""`) and backslashes stripped from tool descriptions before insertion into the docstring.
3. **Restricted namespace:** The execution namespace contains only `_tool_execute` and `_json_dumps` -- no builtins, no other imports accessible.
4. **Traceable compilation:** `compile()` used with named source `<locus-mcp-{name}>` so any errors in generated code produce meaningful stack traces.

**Note:** Full removal of `exec()` was attempted but abandoned because fastMCP requires functions with explicit parameter signatures for introspection. A closure with `inspect.Signature` caused fastMCP to hang during tool registration. The hardened `exec()` is the correct solution.

**Verification:** AST parse confirms no unguarded `exec()`. All 63 fastMCP unit tests pass.

---

### 3. Enhanced Guardrails Patterns (T-AI-01, T-AI-02) -- HIGH

**Problem:** The default content detection patterns in the guardrails hook were too simplistic and could be bypassed with encoding, obfuscation, or alternative syntax.

**File changed:** `src/locus/hooks/builtin/guardrails.py`

**Fix:** Expanded all three pattern categories:

**SQL Injection** -- added detection for:

- `UNION [ALL] SELECT` (union-based injection)
- `ALTER TABLE`, `CREATE TABLE`, `RENAME TABLE` (DDL operations)
- `DROP TABLE IF EXISTS` (conditional drops)
- `--` comment-based bypass
- `/* */` inline comment bypass
- `; DROP`, `; DELETE`, `; TRUNCATE`, etc. (chained statements)

**Path Traversal** -- added detection for:

- `%2e%2e/` (URL-encoded `../`)
- `%252e%252e` (double URL-encoded)
- `.%2e/` and `%2e./` (mixed encoding variants)

**Command Injection** -- added detection for:

- `$()` command substitution
- `${}` variable expansion
- Newline-based injection (`\n cat`, `\n rm`, `\n wget`, etc.)
- Pipe to shell (`| bash`, `| sh`, `| zsh`, `| cmd`)
- Redirect to root (`> /`)

**Verification:** All 10 new pattern categories confirmed present via regex matching. 46 guardrails unit tests pass.

---

### 4. Circuit Breaker Race Condition (T-SEC-09) -- MEDIUM

**Problem:** The `CircuitBreakerExecutor` maintained mutable state (`_failure_counts` dict and `_open_circuits` set) without locking. In concurrent execution scenarios, race conditions could cause incorrect failure tracking.

**File changed:** `src/locus/tools/executor.py`

**Fix:** Added `asyncio.Lock` to protect all access to the shared mutable state:

- Lock acquired for the open-circuit check before tool execution
- Lock released during actual tool execution (I/O) to avoid blocking concurrent operations
- Lock re-acquired for failure count updates after tool execution completes

**Verification:** Lock field and `async with self._lock` usage confirmed in source. All executor unit tests pass.

---

## Test Infrastructure Improvements

### 5. Environment Variable Harmonization

**Problem:** Integration tests used inconsistent environment variable naming -- a mix of `LOCUS_OCI_PROFILE`, `OCI_PROFILE`, `LOCUS_MODEL_ID`, `ADB_DSN`, etc.

**Files changed:** 8 test files under `tests/integration/`

**Fix:** Unified all environment variables to functionality-focused names without the `LOCUS_` prefix:

| Old Name | New Name |
|----------|----------|
| `LOCUS_OCI_PROFILE` | `OCI_PROFILE` |
| `LOCUS_OCI_AUTH_TYPE` | `OCI_AUTH_TYPE` |
| `LOCUS_OCI_ENDPOINT` | `OCI_ENDPOINT` |
| `LOCUS_OCI_COMPARTMENT` / `LOCUS_OCI_COMPARTMENT_ID` | `OCI_COMPARTMENT` |
| `LOCUS_MODEL_ID` | `OCI_MODEL_ID` |
| `LOCUS_GPT_MODEL` | `OCI_GPT_MODEL` |
| `LOCUS_MODEL_PROVIDER` | `MODEL_PROVIDER` |
| `ADB_DSN` | `ORACLE_DSN` |
| `ADB_USER` | `ORACLE_USER` |
| `ADB_WALLET_LOCATION` | `ORACLE_WALLET` |

### 6. Removed Incorrect Python 3.14 Skips

**Problem:** Two test files had blanket `sys.version_info >= (3, 14)` skips based on outdated assumptions.

**Fixes:**

- **Oracle RAG (`test_oracle_rag.py`):** Removed Python 3.14 skip. Verified `oracledb` 3.4.2 thin client TLS works on Python 3.14 (the `DPY-6005` issue was fixed in recent versions).
- **Chroma (`test_new_vector_stores.py`):** Replaced version check with import-based detection (`try: import chromadb`). Verified `chromadb` 1.5.7 works on Python 3.14.

---

## Documentation Produced

### 7. Threat Model (`docs/THREAT_MODEL.md`)

Comprehensive threat model covering:

- 14 identified threats (4 AI-specific + 10 traditional)
- Trust boundary diagram
- Threat actor analysis
- Attack surface analysis (input and output vectors)
- STRIDE analysis
- Risk matrix with likelihood/impact/severity ratings
- Detailed recommendations with implementation status
- Remediation status table for all 14 threats
- Verification evidence with code snippets

### 8. Security Architecture Review (`docs/security-architecture-review.md`)

5,500-word security architecture document covering:

- System architecture with layered diagram
- Data flow analysis with trust boundaries
- Authentication and credentials management (5 OCI auth types)
- Security controls (guardrails, immutable state, Pydantic validation, static analysis)
- Network communication and TLS
- MCP, multi-agent, and RAG security implications
- Observability and telemetry data security
- Third-party dependency table with Business Approval IDs
- Cryptography usage
- 9-threat analysis with mitigations
- Operational security recommendations
- Incident response process
- Security review checklist

---

## Threat Summary

| ID | Threat | Severity | Status |
|----|--------|----------|--------|
| T-AI-01 | Prompt Injection | HIGH | Partially Mitigated (enhanced patterns) |
| T-AI-02 | Model Output Manipulation | MEDIUM | Partially Mitigated (enhanced patterns) |
| T-AI-03 | Indirect Injection via RAG | HIGH | Documented Risk (industry-wide) |
| T-AI-04 | System Prompt Extraction | LOW | Documented Risk |
| T-SEC-01 | SQL Identifier Injection | MEDIUM | **Fixed** |
| T-SEC-02 | Dynamic Code Execution (exec) | MEDIUM-HIGH | **Fixed** |
| T-SEC-03 | Credential Exposure | MEDIUM | Pre-existing (SecretStr) |
| T-SEC-04 | Information Leakage via Errors | LOW | Pre-existing (truncation) |
| T-SEC-05 | Supply Chain Attack | MEDIUM | Pre-existing (Oracle LT process) |
| T-SEC-06 | Checkpoint Tampering | LOW | Partially Mitigated (Pydantic validation) |
| T-SEC-07 | Denial of Service | LOW | Pre-existing (size/iteration limits) |
| T-SEC-08 | Network-Level Attacks | LOW | Pre-existing (TLS + request signing) |
| T-SEC-09 | Concurrent Execution | LOW-MEDIUM | **Fixed** |
| T-SEC-10 | Multi-Agent Privilege Escalation | LOW | Pre-existing (isolated boundaries) |

**Totals:**

- 3 fixed with code changes
- 3 partially mitigated with enhanced detection
- 2 documented as accepted risks
- 6 pre-existing adequate mitigations
- **0 unaddressed threats**

---

## Recommendations Status

| # | Priority | Recommendation | Status |
|---|----------|---------------|--------|
| 1 | Critical | SQL identifier validation | **Implemented** |
| 2 | Critical | Harden exec() in fastMCP | **Implemented** |
| 3 | High | Enhance guardrails patterns | **Implemented** |
| 4 | High | Document AI-specific risks | **Implemented** |
| 5 | Medium | Checkpoint HMAC signing | Deferred (sample code scope) |
| 6 | Medium | Credential handling in backends | Deferred (low risk, config-controlled) |
| 7 | Medium | Circuit breaker async locking | **Implemented** |
| 8 | Medium | RAG result sanitization hook | Deferred (existing hooks sufficient) |
| 9 | Low | Per-tool argument size limits | Deferred (global limits sufficient) |
| 10 | Low | Operational security docs | **Implemented** |

All critical and high priority items implemented. Deferred items are documented with rationale and production hardening guidance.

---

## Files Changed

**Security fixes (5 files):**

- `src/locus/hooks/builtin/guardrails.py` -- enhanced detection patterns
- `src/locus/integrations/fastmcp.py` -- hardened exec() with 4-layer defense
- `src/locus/memory/backends/postgresql.py` -- SQL identifier validation
- `src/locus/memory/backends/sqlite.py` -- SQL identifier validation
- `src/locus/tools/executor.py` -- asyncio.Lock for circuit breaker

**Test improvements (8 files):**

- `tests/integration/conftest.py`
- `tests/integration/test_checkpoint_backends.py`
- `tests/integration/test_checkpointer_adapters.py`
- `tests/integration/test_models_integration.py`
- `tests/integration/test_new_vector_stores.py`
- `tests/integration/test_oci_graph_integration.py`
- `tests/integration/test_oci_integration.py`
- `tests/integration/test_oracle_rag.py`
- `tests/integration/test_tutorials_13_21.py`

**Documentation (2 files):**

- `docs/THREAT_MODEL.md`
- `docs/security-architecture-review.md`

**Configuration (1 file):**

- `.gitignore`
