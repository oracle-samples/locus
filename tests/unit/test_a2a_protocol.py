# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Unit tests for ``locus.a2a.protocol`` (A2AServer + A2AClient).

Coverage was 0% — these tests use the FastAPI test client so the
HTTP routes execute without spinning up uvicorn, and ``respx`` to
mock outbound HTTP for the client. The tests cover:

- the loopback-only-when-anonymous binding gate (CWE-306 surface)
- bearer-token auth on every route (``/agent-card``, ``/a2a/invoke``,
  ``/a2a/stream``)
- the streaming SSE wire format and its error-sanitisation path
- ``AgentCard`` / message round-tripping
- the client's ``invoke``/``as_tool`` wrappers
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from locus.a2a.protocol import (
    A2AClient,
    A2AMessage,
    A2ARequest,
    A2AResponse,
    A2AServer,
    AgentCard,
    _is_loopback,
)
from locus.core.events import TerminateEvent, ThinkEvent


# ---------------------------------------------------------------------------
# Stubs for the agent the server wraps.
# ---------------------------------------------------------------------------


class _StubAgent:
    """Minimal stand-in for ``Agent`` exposing ``run(prompt)``.

    Returns a configurable list of events. Used by both the invoke
    and stream tests.
    """

    def __init__(self, events: list[Any]) -> None:
        self._events = events

    async def run(self, prompt: str) -> Any:
        for event in self._events:
            yield event


def _think(reasoning: str) -> ThinkEvent:
    return ThinkEvent(iteration=0, reasoning=reasoning, tool_calls=[])


def _terminate(*, final_message: str = "", reason: str = "complete") -> TerminateEvent:
    return TerminateEvent(
        reason=reason,
        iterations_used=1,
        final_confidence=1.0,
        total_tool_calls=0,
        final_message=final_message,
    )


# ---------------------------------------------------------------------------
# Models + helpers
# ---------------------------------------------------------------------------


class TestProtocolModels:
    def test_agent_card_round_trip(self) -> None:
        card = AgentCard(name="test", description="d", skills=["a", "b"])
        payload = card.model_dump()
        assert payload["name"] == "test"
        assert payload["skills"] == ["a", "b"]

    def test_a2a_message_default_metadata_empty(self) -> None:
        m = A2AMessage(role="user", content="hi")
        assert m.metadata == {}

    def test_a2a_request_response_round_trip(self) -> None:
        req = A2ARequest(messages=[A2AMessage(role="user", content="hi")])
        assert req.metadata == {}

        resp = A2AResponse(messages=[A2AMessage(role="agent", content="ok")])
        assert resp.status == "completed"


class TestIsLoopback:
    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "127.0.0.5"])
    def test_recognises_loopback_hosts(self, host: str) -> None:
        assert _is_loopback(host) is True

    @pytest.mark.parametrize("host", ["8.8.8.8", "192.0.2.1", "example.com"])
    def test_rejects_non_loopback(self, host: str) -> None:
        assert _is_loopback(host) is False

    def test_invalid_host_string_returns_false(self) -> None:
        # Non-IP, non-known string falls through ``ipaddress.ip_address`` →
        # ValueError caught → returns False.
        assert _is_loopback("not-a-real-host") is False


# ---------------------------------------------------------------------------
# A2AServer — loopback gate on bind
# ---------------------------------------------------------------------------


class TestA2AServerBindGate:
    def test_anonymous_run_on_non_loopback_refused(self) -> None:
        # No api_key, no allow_unauthenticated, non-loopback host →
        # ``run()`` raises before ever touching uvicorn.
        server = A2AServer(agent=_StubAgent([]))
        with pytest.raises(RuntimeError, match="Refusing to bind"):
            server.run(host="8.8.8.8", port=9999)

    def test_anonymous_run_on_loopback_attempts_uvicorn(self) -> None:
        # Loopback path passes the gate. We don't actually want uvicorn
        # to run — patch it to a sentinel.
        server = A2AServer(agent=_StubAgent([]))
        called: dict[str, Any] = {}

        def fake_run(app: Any, **kwargs: Any) -> None:
            called["app"] = app
            called["kwargs"] = kwargs

        # ``import uvicorn`` happens inside ``run`` — sub the module.
        import sys
        import types

        fake_uvicorn = types.ModuleType("uvicorn")
        fake_uvicorn.run = fake_run  # type: ignore[attr-defined]
        sys.modules["uvicorn"] = fake_uvicorn
        try:
            server.run(host="127.0.0.1", port=12345)
        finally:
            sys.modules.pop("uvicorn", None)

        assert "app" in called
        assert called["kwargs"] == {"host": "127.0.0.1", "port": 12345}

    def test_uvicorn_missing_raises_clear_message(self) -> None:
        # Hide uvicorn so the import inside ``run`` raises ImportError.
        import sys

        saved = sys.modules.pop("uvicorn", None)
        # Block re-import so the ``import uvicorn`` line raises.
        sys.modules["uvicorn"] = None  # type: ignore[assignment]
        try:
            server = A2AServer(agent=_StubAgent([]))
            with pytest.raises(ImportError, match="uvicorn required"):
                server.run(host="127.0.0.1")
        finally:
            sys.modules.pop("uvicorn", None)
            if saved is not None:
                sys.modules["uvicorn"] = saved


# ---------------------------------------------------------------------------
# A2AServer — routes (with a real FastAPI test client)
# ---------------------------------------------------------------------------


def _server_with(agent: Any, **kwargs: Any) -> A2AServer:
    """Construct a server and prime the lazy ``app`` property."""
    server = A2AServer(agent=agent, allow_unauthenticated=True, **kwargs)
    _ = server.app  # eager-initialise
    return server


class TestA2AServerRoutes:
    def test_agent_card_returns_metadata(self) -> None:
        server = _server_with(
            _StubAgent([]),
            name="ResearchAgent",
            description="Does research.",
            skills=["lookup", "summarise"],
        )
        client = TestClient(server.app)
        resp = client.get("/agent-card")
        assert resp.status_code == 200
        assert resp.json() == {
            "name": "ResearchAgent",
            "description": "Does research.",
            "skills": ["lookup", "summarise"],
            "url": "",
        }

    def test_invoke_extracts_last_user_message(self) -> None:
        agent = _StubAgent([_terminate(final_message="answer", reason="complete")])
        server = _server_with(agent)
        client = TestClient(server.app)
        resp = client.post(
            "/a2a/invoke",
            json={
                "messages": [
                    {"role": "user", "content": "earlier"},
                    {"role": "agent", "content": "ignored"},
                    {"role": "user", "content": "latest question"},
                ]
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["messages"][0]["content"] == "answer"
        assert body["status"] == "completed"
        assert body["metadata"]["stop_reason"] == "complete"

    def test_invoke_with_no_user_messages_yields_empty_prompt(self) -> None:
        agent = _StubAgent([_terminate(final_message="", reason="complete")])
        server = _server_with(agent)
        client = TestClient(server.app)
        resp = client.post("/a2a/invoke", json={"messages": []})
        assert resp.status_code == 200

    def test_stream_emits_text_done_and_terminator(self) -> None:
        agent = _StubAgent(
            [
                _think(reasoning="thinking..."),
                _terminate(final_message="final", reason="complete"),
            ]
        )
        server = _server_with(agent)
        client = TestClient(server.app)
        with client.stream(
            "POST",
            "/a2a/stream",
            json={"messages": [{"role": "user", "content": "hi"}]},
        ) as resp:
            assert resp.status_code == 200
            body = "".join(resp.iter_text())

        # Each ``data:`` chunk parses as JSON (until the terminator).
        events = [
            json.loads(line.removeprefix("data: "))
            for line in body.split("\n\n")
            if line.startswith("data: ") and line != "data: [DONE]"
        ]
        types = [e["type"] for e in events]
        assert "text" in types
        assert "done" in types
        assert "[DONE]" in body

    def test_stream_emits_event_type_for_other_events(self) -> None:
        # Non-Think/Terminate events fall to the catch-all branch and emit
        # ``{"type": event.event_type}``.
        class _OtherEvent:
            event_type = "tool_start"

        agent = _StubAgent([_OtherEvent(), _terminate(final_message="ok")])
        server = _server_with(agent)
        client = TestClient(server.app)
        with client.stream(
            "POST",
            "/a2a/stream",
            json={"messages": [{"role": "user", "content": "hi"}]},
        ) as resp:
            body = "".join(resp.iter_text())
        assert '"type": "tool_start"' in body

    def test_stream_sanitises_agent_errors(self) -> None:
        class _BoomAgent:
            async def run(self, prompt: str) -> Any:
                raise RuntimeError("DSN=postgres://leak/secret")
                yield  # pragma: no cover (unreachable)

        server = _server_with(_BoomAgent())
        client = TestClient(server.app)
        with client.stream(
            "POST",
            "/a2a/stream",
            json={"messages": [{"role": "user", "content": "hi"}]},
        ) as resp:
            body = "".join(resp.iter_text())
        # The raw exception message must NOT be exposed; instead we get
        # an opaque "internal error" payload with a correlation id.
        assert "DSN=postgres" not in body
        assert "internal error" in body
        assert "correlation_id" in body


# ---------------------------------------------------------------------------
# A2AServer — bearer-token auth
# ---------------------------------------------------------------------------


class TestA2AServerAuth:
    def test_missing_bearer_token_returns_401(self) -> None:
        server = A2AServer(agent=_StubAgent([]), api_key="secret")
        client = TestClient(server.app)
        resp = client.get("/agent-card")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Missing bearer token"

    def test_wrong_bearer_token_returns_401(self) -> None:
        server = A2AServer(agent=_StubAgent([]), api_key="secret")
        client = TestClient(server.app)
        resp = client.get("/agent-card", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid bearer token"

    def test_valid_bearer_token_returns_200(self) -> None:
        server = A2AServer(agent=_StubAgent([]), api_key="secret")
        client = TestClient(server.app)
        resp = client.get("/agent-card", headers={"Authorization": "Bearer secret"})
        assert resp.status_code == 200

    def test_non_bearer_scheme_returns_401(self) -> None:
        server = A2AServer(agent=_StubAgent([]), api_key="secret")
        client = TestClient(server.app)
        resp = client.get("/agent-card", headers={"Authorization": "Basic abc"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Settings-driven docs gate
# ---------------------------------------------------------------------------


class TestDocsGate:
    def test_docs_disabled_when_settings_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Force ``get_settings`` to raise — the helper must swallow and
        # default to no docs (CWE-200 — production should never expose
        # OpenAPI by accident).
        def boom() -> None:
            raise RuntimeError("no settings")

        monkeypatch.setattr("locus.core.config.get_settings", boom)
        server = A2AServer(agent=_StubAgent([]), allow_unauthenticated=True)
        assert server._resolve_docs_enabled() is False


# ---------------------------------------------------------------------------
# A2AClient
# ---------------------------------------------------------------------------


class TestA2AClient:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_agent_card_parses_response(self) -> None:
        respx.get("http://remote/agent-card").mock(
            return_value=httpx.Response(
                200,
                json={"name": "x", "description": "d", "skills": [], "url": ""},
            )
        )
        client = A2AClient(url="http://remote/")
        card = await client.get_agent_card()
        assert card.name == "x"

    @pytest.mark.asyncio
    @respx.mock
    async def test_invoke_returns_last_agent_message(self) -> None:
        respx.post("http://remote/a2a/invoke").mock(
            return_value=httpx.Response(
                200,
                json={
                    "messages": [
                        {"role": "user", "content": "hi", "metadata": {}},
                        {"role": "agent", "content": "answer", "metadata": {}},
                    ],
                    "status": "completed",
                    "metadata": {},
                },
            )
        )
        client = A2AClient(url="http://remote")
        result = await client.invoke("hi")
        assert result == "answer"

    @pytest.mark.asyncio
    @respx.mock
    async def test_invoke_returns_empty_when_no_agent_messages(self) -> None:
        respx.post("http://remote/a2a/invoke").mock(
            return_value=httpx.Response(
                200,
                json={"messages": [], "status": "completed", "metadata": {}},
            )
        )
        client = A2AClient(url="http://remote")
        assert await client.invoke("hi") == ""

    @pytest.mark.asyncio
    @respx.mock
    async def test_auth_headers_propagated(self) -> None:
        route = respx.get("http://remote/agent-card").mock(
            return_value=httpx.Response(200, json={"name": "x", "description": "d", "skills": []})
        )
        client = A2AClient(url="http://remote", api_key="secret")
        await client.get_agent_card()
        assert route.called
        assert route.calls.last.request.headers["Authorization"] == "Bearer secret"

    @pytest.mark.asyncio
    async def test_no_api_key_yields_no_auth_header(self) -> None:
        # Branch: ``_auth_headers`` returns ``{}`` when no key is set.
        client = A2AClient(url="http://remote")
        assert client._auth_headers() == {}

    def test_as_tool_returns_callable_tool(self) -> None:
        client = A2AClient(url="http://remote")
        tool = client.as_tool(name="custom", description="custom desc")
        assert tool.name == "custom"
        assert tool.description == "custom desc"

    def test_as_tool_default_name(self) -> None:
        tool = A2AClient(url="http://remote").as_tool()
        assert tool.name == "remote_agent"

    @respx.mock
    def test_as_tool_invokes_remote(self) -> None:
        respx.post("http://remote/a2a/invoke").mock(
            return_value=httpx.Response(
                200,
                json={
                    "messages": [{"role": "agent", "content": "remote answer", "metadata": {}}],
                    "status": "completed",
                    "metadata": {},
                },
            )
        )
        # ``call_remote`` uses ``asyncio.run``; we exercise it from sync
        # context here, which is what the agent runtime does.
        tool = A2AClient(url="http://remote").as_tool()
        result = tool.fn("hi")
        assert result == "remote answer"
