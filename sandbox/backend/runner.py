"""Locus sandbox backend — pattern runner.

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

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Provider config — exactly one of four auth modes.
# ---------------------------------------------------------------------------


class ProviderConfig(BaseModel):
    """User-supplied model credentials. One config per request."""

    provider: Literal["openai", "anthropic", "oci-session", "oci-apikey"]
    model: str = Field(default="", description="provider-specific model id")
    api_key: str | None = None
    profile: str | None = None
    region: str = "us-chicago-1"
    compartment_id: str | None = None


def build_model(cfg: ProviderConfig) -> Any:
    """Construct a Locus model client from the user's provider config."""
    if cfg.provider == "openai":
        if not cfg.api_key:
            raise HTTPException(400, "openai provider requires api_key")
        # Locus OpenAIModel reads OPENAI_API_KEY by default; pass it through.
        os.environ["OPENAI_API_KEY"] = cfg.api_key
        from locus.models import OpenAIModel

        return OpenAIModel(model=cfg.model or "gpt-5")

    if cfg.provider == "anthropic":
        if not cfg.api_key:
            raise HTTPException(400, "anthropic provider requires api_key")
        os.environ["ANTHROPIC_API_KEY"] = cfg.api_key
        from locus.models import AnthropicModel

        return AnthropicModel(model=cfg.model or "claude-sonnet-4-6")

    if cfg.provider in ("oci-session", "oci-apikey"):
        from locus.models import OCIOpenAIModel

        # Auth-type is inferred from the profile entry in ~/.oci/config —
        # we just need profile + compartment + region. The provider name
        # in our payload is informational, used only for the badge in the
        # web UI.
        return OCIOpenAIModel(
            model=cfg.model or "openai.gpt-5",
            profile=cfg.profile or "DEFAULT",
            compartment_id=cfg.compartment_id,
            region=cfg.region,
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
    """Drive a non-Agent runnable (Pipeline / Orchestrator) by .run_async or .run_sync."""
    if hasattr(runnable, "run") and hasattr(runnable.run, "__aiter__"):
        return await _drive_agent(runnable, prompt)
    if hasattr(runnable, "run_async"):
        out = await runnable.run_async(prompt)
    else:
        import asyncio

        out = await asyncio.to_thread(runnable.run_sync, prompt)
    msg = getattr(out, "message", None) or getattr(out, "final_message", None) or str(out)
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
        system_prompt=(
            "Delegate research to researcher, then ask editor to tighten."
        ),
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
    return RunResponse(reply=str(final_state.get("draft", "")) if isinstance(final_state, dict) else str(final_state))


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
    return RunResponse(reply=str(final.get("report", "")) if isinstance(final, dict) else str(final))


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
        reply = (getattr(result, "message", None) or getattr(result, "final_message", None) or "") or str(result)
    return RunResponse(reply=reply)


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


app = FastAPI(title="locus sandbox runner", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/patterns")
def list_patterns() -> list[dict[str, Any]]:
    return PATTERNS


@app.post("/api/run/{pattern_id}")
async def run(pattern_id: str, req: RunRequest) -> RunResponse:
    runner = PATTERN_RUNNERS.get(pattern_id)
    if not runner:
        raise HTTPException(404, f"unknown pattern: {pattern_id}")
    try:
        return await runner(req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "patterns": [p["id"] for p in PATTERNS]}
