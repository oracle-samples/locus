# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tool execution strategies - 100% Pydantic."""

from __future__ import annotations

import asyncio
import re
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, PrivateAttr

from locus.core.messages import ToolCall, ToolResult
from locus.tools.context import ToolContext


# Patterns that may leak sensitive info in error messages.
# Full-replacement patterns: the match is replaced entirely with "[REDACTED]".
_SENSITIVE_PATTERNS = [
    re.compile(r"postgresql://\S+"),  # DB connection strings
    re.compile(r"redis://\S+"),
    re.compile(r"oracle://\S+"),
    re.compile(r"mongodb://\S+"),
    re.compile(r"mysql://\S+"),
    re.compile(r"host=['\"]?[^\s&#'\"]+['\"]?", re.IGNORECASE),
    re.compile(r"password=['\"]?[^\s&#'\"]+['\"]?", re.IGNORECASE),
    re.compile(r"api[_-]?key=['\"]?[^\s&#'\"]+['\"]?", re.IGNORECASE),
    re.compile(r"token=['\"]?[^\s&#'\"]+['\"]?", re.IGNORECASE),
    re.compile(r"/home/\S+"),  # Home directory paths
    re.compile(r"/Users/\S+"),
    re.compile(r"C:\\Users\\\S+"),
    re.compile(r"ocid1\.\w+\.oc1\.\.\S+"),  # OCI resource IDs
]

# Vendor API-key prefixes. Each alternative is linear (bounded character
# classes, no nested quantifiers) to avoid catastrophic backtracking.
# Lookarounds require a non-token boundary so we don't match inside other
# identifiers (e.g. a longer random string that happens to contain "sk-").
_VENDOR_PREFIX_RE = re.compile(
    r"(?<![A-Za-z0-9_-])("
    r"sk-ant-[A-Za-z0-9_-]{10,}"  # Anthropic
    r"|sk-proj-[A-Za-z0-9_-]{20,}"  # OpenAI project keys
    r"|sk-[A-Za-z0-9]{32,}"  # OpenAI classic / OpenRouter
    r"|AKIA[0-9A-Z]{16}"  # AWS access key id
    r"|AIza[0-9A-Za-z_-]{35}"  # Google API key
    r"|ghp_[A-Za-z0-9]{20,}"  # GitHub PAT (classic)
    r"|github_pat_[A-Za-z0-9_]{20,}"  # GitHub PAT (fine-grained)
    r")(?![A-Za-z0-9_-])"
)

# JWTs always begin with "eyJ" (base64 for "{"). Bounded repetition keeps
# matching linear.
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_=-]{4,}){0,2}")

# HTTP Authorization: Bearer ... — redact only the token value.
_BEARER_RE = re.compile(
    r"(Authorization:\s*Bearer\s+)(\S+)",
    re.IGNORECASE,
)

# URL query-string parameters whose values are opaque tokens. Catches
# cases the vendor-prefix patterns miss (OAuth codes, pre-signed URL
# signatures, short refresh tokens). Value-only redaction preserves the
# URL and path so the diagnostic stays readable.
_URL_WITH_QUERY_RE = re.compile(
    r"(https?|wss?|ftp)://"  # scheme
    r"([^\s/?#]+)"  # authority
    r"([^\s?#]*)"  # path
    r"\?([^\s#]+)"  # query (required)
    r"(#\S*)?"  # optional fragment
)
_SENSITIVE_QUERY_PARAMS = frozenset(
    {
        "access_token",
        "refresh_token",
        "id_token",
        "token",
        "api_key",
        "apikey",
        "client_secret",
        "password",
        "auth",
        "jwt",
        "session",
        "secret",
        "key",
        "code",
        "signature",
        "x-amz-signature",
    }
)


def _mask_token(token: str) -> str:
    """Mask a token. Long tokens keep a short prefix/suffix for debuggability."""
    if len(token) < 18:
        return "[REDACTED]"
    return f"{token[:6]}...{token[-4:]}"


def _redact_query_string(query: str) -> str:
    """Redact sensitive parameter values in a URL query string.

    Preserves parameter order, names, and non-sensitive values. Malformed
    pairs (no ``=``) are passed through unchanged.
    """
    parts: list[str] = []
    for pair in query.split("&"):
        if "=" not in pair:
            parts.append(pair)
            continue
        key, _, _ = pair.partition("=")
        if key.lower() in _SENSITIVE_QUERY_PARAMS:
            parts.append(f"{key}=[REDACTED]")
        else:
            parts.append(pair)
    return "&".join(parts)


def _redact_url_query_params(text: str) -> str:
    """Scan for URLs with query strings and redact known-sensitive params."""

    def _sub(m: re.Match[str]) -> str:
        scheme, authority, path = m.group(1), m.group(2), m.group(3)
        query = _redact_query_string(m.group(4))
        fragment = m.group(5) or ""
        return f"{scheme}://{authority}{path}?{query}{fragment}"

    return _URL_WITH_QUERY_RE.sub(_sub, text)


def redact_sensitive_text(text: str) -> str:
    """Apply all known secret-redaction patterns to ``text``.

    Safe to call on any string — non-matching text passes through unchanged.
    Unlike :func:`_sanitize_error` this does not truncate to the first line,
    so it can be used on multi-line log output or tool results.
    """
    if not text:
        return text
    # URL-aware redaction runs first so the bare-assignment patterns
    # (``token=X``, ``password=Y``, …) don't eat past ``&`` / ``#``.
    text = _redact_url_query_params(text)
    for pattern in _SENSITIVE_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    text = _VENDOR_PREFIX_RE.sub(lambda m: _mask_token(m.group(1)), text)
    text = _JWT_RE.sub(lambda m: _mask_token(m.group(0)), text)
    text = _BEARER_RE.sub(lambda m: f"{m.group(1)}{_mask_token(m.group(2))}", text)
    return text


def _sanitize_error(error: str) -> str:
    """Remove sensitive information from error messages (first line only)."""
    first_line = error.split("\n", maxsplit=1)[0]
    return redact_sensitive_text(first_line)


if TYPE_CHECKING:
    from locus.tools.registry import ToolRegistry


class ToolContextFactory(BaseModel):
    """Factory for creating ToolContext instances."""

    model_config = {"arbitrary_types_allowed": True}

    run_id: str
    agent_id: str | None = None
    iteration: int = 0
    state: Any = None
    invocation_metadata: dict[str, Any] = Field(default_factory=dict)

    def create(self, tool_call: ToolCall, tool_name: str) -> ToolContext:
        """Create a context for a tool call."""
        return ToolContext(
            tool_call_id=tool_call.id,
            tool_name=tool_name,
            agent_id=self.agent_id,
            run_id=self.run_id,
            iteration=self.iteration,
            state=self.state,
            invocation_metadata=self.invocation_metadata,
        )


class ToolExecutor(BaseModel, ABC):
    """
    Base class for tool execution strategies.

    Subclasses implement different execution patterns
    (sequential, concurrent, rate-limited, etc.)
    """

    model_config = {"arbitrary_types_allowed": True}

    @abstractmethod
    async def execute(
        self,
        tool_calls: list[ToolCall],
        registry: ToolRegistry,
        ctx_factory: ToolContextFactory | None = None,
    ) -> list[ToolResult]:
        """
        Execute a batch of tool calls.

        Args:
            tool_calls: Tool calls to execute
            registry: Tool registry to look up tools
            ctx_factory: Optional factory for creating tool contexts

        Returns:
            List of tool results
        """
        ...


class SequentialExecutor(ToolExecutor):
    """Execute tools one at a time."""

    async def execute(
        self,
        tool_calls: list[ToolCall],
        registry: ToolRegistry,
        ctx_factory: ToolContextFactory | None = None,
    ) -> list[ToolResult]:
        """Execute tools sequentially."""
        results: list[ToolResult] = []

        for tc in tool_calls:
            result = await self._execute_one(tc, registry, ctx_factory)
            results.append(result)

        return results

    async def _execute_one(
        self,
        tool_call: ToolCall,
        registry: ToolRegistry,
        ctx_factory: ToolContextFactory | None,
    ) -> ToolResult:
        """Execute a single tool call."""
        start = time.perf_counter()

        try:
            tool = registry.get(tool_call.name)
            if tool is None:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                    content="",
                    error=f"Unknown tool: {tool_call.name}",
                )

            # Create context if factory provided
            ctx = None
            if ctx_factory:
                ctx = ctx_factory.create(tool_call, tool_call.name)

            # Execute
            result = await tool.execute(ctx=ctx, **tool_call.arguments)

            duration = (time.perf_counter() - start) * 1000

            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=result,
                duration_ms=duration,
            )

        except Exception as e:  # noqa: BLE001
            duration = (time.perf_counter() - start) * 1000
            error_type = type(e).__name__
            error_msg = _sanitize_error(str(e))
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content="",
                error=f"{error_type}: {error_msg}",
                duration_ms=duration,
            )


class ConcurrentExecutor(ToolExecutor):
    """Execute tools concurrently with optional concurrency limit."""

    max_concurrency: int = Field(default=10, ge=1)

    async def execute(
        self,
        tool_calls: list[ToolCall],
        registry: ToolRegistry,
        ctx_factory: ToolContextFactory | None = None,
    ) -> list[ToolResult]:
        """Execute tools concurrently."""
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def execute_with_limit(tc: ToolCall) -> ToolResult:
            async with semaphore:
                return await self._execute_one(tc, registry, ctx_factory)

        tasks = [execute_with_limit(tc) for tc in tool_calls]
        results = await asyncio.gather(*tasks)

        return list(results)

    async def _execute_one(
        self,
        tool_call: ToolCall,
        registry: ToolRegistry,
        ctx_factory: ToolContextFactory | None,
    ) -> ToolResult:
        """Execute a single tool call."""
        start = time.perf_counter()

        try:
            tool = registry.get(tool_call.name)
            if tool is None:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    name=tool_call.name,
                    content="",
                    error=f"Unknown tool: {tool_call.name}",
                )

            ctx = None
            if ctx_factory:
                ctx = ctx_factory.create(tool_call, tool_call.name)

            result = await tool.execute(ctx=ctx, **tool_call.arguments)

            duration = (time.perf_counter() - start) * 1000

            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=result,
                duration_ms=duration,
            )

        except Exception as e:  # noqa: BLE001
            duration = (time.perf_counter() - start) * 1000
            error_type = type(e).__name__
            error_msg = _sanitize_error(str(e))
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content="",
                error=f"{error_type}: {error_msg}",
                duration_ms=duration,
            )


class CircuitBreakerExecutor(ToolExecutor):
    """
    Executor with circuit breaker pattern.

    Stops calling a tool after consecutive failures.
    """

    delegate: ToolExecutor = Field(default_factory=ConcurrentExecutor)
    failure_threshold: int = Field(default=3, ge=1)
    _failure_counts: dict[str, int] = PrivateAttr(default_factory=dict)
    _open_circuits: set[str] = PrivateAttr(default_factory=set)
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    model_config = {"arbitrary_types_allowed": True}

    async def execute(
        self,
        tool_calls: list[ToolCall],
        registry: ToolRegistry,
        ctx_factory: ToolContextFactory | None = None,
    ) -> list[ToolResult]:
        """Execute with circuit breaker protection."""
        results: list[ToolResult] = []

        for tc in tool_calls:
            async with self._lock:
                if tc.name in self._open_circuits:
                    results.append(
                        ToolResult(
                            tool_call_id=tc.id,
                            name=tc.name,
                            content="",
                            error=f"Circuit breaker open for tool: {tc.name}",
                        )
                    )
                    continue

            # Execute via delegate (outside lock to avoid holding during I/O)
            [result] = await self.delegate.execute([tc], registry, ctx_factory)

            # Update failure tracking under lock
            async with self._lock:
                if result.error:
                    count = self._failure_counts.get(tc.name, 0) + 1
                    self._failure_counts[tc.name] = count
                    if count >= self.failure_threshold:
                        self._open_circuits.add(tc.name)
                else:
                    self._failure_counts[tc.name] = 0

            results.append(result)

        return results

    def reset(self, tool_name: str | None = None) -> None:
        """Reset circuit breaker state."""
        if tool_name:
            self._failure_counts.pop(tool_name, None)
            self._open_circuits.discard(tool_name)
        else:
            self._failure_counts.clear()
            self._open_circuits.clear()
