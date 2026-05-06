"""Locus workbench backend — pattern runner.

A single FastAPI app that exposes one endpoint per locus pattern. Each
endpoint accepts a JSON body with the user's provider config, builds an
``Agent`` (or composed multi-agent shape) on the fly, and returns the
result.

Provider config (``ProviderConfig``) supports four auth modes:

- ``openai``     — needs ``api_key`` + ``model``
- ``anthropic``  — needs ``api_key`` + ``model``
- ``oci-session``— OCI session-token auth, ``profile`` + ``compartment_id``
- ``oci-apikey`` — OCI API-key auth, ``profile`` + ``compartment_id``

Instance / resource principals are intentionally NOT supported — the
playground runs locally against developer credentials.

Endpoints (all POST, all return ``{reply, events}``):

- ``/api/patterns``                    catalog of patterns + descriptions
- ``/api/run/agent``                   one-shot agent (tutorial 01)
- ``/api/run/agent_with_tools``        agent + tools (tutorial 02)
- ``/api/run/composition``             SequentialPipeline (tutorial 25)
- ``/api/run/orchestrator``            Orchestrator + Specialists (17)
- ``/api/run/stategraph_loop``         critic loop with cycles (43)
- ``/api/run/map_reduce``              Send fan-out + reduce (42)
- ``/api/run/structured_output``       output_schema → typed verdict (44)

Adding a new pattern is ~20 lines: write a builder function that returns
``(agent_or_runnable, run_fn)``, then register it in ``PATTERNS``.
"""

# This is workbench / playground code — relax a handful of ruff rules that
# only matter for production. Keep ruff format on; just silence the lint
# nits that don't apply here.
# ruff: noqa: BLE001, E402, N806, N814, ASYNC230

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator as _AI
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Provider config — exactly one of four auth modes.
# ---------------------------------------------------------------------------


class ProviderConfig(BaseModel):
    """User-supplied model credentials. One config per request."""

    provider: Literal["openai", "anthropic", "oci-session", "oci-apikey"]
    model: str = Field(default="", description="primary model id (slot A)")
    # Optional secondary slots so a tutorial can mix models — e.g. haiku
    # for triage, sonnet for the deep specialist. Both fall through to
    # ``model`` (slot A) when empty. Same provider + credentials as A.
    model_b: str | None = None
    model_c: str | None = None
    api_key: str | None = None
    profile: str | None = None
    region: str = "us-chicago-1"
    compartment_id: str | None = None
    # OCI only: "v1" | "auto" | "sdk". v1 = /openai/v1/chat/completions
    # (OCIOpenAIModel) — the default. sdk = native OCI GenAI chat shape
    # (OCIModel). "auto" routes Cohere R-series → sdk, everything else → v1.
    oci_transport: Literal["auto", "v1", "sdk"] = "v1"


def _is_oci_sdk_family(model_id: str) -> bool:
    """Cohere R-series models go through OCI's proprietary chat shape (SDK
    transport / OCIModel). Everything else (openai.*, meta.*, google.*,
    xai.*, plus non-R Cohere) speaks the OpenAI-compatible v1 endpoint
    (OCIOpenAIModel). Same rule examples/config.py uses."""
    mid = model_id.lower()
    return mid.startswith("cohere.command-r")


def build_model(cfg: ProviderConfig) -> Any:
    """Construct a Locus model client from the user's provider config."""
    if cfg.provider == "openai":
        if not cfg.api_key:
            raise HTTPException(400, "openai provider requires api_key")
        # Locus OpenAIModel reads OPENAI_API_KEY by default; pass it through.
        os.environ["OPENAI_API_KEY"] = cfg.api_key
        from locus.models.native.openai import OpenAIModel

        return OpenAIModel(model=cfg.model or "gpt-5")

    if cfg.provider == "anthropic":
        if not cfg.api_key:
            raise HTTPException(400, "anthropic provider requires api_key")
        os.environ["ANTHROPIC_API_KEY"] = cfg.api_key
        from locus.models.native.anthropic import AnthropicModel

        return AnthropicModel(model=cfg.model or "claude-sonnet-4-6")

    if cfg.provider in ("oci-session", "oci-apikey"):
        model_id = cfg.model or "openai.gpt-5.5-2026-04-23"
        profile = cfg.profile or "DEFAULT"
        # Honour an explicit transport choice; fall back to the
        # examples/config.py auto rule when "auto" or unset.
        if cfg.oci_transport == "sdk":
            use_sdk = True
        elif cfg.oci_transport == "v1":
            use_sdk = False
        else:
            use_sdk = _is_oci_sdk_family(model_id)
        if use_sdk:
            # Cohere R-series → SDK transport. The OCI Python SDK builds
            # its endpoint from the *profile's* region in ~/.oci/config
            # (e.g. MY_PROFILE lists us-ashburn-1) which usually doesn't
            # match where GenAI is deployed. Override service_endpoint
            # explicitly using the user-supplied region so the request
            # actually lands in us-chicago-1.
            from locus.models import OCIAuthType, OCIModel

            auth_type = (
                OCIAuthType.SECURITY_TOKEN if cfg.provider == "oci-session" else OCIAuthType.API_KEY
            )
            region = cfg.region or "us-chicago-1"
            endpoint = f"https://inference.generativeai.{region}.oci.oraclecloud.com"
            return OCIModel(
                model_id=model_id,
                profile_name=profile,
                auth_type=auth_type,
                compartment_id=cfg.compartment_id,
                service_endpoint=endpoint,
            )
        # Everything else → OpenAI-compatible /openai/v1 transport.
        from locus.models.providers.oci.openai_compat import OCIOpenAIModel

        return OCIOpenAIModel(
            model=model_id,
            profile=profile,
            compartment_id=cfg.compartment_id,
            region=cfg.region or "us-chicago-1",
        )

    raise HTTPException(400, f"unknown provider: {cfg.provider}")


# ---------------------------------------------------------------------------
# Request/response shape.
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    prompt: str
    provider: ProviderConfig


class RunEvent(BaseModel):
    kind: str
    text: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class RunResponse(BaseModel):
    reply: str
    events: list[RunEvent] = Field(default_factory=list)
    model: str = ""
    provider: str = ""


# ---------------------------------------------------------------------------
# Patterns.
# ---------------------------------------------------------------------------


async def _drive_agent(agent: Any, prompt: str) -> tuple[str, list[RunEvent]]:
    """Drive an agent's async event stream and collect (reply, events)."""
    events: list[RunEvent] = []
    final = ""
    async for ev in agent.run(prompt):
        kind = type(ev).__name__
        text = (
            getattr(ev, "tool_name", None)
            or getattr(ev, "final_message", None)
            or getattr(ev, "content", None)
            or getattr(ev, "reasoning", None)
            or ""
        )
        if not isinstance(text, str):
            text = str(text)
        events.append(RunEvent(kind=kind, text=text))
        if kind == "TerminateEvent":
            final = getattr(ev, "final_message", "") or ""
    return final, events


async def _drive_pipeline(runnable: Any, prompt: str) -> tuple[str, list[RunEvent]]:
    """Drive a non-Agent multi-agent shape.

    Each shape has its own entry point:
      * ``SequentialPipeline`` / ``ParallelPipeline`` / ``LoopAgent`` → ``await runnable.run(task)``
      * ``Orchestrator``                                              → ``await runnable.execute(task)``
      * Anything else with ``run_async`` / ``run_sync``               → fallthrough.
    """
    cls = type(runnable).__name__
    if cls in {"SequentialPipeline", "ParallelPipeline", "LoopAgent"}:
        out = await runnable.run(prompt)
    elif cls == "Orchestrator":
        out = await runnable.execute(prompt)
    elif hasattr(runnable, "run_async"):
        out = await runnable.run_async(prompt)
    elif hasattr(runnable, "run_sync"):
        import asyncio

        out = await asyncio.to_thread(runnable.run_sync, prompt)
    else:
        raise RuntimeError(f"don't know how to drive {cls}")
    msg = (
        getattr(out, "final_output", None)
        or getattr(out, "final_message", None)
        or getattr(out, "message", None)
        or str(out)
    )
    return msg, []


PATTERNS: list[dict[str, Any]] = [
    {
        "id": "agent",
        "title": "Basic agent",
        "tutorial": 1,
        "summary": "One Agent answers a prompt. Hello world for the SDK.",
    },
    {
        "id": "agent_with_tools",
        "title": "Agent + tools",
        "tutorial": 2,
        "summary": "Agent with two trivial tools — sees ReAct loop in action.",
    },
    {
        "id": "composition",
        "title": "Composition (Sequential)",
        "tutorial": 25,
        "summary": "Two agents chained: researcher → summariser.",
    },
    {
        "id": "orchestrator",
        "title": "Orchestrator + specialists",
        "tutorial": 17,
        "summary": "One coordinator, two specialists, parallel dispatch.",
    },
    {
        "id": "stategraph_loop",
        "title": "StateGraph (critic loop)",
        "tutorial": 43,
        "summary": "Writer → Critic loop until critic approves; allow_cycles.",
    },
    {
        "id": "map_reduce",
        "title": "Map-reduce code review",
        "tutorial": 42,
        "summary": "Send fan-out across N reviewers, reduce findings.",
    },
    {
        "id": "structured_output",
        "title": "Structured output (Verdict)",
        "tutorial": 13,
        "summary": "Pydantic output_schema — typed Verdict, not free text.",
    },
]


async def _run_agent(req: RunRequest) -> RunResponse:
    from locus.agent import Agent, AgentConfig

    agent = Agent(
        config=AgentConfig(
            model=build_model(req.provider),
            system_prompt="You are a concise assistant. Answer in one paragraph.",
            max_iterations=3,
        )
    )
    reply, events = await _drive_agent(agent, req.prompt)
    return RunResponse(reply=reply, events=events)


async def _run_agent_with_tools(req: RunRequest) -> RunResponse:
    from locus.agent import Agent, AgentConfig
    from locus.tools import tool

    @tool
    def add(a: float, b: float) -> float:
        """Sum two numbers."""
        return a + b

    @tool
    def reverse(s: str) -> str:
        """Reverse a string."""
        return s[::-1]

    agent = Agent(
        config=AgentConfig(
            model=build_model(req.provider),
            tools=[add, reverse],
            system_prompt="Use the tools when relevant. Answer succinctly.",
            max_iterations=5,
        )
    )
    reply, events = await _drive_agent(agent, req.prompt)
    return RunResponse(reply=reply, events=events)


async def _run_composition(req: RunRequest) -> RunResponse:
    from locus.agent import Agent, AgentConfig
    from locus.agent.composition import SequentialPipeline

    model = build_model(req.provider)
    researcher = Agent(
        config=AgentConfig(
            model=model,
            system_prompt="You are a researcher. List 3 key points about the topic, no fluff.",
            max_iterations=2,
        )
    )
    summariser = Agent(
        config=AgentConfig(
            model=model,
            system_prompt="Summarise the input as a single tight paragraph.",
            max_iterations=2,
        )
    )
    pipeline = SequentialPipeline(agents=[researcher, summariser])
    reply, events = await _drive_pipeline(pipeline, req.prompt)
    return RunResponse(reply=reply, events=events)


async def _run_orchestrator(req: RunRequest) -> RunResponse:
    from locus.agent import Agent, AgentConfig
    from locus.multiagent import Orchestrator, Specialist

    model = build_model(req.provider)
    researcher = Specialist(
        name="researcher",
        agent=Agent(
            config=AgentConfig(
                model=model,
                system_prompt="You research topics. Be thorough.",
                max_iterations=2,
            )
        ),
        description="Reads sources and explains topics.",
    )
    editor = Specialist(
        name="editor",
        agent=Agent(
            config=AgentConfig(
                model=model,
                system_prompt="You polish writing. Tighten, no padding.",
                max_iterations=2,
            )
        ),
        description="Edits and tightens prose.",
    )
    orch = Orchestrator(
        coordinator_model=model,
        specialists=[researcher, editor],
        system_prompt=("Delegate research to researcher, then ask editor to tighten."),
    )
    reply, events = await _drive_pipeline(orch, req.prompt)
    return RunResponse(reply=reply, events=events)


async def _run_stategraph_loop(req: RunRequest) -> RunResponse:
    """Writer → Critic loop with allow_cycles."""
    from locus.agent import Agent, AgentConfig
    from locus.multiagent.graph import GraphConfig, StateGraph

    model = build_model(req.provider)
    writer = Agent(
        config=AgentConfig(
            model=model,
            system_prompt="You write a one-paragraph answer. Keep it crisp.",
            max_iterations=2,
        )
    )
    critic = Agent(
        config=AgentConfig(
            model=model,
            system_prompt=(
                "You are a critic. Reply 'APPROVED' if the input is clear and "
                "factually safe, otherwise reply with one sentence of feedback."
            ),
            max_iterations=2,
        )
    )

    import asyncio

    async def write_node(state: dict[str, Any]) -> dict[str, Any]:
        prompt = state["prompt"]
        if "feedback" in state:
            prompt = f"{prompt}\n\nIncorporate this feedback: {state['feedback']}"
        out = await asyncio.to_thread(writer.run_sync, prompt)
        return {"draft": out.message or ""}

    async def critic_node(state: dict[str, Any]) -> dict[str, Any]:
        out = await asyncio.to_thread(critic.run_sync, state["draft"])
        text = (out.message or "").strip()
        if text.upper().startswith("APPROVED"):
            return {"approved": True}
        return {"approved": False, "feedback": text}

    def route(state: dict[str, Any]) -> str:
        return "end" if state.get("approved") else "writer"

    graph = StateGraph(config=GraphConfig(allow_cycles=True, max_iterations=4))
    graph.add_node("writer", write_node)
    graph.add_node("critic", critic_node)
    graph.set_entry_point("writer")
    graph.add_edge("writer", "critic")
    graph.add_conditional_edges("critic", route, {"writer": "writer", "end": "__end__"})
    result = await graph.execute({"prompt": req.prompt})
    final_state = getattr(result, "final_state", result)
    return RunResponse(
        reply=str(final_state.get("draft", ""))
        if isinstance(final_state, dict)
        else str(final_state)
    )


async def _run_map_reduce(req: RunRequest) -> RunResponse:
    """Send fan-out across N reviewers, reduce into one report."""
    from locus.agent import Agent, AgentConfig
    from locus.core.send import Send
    from locus.multiagent.graph import StateGraph

    model = build_model(req.provider)

    def reviewer(role: str) -> Agent:
        return Agent(
            config=AgentConfig(
                model=model,
                system_prompt=f"You are a {role} reviewer. Output one bullet on the input.",
                max_iterations=2,
            )
        )

    ROLES = ["security", "performance", "style"]

    async def split(state: dict[str, Any]) -> Any:
        return [Send("review", {"role": r, "input": state["prompt"]}) for r in ROLES]

    import asyncio

    async def review(state: dict[str, Any]) -> dict[str, Any]:
        out = await asyncio.to_thread(reviewer(state["role"]).run_sync, state["input"])
        return {"finding": {"role": state["role"], "text": out.message or ""}}

    async def reduce(state: dict[str, Any]) -> dict[str, Any]:
        findings = [v["finding"] for v in state.values() if isinstance(v, dict) and "finding" in v]
        report = "\n".join(f"[{f['role']}] {f['text']}" for f in findings)
        return {"report": report}

    graph = StateGraph()
    graph.add_node("split", split)
    graph.add_node("review", review)
    graph.add_node("reduce", reduce)
    graph.set_entry_point("split")
    graph.add_edge("split", "reduce")
    graph.add_edge("review", "reduce")
    result = await graph.execute({"prompt": req.prompt})
    final = getattr(result, "final_state", result)
    return RunResponse(
        reply=str(final.get("report", "")) if isinstance(final, dict) else str(final)
    )


async def _run_structured_output(req: RunRequest) -> RunResponse:
    """Verdict output_schema — typed Pydantic terminal artifact."""
    from locus.agent import Agent, AgentConfig

    class Verdict(BaseModel):
        winner: str
        confidence: float
        reasoning: str

    agent = Agent(
        config=AgentConfig(
            model=build_model(req.provider),
            output_schema=Verdict,
            system_prompt=(
                "You are a judge. Pick a winner from the input and report a "
                "Verdict with winner, confidence (0..1), and one-sentence reasoning."
            ),
            max_iterations=2,
        )
    )
    import asyncio

    result = await asyncio.to_thread(agent.run_sync, req.prompt)
    parsed = getattr(result, "parsed", None)
    if isinstance(parsed, Verdict):
        reply = (
            f"winner: {parsed.winner}\n"
            f"confidence: {parsed.confidence}\n"
            f"reasoning: {parsed.reasoning}"
        )
    else:
        reply = (
            getattr(result, "message", None) or getattr(result, "final_message", None) or ""
        ) or str(result)
    return RunResponse(reply=reply)


# ---------------------------------------------------------------------------
# Streaming — only for patterns that build a single Agent (agent,
# agent_with_tools, structured_output). Multi-stage patterns
# (orchestrator, pipeline, graph) still use the one-shot endpoint.
# ---------------------------------------------------------------------------


def _build_streaming_agent(pattern_id: str, provider: ProviderConfig) -> Any:
    from locus.agent import Agent, AgentConfig
    from locus.tools import tool

    model = build_model(provider)

    if pattern_id == "agent":
        return Agent(
            config=AgentConfig(
                model=model,
                system_prompt="You are a concise assistant. Answer in one paragraph.",
                max_iterations=3,
            )
        )
    if pattern_id == "agent_with_tools":

        @tool
        def add(a: float, b: float) -> float:
            """Sum two numbers."""
            return a + b

        @tool
        def reverse(s: str) -> str:
            """Reverse a string."""
            return s[::-1]

        return Agent(
            config=AgentConfig(
                model=model,
                tools=[add, reverse],
                system_prompt="Use the tools when relevant. Answer succinctly.",
                max_iterations=5,
            )
        )
    if pattern_id == "structured_output":

        class Verdict(BaseModel):
            winner: str
            confidence: float
            reasoning: str

        return Agent(
            config=AgentConfig(
                model=model,
                output_schema=Verdict,
                system_prompt=(
                    "You are a judge. Pick a winner from the input and report a "
                    "Verdict with winner, confidence (0..1), and one-sentence reasoning."
                ),
                max_iterations=2,
            )
        )
    return None  # not a stream-capable pattern


async def _stream_pattern(pattern_id: str, prompt: str, provider: ProviderConfig) -> _AI[str]:
    """Yield SSE-formatted lines.

    For the ``agent`` pattern (no tools) we go directly to ``model.stream()``
    so the user sees real token-by-token streaming. For ``agent_with_tools``
    and ``structured_output`` we drive the full agent loop and forward its
    coarser-grained events (Think / Tool / Terminate) — token streaming
    inside a ReAct loop isn't a thing the runtime currently offers.
    """
    if pattern_id == "agent":
        async for line in _stream_raw_model(prompt, provider):
            yield line
        return

    agent = _build_streaming_agent(pattern_id, provider)
    if agent is None:
        yield _sse(
            {"type": "ErrorEvent", "message": f"pattern {pattern_id!r} does not support streaming"}
        )
        return
    try:
        async for ev in agent.run(prompt):
            kind = type(ev).__name__
            payload: dict[str, Any] = {"type": kind}
            for attr in ("tool_name", "final_message", "content", "reasoning", "message"):
                v = getattr(ev, attr, None)
                if v is not None:
                    payload[attr] = v if isinstance(v, str) else str(v)
            yield _sse(payload)
            await asyncio.sleep(0)
    except Exception as exc:
        yield _sse({"type": "ErrorEvent", "message": f"{type(exc).__name__}: {exc}"})


async def _stream_raw_model(prompt: str, provider: ProviderConfig) -> _AI[str]:
    """Stream tokens directly from ``model.stream()`` — used for plain Q&A."""
    from locus.core.messages import Message

    try:
        model = build_model(provider)
        messages = [
            Message.system("You are a concise assistant. Answer in one paragraph."),
            Message.user(prompt),
        ]
        full = ""
        async for chunk in model.stream(messages):
            content = getattr(chunk, "content", None) or ""
            done = bool(getattr(chunk, "done", False))
            if content:
                full += content
                yield _sse(
                    {"type": "ModelChunkEvent", "chunk": True, "content": content, "done": done}
                )
            elif done:
                yield _sse({"type": "ModelChunkEvent", "chunk": True, "content": "", "done": True})
            await asyncio.sleep(0)
        yield _sse({"type": "TerminateEvent", "final_message": full})
    except Exception as exc:
        yield _sse({"type": "ErrorEvent", "message": f"{type(exc).__name__}: {exc}"})


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


PATTERN_RUNNERS: dict[str, Any] = {
    "agent": _run_agent,
    "agent_with_tools": _run_agent_with_tools,
    "composition": _run_composition,
    "orchestrator": _run_orchestrator,
    "stategraph_loop": _run_stategraph_loop,
    "map_reduce": _run_map_reduce,
    "structured_output": _run_structured_output,
}


# ---------------------------------------------------------------------------
# FastAPI app.
# ---------------------------------------------------------------------------


app = FastAPI(title="locus workbench runner", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


STREAMABLE = {"agent", "agent_with_tools", "structured_output"}


@app.get("/api/patterns")
def list_patterns() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in PATTERNS:
        out.append({**p, "streamable": p["id"] in STREAMABLE})
    return out


@app.post("/api/run/{pattern_id}")
async def run(pattern_id: str, req: RunRequest) -> RunResponse:
    runner = PATTERN_RUNNERS.get(pattern_id)
    if not runner:
        raise HTTPException(404, f"unknown pattern: {pattern_id}")
    try:
        out = await runner(req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc
    # Echo back the exact model id the request asked for so the UI can
    # show "via openai.gpt-5.5-2026-04-23" instead of relying on stale localStorage.
    out.model = req.provider.model or ""
    out.provider = req.provider.provider
    return out


@app.post("/api/run/{pattern_id}/stream")
async def run_stream(pattern_id: str, req: RunRequest) -> StreamingResponse:
    if pattern_id not in PATTERN_RUNNERS:
        raise HTTPException(404, f"unknown pattern: {pattern_id}")
    if pattern_id not in STREAMABLE:
        raise HTTPException(400, f"pattern {pattern_id!r} doesn't support streaming yet")

    async def gen() -> _AI[str]:
        async for line in _stream_pattern(pattern_id, req.prompt, req.provider):
            yield line

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class ListModelsRequest(BaseModel):
    provider: ProviderConfig


# Curated OpenAI / Anthropic model lists — listing them via the provider
# APIs requires a valid api key, so we keep a small hand-rolled set for
# the dropdown. The backend will accept any model id the user types
# anyway; this is just discoverability.
_OPENAI_MODELS = [
    "gpt-5.5",
    "gpt-5.5-pro",
    "gpt-5.1",
    "gpt-5.1-codex",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-4.1",
    "gpt-4o",
    "gpt-4o-mini",
    "o3",
    "o4-mini",
]
_ANTHROPIC_MODELS = [
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
]


@app.post("/api/models")
async def list_models(req: ListModelsRequest) -> dict[str, Any]:
    """Discoverable model ids for a given provider config.

    OpenAI / Anthropic return curated lists. OCI hits the live
    ``ListModels`` API against the user-supplied compartment + profile,
    so the dropdown reflects the user's tenancy + access policies.
    """
    p = req.provider.provider
    if p == "openai":
        return {"provider": p, "models": _OPENAI_MODELS}
    if p == "anthropic":
        return {"provider": p, "models": _ANTHROPIC_MODELS}

    # OCI — hit the GenAI control plane.
    if not req.provider.compartment_id:
        return {"provider": p, "models": [], "error": "compartment_id required"}
    try:
        import asyncio

        import oci

        cfg_path = "~/.oci/config"
        config = oci.config.from_file(cfg_path, req.provider.profile or "DEFAULT")

        signer: Any | None = None
        if "security_token_file" in config:
            with open(config["security_token_file"]) as f:
                token = f.read().strip()
            private_key = oci.signer.load_private_key_from_file(config["key_file"])
            signer = oci.auth.signers.SecurityTokenSigner(token, private_key)

        # Override region in the config for the call.
        config = {**config, "region": req.provider.region or "us-chicago-1"}

        client_kwargs: dict[str, Any] = {"config": config}
        if signer is not None:
            client_kwargs["signer"] = signer

        client = oci.generative_ai.GenerativeAiClient(**client_kwargs)

        def _list() -> list[str]:
            page = client.list_models(
                compartment_id=req.provider.compartment_id,
                lifecycle_state="ACTIVE",
                limit=400,
            ).data
            names = sorted({m.display_name for m in page.items if m.display_name})
            # Surface only chat-capable models (those whose names start with
            # one of the families we know).
            keep_prefix = ("openai.", "cohere.command", "meta.llama", "google.gemini", "xai.grok")
            return [n for n in names if n.startswith(keep_prefix)]

        models = await asyncio.to_thread(_list)
        return {"provider": p, "models": models}
    except Exception as exc:  # pragma: no cover — surface to UI
        return {"provider": p, "models": [], "error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# Workbench — list every model-only tutorial under examples/, serve its
# source code, and run user-edited copies in a subprocess with streamed
# stdout/stderr over SSE.
# ---------------------------------------------------------------------------

import re
import shutil
import tempfile
from pathlib import Path


# Tutorials kept out of the workbench because they require infra beyond
# the model (Postgres, vector store, MCP server, multi-process A2A,
# multimodal providers, dedicated AI cluster, etc.).
TUTORIAL_BLOCKLIST = {
    12,  # MCP integration
    20,  # checkpoint backends — Redis/Postgres
    21,  # SSE streaming — needs FastAPI server
    22,
    23,
    24,  # RAG suite
    28,  # agent server
    34,  # A2A protocol — needs separate process
    38,  # multimodal providers
    40,  # OCI DAC
}

# Tutorials that pause for human input via locus.core.interrupt(). The
# subprocess has no stdin attached, so these would hang until the
# harness timeout. Surfaced in the catalog (needs_stdin: true) so the
# UI can flag them and /api/tutorials/run can reject early.
TUTORIAL_NEEDS_STDIN = {9, 45, 46, 47, 48}

_TUTORIAL_DIR = (Path(__file__).resolve().parents[2] / "examples").resolve()


# Topic progression for the workbench sidebar. Each tutorial number is
# bound to one category; categories are rendered in the order declared
# here. Keep ranges contiguous so adding a new tutorial slots in
# without renumbering — gaps ("RAG suite blocked in workbench") leave
# the category empty rather than reshuffling.
TUTORIAL_CATEGORIES: list[dict[str, Any]] = [
    {
        "id": "fundamentals",
        "name": "Fundamentals",
        "description": "Build your first agent — model, tools, memory, streaming, hooks.",
        "members": [1, 2, 3, 4, 5],
    },
    {
        "id": "graphs",
        "name": "Graphs & flow control",
        "description": "StateGraph, conditional routing, reducers, HITL, advanced patterns.",
        "members": [6, 7, 8, 9, 10, 35, 36, 37],
    },
    {
        "id": "structured-output",
        "name": "Structured reasoning",
        "description": "Typed outputs, playbooks, reasoning patterns, GSAR grounding, evaluation.",
        "members": [13, 14, 15, 26, 39],
    },
    {
        "id": "composition",
        "name": "Composition",
        "description": "SequentialPipeline, ParallelPipeline, LoopAgent — wiring agents together.",
        "members": [25],
    },
    {
        "id": "multi-agent",
        "name": "Multi-agent",
        "description": "Swarm, handoff, orchestrator, specialists, A2A, debate, supervisor patterns.",
        "members": [11, 16, 17, 18, 33, 34, 42, 43, 44],
    },
    {
        "id": "production",
        "name": "Production",
        "description": "Guardrails, hooks (advanced), model providers, servers, checkpoint backends.",
        "members": [19, 20, 21, 27, 28, 29, 30, 38, 40],
    },
    {
        "id": "skills-plugins",
        "name": "Skills & plugins",
        "description": "Pluggable skill packs and integration plugins (MCP, fastmcp, more).",
        "members": [12, 31, 32],
    },
    {
        "id": "real-world",
        "name": "Real-world workflows",
        "description": "End-to-end use cases — incident response, contract review, audio chat.",
        "members": [45, 46, 47, 48, 49, 50],
    },
    {
        "id": "router",
        "name": "Cognitive router (PRISM)",
        "description": "Bounded graph generation — typed extraction → registry → compiler.",
        "members": [51],
    },
    {
        "id": "observability",
        "name": "Observability & SSE",
        "description": "Opt-in telemetry — run_context, event bus, agent yield bridge, token usage, full catalogue.",
        "members": [52, 53, 54, 55],
    },
]


def _tutorial_category(number: int) -> tuple[str, int]:
    """Return ``(category_id, order_within_category)`` for a tutorial.

    Tutorials not bound to a category fall under ``"misc"`` so a stray
    ``tutorial_99_*`` still renders. ``order_within_category`` is the
    member's index in the category's ``members`` list — preserves
    declaration order rather than numeric sort, so we can manually
    foreground a tutorial that's logically a prerequisite.
    """
    for cat in TUTORIAL_CATEGORIES:
        if number in cat["members"]:
            return cat["id"], cat["members"].index(number)
    return "misc", number


def _parse_tutorial(path: Path) -> dict[str, Any]:
    """Pull (id, number, title, summary, source) out of a tutorial file."""
    src = path.read_text()
    # Extract the leading triple-quoted docstring; first line is the
    # title, everything else up to "This tutorial covers:" is the summary.
    m = re.search(r'^"""(.*?)"""', src, re.DOTALL | re.MULTILINE)
    docstring = m.group(1).strip() if m else ""
    title = path.stem.replace("_", " ").title()
    summary = ""
    if docstring:
        lines = docstring.splitlines()
        title = lines[0].strip().rstrip(".")
        # Take the next non-empty narrative paragraph as summary.
        for ln in lines[1:]:
            if (
                ln.strip()
                .lower()
                .startswith(("this tutorial covers", "prerequisites", "difficulty"))
            ):
                break
            if ln.strip():
                summary = ln.strip()
                break
    num_match = re.match(r"tutorial_(\d+)_", path.name)
    number = int(num_match.group(1)) if num_match else 0
    category_id, order_in_category = _tutorial_category(number)
    return {
        "id": path.stem,
        "number": number,
        "title": title,
        "summary": summary,
        "filename": path.name,
        "source": src,
        "needs_stdin": number in TUTORIAL_NEEDS_STDIN,
        "category": category_id,
        "category_order": order_in_category,
    }


def _list_tutorials() -> list[dict[str, Any]]:
    if not _TUTORIAL_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(_TUTORIAL_DIR.glob("tutorial_*.py")):
        m = re.match(r"tutorial_(\d+)_", p.name)
        if not m:
            continue
        n = int(m.group(1))
        if n in TUTORIAL_BLOCKLIST:
            continue
        try:
            out.append(_parse_tutorial(p))
        except Exception:  # pragma: no cover
            continue

    # Sort by (category position, member position within the category,
    # tutorial number) so the sidebar reads top-to-bottom as a curated
    # learning path rather than a numeric file dump. ``misc`` falls to
    # the end via the sentinel category index.
    cat_index: dict[str, int] = {c["id"]: i for i, c in enumerate(TUTORIAL_CATEGORIES)}
    cat_index.setdefault("misc", len(TUTORIAL_CATEGORIES))
    out.sort(
        key=lambda t: (
            cat_index.get(t["category"], len(TUTORIAL_CATEGORIES)),
            t.get("category_order", t["number"]),
            t["number"],
        )
    )
    return out


@app.get("/api/tutorials")
def list_tutorials() -> list[dict[str, Any]]:
    return [{k: v for k, v in t.items() if k != "source"} for t in _list_tutorials()]


@app.get("/api/tutorials/categories")
def list_tutorial_categories() -> list[dict[str, Any]]:
    """Topic-progression categories the workbench renders as section
    headers. The ``members`` field is omitted from the wire payload —
    membership is already encoded on each tutorial as ``category``."""
    return [
        {"id": c["id"], "name": c["name"], "description": c["description"]}
        for c in TUTORIAL_CATEGORIES
    ]


@app.get("/api/tutorials/{tid}")
def tutorial_source(tid: str) -> dict[str, Any]:
    for t in _list_tutorials():
        if t["id"] == tid:
            return t
    raise HTTPException(404, f"unknown tutorial: {tid}")


# ---------------------------------------------------------------------------
# Skills — read-only catalogue of AgentSkills.io SKILL.md packages.
# ---------------------------------------------------------------------------


_SKILLS_DIR = (Path(__file__).resolve().parents[2] / "examples" / "skills").resolve()


# Topic groupings for the Skills sidebar. ``domain`` on a Skill is a
# free-text metadata field; we map common values to a curated category
# so the sidebar renders coherent groups. Skills whose domain doesn't
# match any group fall under ``"other"``.
SKILL_CATEGORIES: list[dict[str, Any]] = [
    {
        "id": "engineering",
        "name": "Engineering",
        "description": "Code review, API design, architecture rituals.",
        "domains": {"engineering", "code", "code-review", "api", "api-design", "architecture"},
    },
    {
        "id": "operations",
        "name": "Operations",
        "description": "Incident triage, on-call playbooks, observability runbooks.",
        "domains": {"operations", "ops", "incident", "incident-response", "sre", "observability"},
    },
    {
        "id": "data",
        "name": "Data & analytics",
        "description": "SQL queries, schema awareness, data exploration.",
        "domains": {"data", "sql", "analytics", "warehouse"},
    },
]


def _skill_category(skill: Any) -> str:
    """Map a skill's free-text domain tag onto one of the curated
    categories. Default ``"other"`` for anything unrecognised — the UI
    renders it as its own section so nothing disappears."""
    domain = ((skill.metadata or {}).get("domain") or "").lower().strip()
    skill_name = (skill.name or "").lower()
    for cat in SKILL_CATEGORIES:
        if domain in cat["domains"] or skill_name in cat["domains"]:
            return cat["id"]
    return "other"


def _skill_summary(skill: Any, dir_path: Path) -> dict[str, Any]:
    """Pick the catalogue-level fields off a Skill — full body is fetched
    per-skill via the detail endpoint."""
    return {
        "id": skill.name,
        "name": skill.name,
        "description": skill.description,
        "domain": (skill.metadata or {}).get("domain", ""),
        "allowed_tools": skill.allowed_tools or [],
        "license": skill.license,
        "path": str(dir_path),
        "category": _skill_category(skill),
    }


def _list_skills() -> list[tuple[Any, Path]]:
    """Load every SKILL.md package under examples/skills/.

    Returns (Skill, dir_path) tuples in registration order. Invalid
    SKILL.md packages are silently skipped (Skill.from_directory's
    behaviour) so a single bad package doesn't take the catalogue
    offline.
    """
    if not _SKILLS_DIR.is_dir():
        return []
    from locus.skills import Skill  # noqa: PLC0415 — import-light at module load

    out: list[tuple[Any, Path]] = []
    for child in sorted(_SKILLS_DIR.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            try:
                out.append((Skill.from_file(child), child))
            except Exception:  # noqa: BLE001 — bad packages must not nuke the catalogue
                continue
    return out


@app.get("/api/skills")
def list_skills() -> list[dict[str, Any]]:
    """Catalogue: name, description, domain tag, allowed-tools, license."""
    raw = [_skill_summary(sk, p) for sk, p in _list_skills()]
    cat_index: dict[str, int] = {c["id"]: i for i, c in enumerate(SKILL_CATEGORIES)}
    cat_index.setdefault("other", len(SKILL_CATEGORIES))
    raw.sort(key=lambda s: (cat_index.get(s["category"], len(SKILL_CATEGORIES)), s["name"]))
    return raw


@app.get("/api/skills/categories")
def list_skill_categories() -> list[dict[str, Any]]:
    """Topic groupings the workbench renders as Skills section headers."""
    return [
        {"id": c["id"], "name": c["name"], "description": c["description"]}
        for c in SKILL_CATEGORIES
    ]


@app.get("/api/skills/{sid}")
def skill_detail(sid: str) -> dict[str, Any]:
    """Full SKILL.md body + resource file listing for one skill."""
    for skill, dir_path in _list_skills():
        if skill.name == sid:
            return {
                **_skill_summary(skill, dir_path),
                "instructions": skill.instructions,
                "resources": skill.list_resources(max_files=50),
            }
    raise HTTPException(404, f"unknown skill: {sid}")


# ---------------------------------------------------------------------------
# Router protocols — the eight built-in orchestration shapes.
# ---------------------------------------------------------------------------


# Per-protocol description of what its builder *emits* at compile time.
# The router enforces these shapes via the structural-audit test suite
# (tests/unit/test_router_compiled_shape.py); reproducing them here lets
# the workbench display the runtime topology without importing the
# builder closures themselves.
_RUNTIME_SHAPES: dict[str, str] = {
    "direct_response": "Agent (single call) with the requested capability tools",
    "plan_execute_validate": "SequentialPipeline of 3 Agents: planner → executor → validator",
    "specialist_fanout": "ParallelPipeline of N Agents — one tool-bound Agent per capability",
    "debate": "ParallelPipeline of 2 debaters (pro/con) followed by a judge Agent",
    "codegen_test_validate": "LoopAgent — iterates until first line of output starts with PASS",
    "approval_gated_execution": "Single Agent wrapped by an approval interrupt before execution",
    "a2a_delegate": "A2AClient.invoke against the configured remote endpoint",
    "handoff_chain": "SequentialPipeline of N one-tool Agents — each link adds a fact and hands off",
}


# Protocol groupings ordered by execution-shape complexity. Renders as
# section headers in the Protocols sidebar so users see the cardinal
# shapes (single, linear, parallel, gated) up front and the specialised
# ones (a2a/handoff) further down.
PROTOCOL_CATEGORIES: list[dict[str, Any]] = [
    {
        "id": "single",
        "name": "Single shot",
        "description": "One Agent call, optional output_schema. Fastest path.",
        "members": ["direct_response"],
    },
    {
        "id": "linear",
        "name": "Linear pipelines",
        "description": "Sequential plan → execute → validate, including loops with stop conditions.",
        "members": ["plan_execute_validate", "codegen_test_validate"],
    },
    {
        "id": "parallel",
        "name": "Parallel fan-out",
        "description": "Multiple agents running concurrently, results merged by an orchestrator or judge.",
        "members": ["specialist_fanout", "debate"],
    },
    {
        "id": "delegation",
        "name": "Delegation",
        "description": "Pass the conversation across agents (in-process or remote A2A peers).",
        "members": ["handoff_chain", "a2a_delegate"],
    },
    {
        "id": "gated",
        "name": "Approval-gated",
        "description": "High-risk paths interrupted for human approval before execution.",
        "members": ["approval_gated_execution"],
    },
]


def _protocol_category(protocol_id: str) -> tuple[str, int]:
    for cat in PROTOCOL_CATEGORIES:
        if protocol_id in cat["members"]:
            return cat["id"], cat["members"].index(protocol_id)
    return "other", 0


def _protocol_summary(protocol: Any) -> dict[str, Any]:
    """Catalogue-level fields for one Protocol — same set the detail
    endpoint returns, just without the runtime_shape."""
    cat_id, order_in_cat = _protocol_category(protocol.id)
    return {
        "id": protocol.id,
        "name": protocol.id,
        "description": protocol.description,
        "handles": [t.value for t in protocol.handles],
        "primary_for": [t.value for t in protocol.primary_for],
        "requires_capabilities": list(protocol.requires_capabilities),
        "risk_max": protocol.risk_max.value,
        "cost": protocol.cost,
        "latency": protocol.latency,
        "supports_streaming": protocol.supports_streaming,
        "supports_repair": protocol.supports_repair,
        "category": cat_id,
        "category_order": order_in_cat,
    }


def _list_protocols() -> list[Any]:
    from locus.router import builtin_protocols  # noqa: PLC0415

    return list(builtin_protocols())


@app.get("/api/protocols")
def list_protocols() -> list[dict[str, Any]]:
    """The eight router protocol definitions, sorted by category."""
    raw = [_protocol_summary(p) for p in _list_protocols()]
    cat_index: dict[str, int] = {c["id"]: i for i, c in enumerate(PROTOCOL_CATEGORIES)}
    cat_index.setdefault("other", len(PROTOCOL_CATEGORIES))
    raw.sort(
        key=lambda p: (
            cat_index.get(p["category"], len(PROTOCOL_CATEGORIES)),
            p["category_order"],
            p["name"],
        )
    )
    return raw


@app.get("/api/protocols/categories")
def list_protocol_categories() -> list[dict[str, Any]]:
    """Topic groupings the workbench renders as Protocols section headers."""
    return [
        {"id": c["id"], "name": c["name"], "description": c["description"]}
        for c in PROTOCOL_CATEGORIES
    ]


@app.get("/api/protocols/{pid}")
def protocol_detail(pid: str) -> dict[str, Any]:
    """Full Protocol metadata + a description of the emitted runtime shape."""
    for p in _list_protocols():
        if p.id == pid:
            return {
                **_protocol_summary(p),
                "runtime_shape": _RUNTIME_SHAPES.get(p.id, "(no shape recorded)"),
            }
    raise HTTPException(404, f"unknown protocol: {pid}")


# ---------------------------------------------------------------------------
# Telemetry SSE endpoints — bridge ``locus.observability.EventBus`` over
# the wire so the workbench (or any consumer with curl) can watch events
# in real time.
# ---------------------------------------------------------------------------


def _sse_format(payload: dict[str, Any]) -> bytes:
    """Encode one ``StreamEvent.to_dict()`` payload as an SSE frame.

    Two carriage-return-terminated lines per event:
    ``event: <type>\\ndata: <json>\\n\\n``. The ``event:`` line lets
    EventSource consumers register typed listeners; the ``data:`` line
    is the JSON payload.
    """
    event_type = payload.get("event_type", "message")
    body = json.dumps(payload, default=str)
    return f"event: {event_type}\ndata: {body}\n\n".encode()


async def _sse_stream_run(run_id: str) -> _AI[bytes]:
    """Async generator for one run's events. Yields SSE frames until
    the bus closes the run, then yields a final ``done`` frame."""
    from locus.observability import get_event_bus  # noqa: PLC0415 — import-light

    yield b": connected\n\n"  # SSE comment, keeps proxies awake
    async for event in get_event_bus().subscribe(run_id):
        yield _sse_format(event.to_dict())
    yield b"event: done\ndata: {}\n\n"


async def _sse_stream_global() -> _AI[bytes]:
    """Global SSE stream — every event from every run."""
    from locus.observability import get_event_bus  # noqa: PLC0415 — import-light

    yield b": connected\n\n"
    async for event in get_event_bus().subscribe_global():
        yield _sse_format(event.to_dict())


# NB: `/__stats` MUST register before `/{run_id}` — FastAPI matches in
# declaration order, and `__stats` would otherwise match as
# ``run_id='__stats'`` and return an SSE stream instead of JSON.
@app.get("/api/events/__stats")
def sse_event_stats() -> dict[str, Any]:
    """Read-only snapshot of bus internals for debugging slow consumers."""
    from locus.observability import get_event_bus  # noqa: PLC0415

    return get_event_bus().stats()


@app.get("/api/events")
async def sse_events_global() -> StreamingResponse:
    """SSE stream of every event the bus publishes — monitoring view."""
    return StreamingResponse(
        _sse_stream_global(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/events/{run_id}")
async def sse_events_for_run(run_id: str) -> StreamingResponse:
    """SSE stream for a single cognitive dispatch.

    Subscribers receive every :class:`StreamEvent` with matching
    ``run_id`` plus a ``done`` sentinel when the bus closes the run.
    History (last N events) is replayed on connect.
    """
    return StreamingResponse(
        _sse_stream_run(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx — disable proxy buffering
            "Connection": "keep-alive",
        },
    )


# Bootstrap-emitted structured event lines start with this prefix so the
# parent can split them out from regular stdout. The subprocess writes
# the prefix; we strip + parse + republish on the bus.
_LE_PREFIX = "__LE__:"


async def _bridge_subprocess_line_to_bus(run_id: str, kind: str, text: str) -> None:
    """Republish one tutorial-subprocess output line on the EventBus.

    Lines that start with ``__LE__:`` are typed locus events
    (``ThinkEvent``, ``ToolStartEvent``, etc.) — the JSON payload
    becomes the StreamEvent ``data``. Everything else is republished
    as a plain ``tutorial.stdout`` / ``tutorial.stderr`` event so a
    bus subscriber gets the full output stream from one channel.
    """
    from locus.observability import StreamEvent, get_event_bus  # noqa: PLC0415

    bus = get_event_bus()
    if text.startswith(_LE_PREFIX):
        try:
            payload = json.loads(text[len(_LE_PREFIX) :])
        except json.JSONDecodeError:
            payload = {"raw": text}
        ev_type = payload.pop("type", "agent.event") if isinstance(payload, dict) else "agent.event"
        # Locus's typed events use CamelCase class names ("ThinkEvent",
        # "ToolStartEvent"); republish under a dotted lower-case shape
        # so subscribers can filter by prefix without knowing class names.
        normalised = "agent." + (
            ev_type.replace("Event", "").lower() if isinstance(ev_type, str) else "event"
        )
        await bus.publish(
            StreamEvent(
                run_id=run_id,
                event_type=normalised,
                data=payload if isinstance(payload, dict) else {"raw": payload},
            ),
        )
    else:
        await bus.publish(
            StreamEvent(
                run_id=run_id,
                event_type=f"tutorial.{kind}",
                data={"text": text},
            ),
        )


class WorkbenchRunRequest(BaseModel):
    source: str
    provider: ProviderConfig
    timeout_seconds: int = 120
    # When true, the bootstrap force-enables reflexion=True on every
    # Agent the tutorial creates — exposes chain-of-thought via
    # ReflectEvent (assessment + guidance per step) on any provider /
    # transport, since reflexion is an SDK feature, not a model feature.
    reflexion: bool = False


def _describe_provider(cfg: ProviderConfig) -> str:
    """One-line label for the bootstrap banner. Avoid leaking secrets."""
    if cfg.provider == "openai":
        return f"openai · {cfg.model or 'gpt-5'}"
    if cfg.provider == "anthropic":
        return f"anthropic · {cfg.model or 'claude-sonnet-4-6'}"
    if cfg.provider in ("oci-session", "oci-apikey"):
        tail = cfg.model or "openai.gpt-5"
        return f"{cfg.provider} · {cfg.profile or 'DEFAULT'} · {tail}"
    return cfg.provider


def _provider_env(cfg: ProviderConfig) -> dict[str, str]:
    """Translate a UI provider config into the env vars examples/config.py expects."""
    env: dict[str, str] = {}
    if cfg.provider == "openai":
        env["LOCUS_MODEL_PROVIDER"] = "openai"
        env["LOCUS_MODEL_ID"] = cfg.model or "gpt-5"
        if cfg.api_key:
            env["OPENAI_API_KEY"] = cfg.api_key
    elif cfg.provider == "anthropic":
        env["LOCUS_MODEL_PROVIDER"] = "anthropic"
        env["LOCUS_MODEL_ID"] = cfg.model or "claude-sonnet-4-6"
        if cfg.api_key:
            env["ANTHROPIC_API_KEY"] = cfg.api_key
    elif cfg.provider in ("oci-session", "oci-apikey"):
        env["LOCUS_MODEL_PROVIDER"] = "oci"
        env["LOCUS_MODEL_ID"] = cfg.model or "openai.gpt-5.5-2026-04-23"
    # Optional secondary slots — tutorials read these via get_model_b()
    # / get_model_c() in examples/config.py. Empty means "fall back to
    # slot A" so existing tutorials stay correct.
    if cfg.model_b:
        env["LOCUS_MODEL_ID_B"] = cfg.model_b
    if cfg.model_c:
        env["LOCUS_MODEL_ID_C"] = cfg.model_c
    if cfg.provider in ("oci-session", "oci-apikey"):
        if cfg.profile:
            env["LOCUS_OCI_PROFILE"] = cfg.profile
        if cfg.region:
            env["LOCUS_OCI_REGION"] = cfg.region
        if cfg.compartment_id:
            env["LOCUS_OCI_COMPARTMENT"] = cfg.compartment_id
        # examples/config.py reads LOCUS_OCI_TRANSPORT to override its
        # auto pick. The workbench subprocess inherits this env so the
        # tutorial's `from config import get_model` lands on the right
        # transport.
        if cfg.oci_transport != "auto":
            env["LOCUS_OCI_TRANSPORT"] = cfg.oci_transport
        env["LOCUS_OCI_AUTH_TYPE"] = (
            "security_token" if cfg.provider == "oci-session" else "api_key"
        )
    return env


import uuid as _uuid


# Active subprocess runs that can accept human-input responses via
# `POST /api/tutorials/runs/{run_id}/respond`. Keyed by run id, value is
# the asyncio subprocess so the endpoint can write JSON to its stdin.
_RUNS: dict[str, asyncio.subprocess.Process] = {}


def _split_future_imports(source: str) -> tuple[str, str]:
    """Pull the shebang + license header + module docstring + any
    ``from __future__`` imports off the front of *source* so they stay
    at the top of the generated file. Python's parser requires
    ``from __future__`` imports to precede every other statement.

    Returns ``(preamble, rest)``. If the source contains no future
    imports we return ``("", source)`` so the bootstrap goes on top
    unchanged.
    """
    lines = source.splitlines(keepends=True)
    n = len(lines)
    i = 0
    # 1. Optional shebang.
    if i < n and lines[i].startswith("#!"):
        i += 1
    # 2. Skip blank + `#` comment lines (license header etc.).
    while i < n and (lines[i].strip() == "" or lines[i].lstrip().startswith("#")):
        i += 1
    # 3. Optional module docstring (single or triple quoted).
    if i < n:
        stripped = lines[i].lstrip()
        for q in ('"""', "'''"):
            if stripped.startswith(q):
                rest_after_q = stripped[len(q) :]
                if q in rest_after_q:  # one-liner
                    i += 1
                else:
                    i += 1
                    while i < n and q not in lines[i]:
                        i += 1
                    if i < n:
                        i += 1
                break
    # 4. More blanks / comments / future imports.
    last_future = i
    while i < n:
        s = lines[i].strip()
        if s == "" or s.startswith("#"):
            i += 1
            continue
        if s.startswith("from __future__"):
            i += 1
            last_future = i
            continue
        break
    if last_future == 0:
        return "", source
    return "".join(lines[:last_future]), "".join(lines[last_future:])


@app.post("/api/tutorials/run")
async def run_tutorial(req: WorkbenchRunRequest) -> StreamingResponse:
    """Execute user-edited tutorial source in a subprocess; stream stdout/stderr as SSE.

    Each output line is wrapped in an SSE ``data:`` envelope with type
    ``stdout``, ``stderr``, ``exit``, or ``error``. The frontend renders a
    terminal-shaped log.

    Tutorials that call ``locus.core.interrupt()`` are supported now —
    the bootstrap monkey-patches ``interrupt`` to emit an
    ``InterruptEvent`` SSE line and block on stdin for the response.
    The frontend pops a modal and POSTs the answer to
    ``/api/tutorials/runs/{run_id}/respond`` which writes a JSON line
    to the subprocess's stdin.
    """
    repo_root = _TUTORIAL_DIR.parent
    examples_dir = _TUTORIAL_DIR
    src_dir = repo_root / "src"

    # Bootstrap: monkey-patch Agent.__init__ so every agent the tutorial
    # creates emits a typed event line per turn. Lines start with __LE__:
    # so the frontend can split them out from regular stdout. Only fires
    # when the tutorial hasn't already wired its own callback_handler.
    bootstrap = """\
import json as __le_json, sys as __le_sys, os as __le_os
__LE_PREFIX = "__LE__:"

# Hard guard: never let a tutorial silently fall back to MockModel. The
# workbench always sets LOCUS_MODEL_PROVIDER to a real provider, but
# guard against any tutorial that hardcodes mock or imports MockModel
# directly. Wraps `from config import get_model` so the returned object
# is asserted real before the tutorial uses it.
__SB_PROVIDER = "__SB_PROVIDER_VALUE__"
__le_sys.stdout.write(f"[locus-workbench] running against {__SB_PROVIDER}\\n")
__le_sys.stdout.flush()
try:
    import config as __sb_config
    __orig_get_model = __sb_config.get_model
    def __guarded_get_model(*a, **kw):
        m = __orig_get_model(*a, **kw)
        if type(m).__name__ == "MockModel":
            raise RuntimeError(
                "locus-workbench: refusing to run with MockModel. "
                "Set OpenAI / Anthropic / OCI provider in Provider settings."
            )
        return m
    __sb_config.get_model = __guarded_get_model
except Exception as __sb_err:
    __le_sys.stderr.write(f"[locus-workbench] guard install failed: {__sb_err}\\n")

def __le_emit__(payload):
    try:
        __le_sys.stdout.write(__LE_PREFIX + __le_json.dumps(payload, ensure_ascii=False) + "\\n")
        __le_sys.stdout.flush()
    except Exception:
        pass

def __locus_emit__(ev):
    d = {"type": type(ev).__name__}
    # Surface narrative + metadata fields that downstream visualisers
    # (workbench timeline, paper export) actually use.
    for k in (
        "tool_name", "final_message", "content", "reasoning", "message",
        "agent_name", "node_id", "stop_reason", "iteration",
    ):
        v = getattr(ev, k, None)
        if v is None:
            continue
        d[k] = v if isinstance(v, str) else str(v)
    # Token usage — comes through different shapes per event type. We
    # try a few canonical paths and surface whatever we find.
    for tok_attr in ("usage", "metrics", "state"):
        obj = getattr(ev, tok_attr, None)
        if obj is None:
            continue
        for tok_field, payload_key in (
            ("prompt_tokens", "prompt_tokens"),
            ("completion_tokens", "completion_tokens"),
            ("total_tokens", "total_tokens"),
            ("prompt_tokens_used", "prompt_tokens"),
            ("completion_tokens_used", "completion_tokens"),
            ("total_tokens_used", "total_tokens"),
        ):
            try:
                v = getattr(obj, tok_field, None)
                if isinstance(v, (int, float)) and v:
                    d[payload_key] = v
            except Exception:
                pass
    __le_emit__(d)

# 1. After every Agent is constructed, attach a callback_handler so we
#    see Think / Tool / Terminate events as they fire — regardless of
#    whether the tutorial passed model=… directly or config=AgentConfig(…).
#    Also wrap run_sync / run so we emit a "QueryEvent" at the very top
#    of each call carrying the prompt — that way the UI shows
#    QUERY → ... before the THINK / TOOL chips, instead of after.
try:
    from locus.agent import Agent as __LocusAgent__
    __orig_init__ = __LocusAgent__.__init__
    __orig_run_sync = __LocusAgent__.run_sync

    __SB_FORCE_REFLEXION = __le_os.environ.get("LOCUS_WORKBENCH_REFLEXION") == "1"

    def __patched__(self, *a, **kw):
        __orig_init__(self, *a, **kw)
        try:
            cfg = getattr(self, "config", None)
            if cfg is not None and getattr(cfg, "callback_handler", None) is None:
                cfg.callback_handler = __locus_emit__
            # When the workbench user asks for chain-of-thought we flip
            # reflexion on. The agent then emits ReflectEvent each step
            # carrying the model's self-assessment + guidance — the
            # closest provider-agnostic CoT we can offer.
            if cfg is not None and __SB_FORCE_REFLEXION:
                if not getattr(cfg, "reflexion", None):
                    cfg.reflexion = True
        except Exception:
            pass
    __LocusAgent__.__init__ = __patched__

    def __patched_run_sync__(self, prompt, *a, **kw):
        try:
            __le_emit__({"type": "QueryEvent", "prompt": str(prompt)})
        except Exception:
            pass
        return __orig_run_sync(self, prompt, *a, **kw)
    __LocusAgent__.run_sync = __patched_run_sync__
except Exception:
    pass

# Override locus.core.interrupt so it emits an InterruptEvent SSE line
# and blocks on stdin for the user's response. The runner's
# /api/tutorials/runs/{run_id}/respond endpoint writes a JSON line to
# the subprocess's stdin on the user's behalf.
try:
    import locus.core as __sb_lcore
    def __locus_interrupt__(payload, **metadata):
        try:
            payload_str = payload if isinstance(payload, (str, int, float, bool, list, dict, type(None))) else str(payload)
        except Exception:
            payload_str = str(payload)
        __le_emit__({"type": "InterruptEvent", "payload": payload_str, "metadata": metadata})
        try:
            line = __le_sys.stdin.readline()
        except Exception:
            return None
        if not line:
            return None
        s = line.strip()
        try:
            return __le_json.loads(s)
        except Exception:
            return s
    try:
        __sb_lcore.interrupt = __locus_interrupt__
    except Exception:
        pass
    # Also rebind on locus.multiagent.graph if it imported the original
    # symbol at module load time.
    try:
        import locus.multiagent.graph as __sb_lgraph
        if hasattr(__sb_lgraph, "interrupt"):
            __sb_lgraph.interrupt = __locus_interrupt__
    except Exception:
        pass
except Exception:
    pass

# Note: a previous version of this bootstrap also patched each model's
# .complete() to internally call .stream() so the workbench could show
# tokens land live inside the THINK chip. That patch reconstructs the
# ModelResponse from chunks (Message.assistant(content=...)) and was
# subtly losing fields like message-id metadata which broke
# conversation memory in checkpointed tutorials. We rely on the agent's
# ThinkEvent body for the chain-of-thought instead — the reasoning
# field already carries the model's response and is rendered live as
# soon as the event fires.

# --- end bootstrap; user source follows ---
"""

    # Write the user's source to a tmp file. Keep it inside examples/ so
    # tutorials' relative imports (`from config import get_model`) resolve.
    tmp_dir = Path(tempfile.mkdtemp(prefix="locus-wb-"))
    tmp_file = tmp_dir / "tutorial_workbench.py"
    rendered = bootstrap.replace("__SB_PROVIDER_VALUE__", _describe_provider(req.provider))
    # `from __future__` imports MUST be the first executable statement in
    # the file. If the tutorial has any, split them out and place them
    # at the very top, with the bootstrap after.
    user_preamble, user_rest = _split_future_imports(req.source)
    tmp_file.write_text(user_preamble + rendered + user_rest)

    run_id = _uuid.uuid4().hex
    env = {
        **os.environ,
        **_provider_env(req.provider),
        "PYTHONPATH": f"{src_dir}{os.pathsep}{examples_dir}",
        "PYTHONUNBUFFERED": "1",
        "LOCUS_WORKBENCH_REFLEXION": "1" if req.reflexion else "0",
        # Forwarded into the subprocess so its bootstrap can stamp every
        # __LE__:{...} line with the parent's run_id. The parent then
        # republishes those lines on the EventBus under the same run_id
        # so the unified /api/events/{run_id} SSE consumer sees the same
        # structured events as the legacy /api/tutorials/run consumer.
        "LOCUS_WORKBENCH_RUN_ID": run_id,
    }

    async def gen() -> _AI[str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "python",
                str(tmp_file),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=str(examples_dir),
            )
        except Exception as exc:
            yield _sse({"type": "error", "text": f"spawn failed: {exc}"})
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return

        _RUNS[run_id] = proc
        # First SSE message gives the client the run id so it can POST
        # responses back to /api/tutorials/runs/{run_id}/respond when an
        # InterruptEvent fires.
        yield _sse({"type": "runStarted", "run_id": run_id})

        async def pump(reader: asyncio.StreamReader | None, kind: str) -> None:
            if reader is None:
                return
            while True:
                line = await reader.readline()
                if not line:
                    return
                queue.put_nowait((kind, line.decode(errors="replace").rstrip("\n")))

        queue: asyncio.Queue[tuple[str, str] | None] = asyncio.Queue()

        async def gather() -> None:
            await asyncio.gather(pump(proc.stdout, "stdout"), pump(proc.stderr, "stderr"))
            await queue.put(None)

        gather_task = asyncio.create_task(gather())

        try:
            timeout = max(5, req.timeout_seconds)
            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                try:
                    item = await asyncio.wait_for(
                        queue.get(),
                        timeout=max(0.1, deadline - asyncio.get_event_loop().time()),
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    yield _sse({"type": "error", "text": f"killed after {timeout}s"})
                    break
                if item is None:
                    break
                kind, text = item
                # Bridge structured agent events (__LE__:{json}) onto the
                # observability EventBus so the unified SSE endpoint
                # /api/events/{run_id} sees the same telemetry the legacy
                # /api/tutorials/run consumer sees. Plain stdout/stderr
                # lines also flow as bus events so users can tail
                # everything from one channel.
                await _bridge_subprocess_line_to_bus(run_id, kind, text)
                yield _sse({"type": kind, "text": text})
            rc = await proc.wait()
            yield _sse({"type": "exit", "code": rc})
            # Final marker on the bus + close the run channel so SSE
            # consumers see a clean termination instead of timing out.
            from locus.observability import StreamEvent, get_event_bus  # noqa: PLC0415

            bus = get_event_bus()
            await bus.publish(
                StreamEvent(
                    run_id=run_id,
                    event_type="tutorial.exited",
                    data={"code": rc},
                )
            )
            await bus.close_stream(run_id)
        finally:
            gather_task.cancel()
            _RUNS.pop(run_id, None)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class RespondRequest(BaseModel):
    response: Any


@app.post("/api/tutorials/runs/{run_id}/respond")
async def respond_to_interrupt(run_id: str, req: RespondRequest) -> dict[str, Any]:
    """Pipe a JSON-encoded response into the running subprocess's stdin.

    The bootstrap monkey-patches ``locus.core.interrupt`` to print an
    InterruptEvent then read one line from stdin. The frontend POSTs
    the user's answer here when they fill in the modal.
    """
    proc = _RUNS.get(run_id)
    if proc is None:
        raise HTTPException(404, f"unknown or finished run: {run_id}")
    if proc.stdin is None or proc.stdin.is_closing():
        raise HTTPException(409, "subprocess stdin is closed")
    try:
        proc.stdin.write((json.dumps(req.response) + "\n").encode())
        await proc.stdin.drain()
    except Exception as exc:
        raise HTTPException(500, f"write failed: {exc}") from exc
    return {"ok": True, "run_id": run_id}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "patterns": [p["id"] for p in PATTERNS],
        "streamable": sorted(STREAMABLE),
        "tutorials": len(_list_tutorials()),
    }
