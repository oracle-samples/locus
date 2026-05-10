# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 34: A2A Protocol — Spec-Compliant Agent-to-Agent Transport

Locus implements the public A2A protocol from
https://a2aproject.github.io/A2A/. This tutorial drives every spec
endpoint against a real Agent end-to-end:

- Agent Card published at ``/.well-known/agent-card.json`` with
  capabilities, typed AgentSkills, and provider metadata.
- JSON-RPC 2.0 ``message/send`` returning a typed Task you can poll.
- ``tasks/get`` to read the task back.
- ``tasks/cancel`` to demonstrate the TaskNotCancelable error code on a
  task that's already terminal.
- ``message/stream`` to stream lifecycle events (``status-update`` /
  ``artifact-update``) as SSE.
- Backwards-compat ``A2AClient.invoke`` for peers that haven't picked
  up the spec yet.

Topics covered:
1. Building a typed AgentSkill list for the Agent Card.
2. Spinning up an A2AServer with bearer-token auth.
3. Driving the spec methods (send / get / cancel / stream) from
   :class:`A2AClient`.
4. Reading the typed Task / TaskStatus / TaskState lifecycle.

Prerequisites:
- pip install fastapi uvicorn
- Configure model via environment variables (any provider works —
  the wire format is provider-agnostic).

Difficulty: Advanced
"""

from __future__ import annotations

import asyncio
import socket
import threading
import time

from config import get_model

from locus.a2a import (
    A2AClient,
    A2AServer,
    AgentSkill,
    Message,
    TaskState,
    TextPart,
)
from locus.agent import Agent, AgentConfig


def _free_port() -> int:
    """Bind an ephemeral port and release it; small TOCTOU window but
    fine for a tutorial."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


def _start_server(server: A2AServer, port: int) -> threading.Thread:
    """Run uvicorn in a daemon thread so the tutorial can drive the
    client synchronously below it."""
    import uvicorn

    config = uvicorn.Config(
        app=server.app, host="127.0.0.1", port=port, log_level="warning", access_log=False
    )
    uv = uvicorn.Server(config)
    thread = threading.Thread(target=uv.run, daemon=True, name="a2a-server")
    thread.start()
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline and not uv.started:
        time.sleep(0.05)
    if not uv.started:
        msg = "uvicorn did not start within deadline"
        raise RuntimeError(msg)
    return thread


async def main() -> None:
    print("=" * 60)
    print("Tutorial 34: A2A Protocol — spec-compliant transport")
    print("=" * 60)

    # ---------------------------------------------------------------
    # Part 1: Stand up a real agent behind A2A.
    # ---------------------------------------------------------------
    print("
=== Part 1: A2AServer with typed skills ===
")

    model = get_model()
    research = Agent(
        config=AgentConfig(
            system_prompt=("You are a research assistant. Reply in one short sentence."),
            max_iterations=2,
            model=model,
        )
    )

    port = _free_port()
    api_key = "tutorial-secret"  # noqa: S105 — demo only

    server = A2AServer(
        agent=research,
        name="research",
        description="Answers research questions with concise summaries.",
        url=f"http://127.0.0.1:{port}",
        skills=[
            AgentSkill(
                id="research",
                name="Research",
                description="Look up facts and summarise.",
                tags=["search", "summarise"],
                examples=["What is quantum computing?"],
            ),
        ],
        api_key=api_key,
    )
    _start_server(server, port)
    print(f"  A2AServer listening on http://127.0.0.1:{port}")

    base_url = f"http://127.0.0.1:{port}"
    client = A2AClient(url=base_url, api_key=api_key)

    # ---------------------------------------------------------------
    # Part 2: Discover via the well-known Agent Card.
    # ---------------------------------------------------------------
    print("
=== Part 2: Agent Card discovery ===
")
    card = await client.get_agent_card()
    print(f"  name:         {card.name}")
    print(f"  description:  {card.description}")
    print(f"  url:          {card.url}")
    print(
        f"  capabilities: streaming={card.capabilities.streaming} "
        f"push={card.capabilities.pushNotifications}"
    )
    for skill in card.skills:
        print(f"  skill:        {skill.id} — {skill.name} (tags={skill.tags})")

    # ---------------------------------------------------------------
    # Part 3: message/send — synchronous round-trip, typed Task back.
    # ---------------------------------------------------------------
    print("
=== Part 3: message/send → Task ===
")
    task = await client.send_message(
        Message(
            role="user",
            parts=[TextPart(text="What is quantum computing?")],
            messageId="m-1",
        )
    )
    print(f"  task.id:           {task.id}")
    print(f"  task.contextId:    {task.contextId}")
    print(f"  task.status.state: {task.status.state.value}")
    if task.artifacts:
        first_part = task.artifacts[-1].parts[0]
        text = getattr(first_part, "text", "")
        print(f"  reply artifact:    {text[:120]}")

    # ---------------------------------------------------------------
    # Part 4: tasks/get — poll the task by id.
    # ---------------------------------------------------------------
    print("
=== Part 4: tasks/get ===
")
    refetched = await client.get_task(task.id)
    print(
        f"  re-fetched task is in {refetched.status.state.value} state "
        f"(== completed: {refetched.status.state == TaskState.completed})"
    )

    # ---------------------------------------------------------------
    # Part 5: tasks/cancel — terminal task → TaskNotCancelable (-32002).
    # ---------------------------------------------------------------
    print("
=== Part 5: tasks/cancel on a terminal task ===
")
    try:
        await client.cancel_task(task.id)
    except RuntimeError as e:
        print(f"  spec error surfaced: {e}")

    # ---------------------------------------------------------------
    # Part 6: message/stream — SSE lifecycle events.
    # ---------------------------------------------------------------
    print("
=== Part 6: message/stream ===
")
    seen: list[str] = []
    async for event in client.send_message_streaming(
        Message(
            role="user",
            parts=[TextPart(text="Stream a one-sentence answer about LLMs.")],
            messageId="m-2",
        )
    ):
        kind = event.get("kind") or "?"
        seen.append(kind)
        if kind == "task":
            print(f"  initial task envelope: id={event.get('id')}")
        elif kind == "status-update":
            state = event.get("status", {}).get("state")
            print(f"  status-update: state={state}")
        elif kind == "artifact-update":
            artifact = event.get("artifact", {})
            parts = artifact.get("parts", [])
            text = parts[0].get("text", "") if parts else ""
            print(f"  artifact-update: {text[:120]}")
    print(f"  total events: {len(seen)}")

    # ---------------------------------------------------------------
    # Part 7: backwards-compat — flat invoke for legacy peers.
    # ---------------------------------------------------------------
    print("
=== Part 7: legacy /a2a/invoke (backwards-compat) ===
")
    text = await client.invoke("Give me a one-line summary of A2A.")
    print(f"  flat reply: {text[:120]}")

    # ---------------------------------------------------------------
    # Part 8: as_tool — wrap the remote agent as a Locus @tool so a
    # local agent can delegate to it. (Simulated here with a sync call
    # since asyncio.run wraps it for free.)
    # ---------------------------------------------------------------
    print("
=== Part 8: A2AClient.as_tool ===
")
    tool = client.as_tool(name="ask_research", description="ask the research agent")
    print(f"  tool.name = {tool.name}, tool.description = {tool.description}")
    # NB: tool.fn invokes asyncio.run() internally, so it's only safe
    # to call from sync code. Don't call it from inside this async
    # ``main`` — that's why this part just inspects the tool object.

    print("
" + "=" * 60)
    print("Next: Tutorial 35 — advanced graph features")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
