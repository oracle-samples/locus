# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""A2A protocol implementation — agent-to-agent communication.

Provides a standardized way for agents to communicate across frameworks.
Based on the A2A protocol pattern from Strands SDK.

A2AServer wraps a Locus agent as an HTTP endpoint that accepts
standardized requests and returns standardized responses.

A2AClient wraps a remote A2A agent as a callable tool for Locus agents.

Security model
--------------
``A2AServer`` mirrors ``AgentServer``: every route requires a bearer
token when ``api_key`` / ``LOCUS_A2A_API_KEY`` is set. With no key, the
server refuses to bind to anything other than loopback unless
``allow_unauthenticated=True`` is passed explicitly. ``/agent-card`` is
scoped the same as the invocation routes so an anonymous peer cannot
enumerate the agent's tool inventory (CWE-306).
"""

from __future__ import annotations

import hmac
import ipaddress
import json
import logging
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field


_logger = logging.getLogger(__name__)

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _is_loopback(host: str) -> bool:
    if host in _LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class A2AMessage(BaseModel):
    """Standard A2A message format."""

    role: str  # "user" or "agent"
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2ARequest(BaseModel):
    """Request to an A2A agent."""

    messages: list[A2AMessage]
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2AResponse(BaseModel):
    """Response from an A2A agent."""

    messages: list[A2AMessage]
    status: str = "completed"  # "completed", "in_progress", "failed"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentCard(BaseModel):
    """Agent capability card for discovery."""

    name: str
    description: str
    skills: list[str] = Field(default_factory=list)
    url: str = ""


class A2AServer:
    """Expose a Locus agent as an A2A-compatible endpoint.

    Creates a FastAPI app with standardized A2A endpoints:
    - GET /agent-card — agent capability discovery
    - POST /a2a/invoke — synchronous invocation
    - POST /a2a/stream — streaming invocation

    Example:
        >>> from locus.a2a import A2AServer
        >>> server = A2AServer(agent=my_agent, name="Research Agent", api_key="secret")
        >>> server.run(port=8001)
    """

    def __init__(
        self,
        agent: Any,
        name: str = "Locus Agent",
        description: str = "",
        skills: list[str] | None = None,
        api_key: str | None = None,
        allow_unauthenticated: bool = False,
    ) -> None:
        self._agent = agent
        self._name = name
        self._description = description or f"A2A-compatible {name}"
        self._skills = skills or []
        self._api_key = api_key or os.environ.get("LOCUS_A2A_API_KEY") or None
        self._allow_unauthenticated = allow_unauthenticated
        self._app = None

    @property
    def app(self) -> Any:
        """Get or create the FastAPI app."""
        if self._app is None:
            self._app = self._create_app()
        return self._app

    def _resolve_docs_enabled(self) -> bool:
        try:
            from locus.core.config import get_settings

            return bool(get_settings().debug)
        except Exception:  # noqa: BLE001 — settings failure must not leak docs
            return False

    def _require_auth(self) -> Any:
        from fastapi import Header, HTTPException, status

        expected = self._api_key

        async def dependency(
            authorization: str | None = Header(default=None),
        ) -> str:
            if expected is None:
                return "anon"
            if not authorization or not authorization.lower().startswith("bearer "):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing bearer token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            presented = authorization.split(" ", 1)[1].strip()
            if not hmac.compare_digest(presented, expected):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid bearer token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return "authed"

        return dependency

    def _create_app(self) -> Any:
        try:
            from fastapi import Depends, FastAPI
            from fastapi.responses import StreamingResponse
        except ImportError as e:
            msg = "FastAPI required. Install with: pip install fastapi uvicorn"
            raise ImportError(msg) from e

        if self._api_key is None and not self._allow_unauthenticated:
            _logger.warning(
                "A2AServer: no api_key configured; will require "
                "loopback-only binding. Set LOCUS_A2A_API_KEY or pass "
                "allow_unauthenticated=True to override."
            )

        debug_docs = self._resolve_docs_enabled()
        app = FastAPI(
            title=f"A2A: {self._name}",
            docs_url="/docs" if debug_docs else None,
            redoc_url="/redoc" if debug_docs else None,
            openapi_url="/openapi.json" if debug_docs else None,
        )
        agent = self._agent

        if self._api_key is not None:
            auth_dep = Depends(self._require_auth())
        else:

            async def _anon() -> str:
                return "anon"

            auth_dep = Depends(_anon)

        @app.get("/agent-card")
        async def agent_card(principal: str = auth_dep) -> dict:
            return AgentCard(
                name=self._name,
                description=self._description,
                skills=self._skills,
            ).model_dump()

        @app.post("/a2a/invoke")
        async def invoke(
            request: A2ARequest,
            principal: str = auth_dep,
        ) -> dict:
            # Extract last user message as prompt
            user_msgs = [m for m in request.messages if m.role == "user"]
            prompt = user_msgs[-1].content if user_msgs else ""

            # Native async iteration — avoids the run_sync/future.result()
            # event-loop trap (CWE-1088).
            from locus.core.events import TerminateEvent

            final = ""
            stop_reason = "complete"
            iterations = 0
            success = True

            async for event in agent.run(prompt):
                if isinstance(event, TerminateEvent):
                    final = event.final_message or final
                    stop_reason = event.reason or stop_reason
                iterations += 1

            return A2AResponse(
                messages=[A2AMessage(role="agent", content=final)],
                status="completed" if success else "failed",
                metadata={
                    "stop_reason": stop_reason,
                    "iterations": iterations,
                },
            ).model_dump()

        @app.post("/a2a/stream")
        async def stream(
            request: A2ARequest,
            principal: str = auth_dep,
        ) -> StreamingResponse:
            from locus.core.events import TerminateEvent, ThinkEvent

            user_msgs = [m for m in request.messages if m.role == "user"]
            prompt = user_msgs[-1].content if user_msgs else ""

            async def event_generator() -> AsyncIterator[str]:
                try:
                    async for event in agent.run(prompt):
                        if isinstance(event, ThinkEvent):
                            data = {"type": "text", "content": event.reasoning or ""}
                        elif isinstance(event, TerminateEvent):
                            data = {"type": "done", "content": event.final_message or ""}
                        else:
                            data = {"type": event.event_type}
                        yield f"data: {json.dumps(data)}\n\n"
                except Exception:  # noqa: BLE001 — sanitize all agent errors
                    correlation_id = uuid.uuid4().hex
                    _logger.exception("A2A stream error (correlation_id=%s)", correlation_id)
                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "type": "error",
                                "error": "internal error",
                                "correlation_id": correlation_id,
                            }
                        )
                        + "\n\n"
                    )
                finally:
                    yield "data: [DONE]\n\n"

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        return app

    def run(self, host: str = "127.0.0.1", port: int = 8001, **kwargs: Any) -> None:
        """Run the A2A server.

        Defaults to loopback binding. Non-loopback bindings require
        either ``api_key`` to be set or ``allow_unauthenticated=True``.
        """
        if self._api_key is None and not self._allow_unauthenticated and not _is_loopback(host):
            msg = (
                f"Refusing to bind A2AServer to {host!r} without an API "
                "key. Set LOCUS_A2A_API_KEY, pass api_key=... to "
                "A2AServer, or pass allow_unauthenticated=True if an "
                "upstream proxy terminates auth."
            )
            raise RuntimeError(msg)

        try:
            import uvicorn
        except ImportError as e:
            msg = "uvicorn required. Install with: pip install uvicorn"
            raise ImportError(msg) from e
        uvicorn.run(self.app, host=host, port=port, **kwargs)


class A2AClient:
    """Call a remote A2A agent from Locus.

    Wraps a remote A2A endpoint as a tool that can be used by Locus agents.

    Example:
        >>> client = A2AClient(url="http://localhost:8001")
        >>> card = await client.get_agent_card()
        >>> response = await client.invoke("What is AI?")
        >>> tool = client.as_tool()  # Use as agent tool

    With authentication:
        >>> client = A2AClient(url="https://a2a.example.com", api_key="secret")
    """

    def __init__(self, url: str, api_key: str | None = None) -> None:
        self._url = url.rstrip("/")
        self._api_key = api_key

    def _auth_headers(self) -> dict[str, str]:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    async def get_agent_card(self) -> AgentCard:
        """Fetch the remote agent's capability card."""
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._url}/agent-card",
                headers=self._auth_headers(),
            )
            resp.raise_for_status()
            return AgentCard(**resp.json())

    async def invoke(self, prompt: str) -> str:
        """Send a message to the remote agent and get response."""
        import httpx

        request = A2ARequest(messages=[A2AMessage(role="user", content=prompt)])

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self._url}/a2a/invoke",
                json=request.model_dump(),
                headers=self._auth_headers(),
            )
            resp.raise_for_status()
            response = A2AResponse(**resp.json())

        agent_msgs = [m for m in response.messages if m.role == "agent"]
        return agent_msgs[-1].content if agent_msgs else ""

    def as_tool(self, name: str | None = None, description: str | None = None) -> Any:
        """Wrap this remote agent as a tool for Locus agents.

        Args:
            name: Tool name (fetches from agent card if not provided).
            description: Tool description.
        """
        from locus.tools.decorator import tool as tool_decorator

        client = self
        tool_name = name or "remote_agent"
        tool_desc = description or "Call a remote A2A agent"

        @tool_decorator(name=tool_name, description=tool_desc)
        def call_remote(prompt: str) -> str:
            """Send a request to a remote agent."""
            import asyncio

            return asyncio.run(client.invoke(prompt))

        return call_remote
