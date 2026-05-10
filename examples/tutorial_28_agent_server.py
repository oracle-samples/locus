# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 28: Agent Server — Deploy Agents as HTTP APIs

This tutorial covers:
- AgentServer: wrap any agent as a FastAPI app
- POST /invoke: synchronous invocation
- POST /stream: SSE streaming (uses the same SSE primitives as tutorial 21)
- GET /threads/{tid}: load a persisted thread
- DELETE /threads/{tid}: drop a persisted thread
- GET /health: health check

Threads are scoped to the bearer-principal hash so two API keys sharing
one server can't read each other's conversations.

When to use AgentServer vs A2AServer (tutorial 34):
- AgentServer: first-party HTTP API. Persisted threads, principal scoping,
  bearer auth. Use when locus is the system of record and clients are yours.
- A2AServer: cross-framework interop with the A2A message spec. Use when
  another framework (Strands, ADK) needs to call your locus agent or vice
  versa.

Prerequisites:
- pip install fastapi uvicorn
- Configure model via environment variables

Difficulty: Intermediate
"""

import os

from config import get_model

from locus.agent import Agent, AgentConfig
from locus.memory.backends.memory import MemoryCheckpointer
from locus.server import AgentServer


# =============================================================================
# Part 1: Create and configure the server
# =============================================================================


def example_server():
    """Create an agent server with health, invoke, and stream endpoints."""
    print("=== Agent Server ===
")

    model = get_model()

    agent = Agent(
        config=AgentConfig(
            system_prompt="You are a helpful assistant. Answer concisely.",
            max_iterations=5,
            model=model,
            # In-memory checkpointer so /threads/{id} has something to read.
            checkpointer=MemoryCheckpointer(),
        )
    )

    server = AgentServer(
        agent=agent,
        title="My Agent API",
        description="A helpful AI assistant exposed as HTTP API",
    )

    # Test with FastAPI TestClient (no actual server needed)
    from fastapi.testclient import TestClient

    client = TestClient(server.app)

    # Health check
    r = client.get("/health")
    print(f"GET /health: {r.json()}")

    # Invoke with an explicit thread_id so we can read it back.
    r = client.post(
        "/invoke",
        json={"prompt": "What is 2+2?", "thread_id": "demo-thread"},
    )
    data = r.json()
    print(f"POST /invoke: {data['message']} (success={data['success']})")

    # Stream
    r = client.post("/stream", json={"prompt": "Name 3 colors."})
    print(f"POST /stream: status={r.status_code}")

    # GET the persisted thread we just populated.
    r = client.get("/threads/demo-thread")
    if r.status_code == 200:
        thread = r.json()
        print(
            f"GET /threads/demo-thread: iteration={thread['iteration']}, "
            f"messages={len(thread['messages'])}"
        )
    else:
        print(f"GET /threads/demo-thread: status={r.status_code}")

    # 404 on a thread that doesn't exist.
    r = client.get("/threads/never-existed")
    print(f"GET /threads/never-existed: status={r.status_code}")

    # DELETE the thread (idempotent — second delete returns deleted=False).
    r = client.delete("/threads/demo-thread")
    print(f"DELETE /threads/demo-thread: {r.json()}")

    print("
To run as a real server, set LOCUS_TUTORIAL_BOOT=1 and run this")
    print("file directly. Example session:")
    print("  LOCUS_TUTORIAL_BOOT=1 LOCUS_MODEL_PROVIDER=oci \")
    print("      python examples/tutorial_28_agent_server.py")
    print("  curl -s -X POST http://127.0.0.1:8000/invoke \")
    print("       -H 'Content-Type: application/json' \")
    print('       -d \'{"prompt":"What is 2+2?"}\'')
    print("
With api_key= set, every /threads call is principal-scoped:")
    print("  AgentServer(agent=agent, api_key='secret')")
    print("  # Two clients with different bearer tokens see different threads")
    print("  # for the same client-supplied thread_id.")
    return server


def boot_live_server() -> None:
    """Build the agent server and bind a live uvicorn instance.

    Gated behind ``LOCUS_TUTORIAL_BOOT=1`` so the integration runner that
    imports / executes every tutorial doesn't hang here.
    """
    model = get_model()
    agent = Agent(
        config=AgentConfig(
            system_prompt="You are a helpful assistant. Answer concisely.",
            max_iterations=5,
            model=model,
            checkpointer=MemoryCheckpointer(),
        )
    )
    server = AgentServer(
        agent=agent,
        title="My Agent API",
        description="A helpful AI assistant exposed as HTTP API",
    )
    print("Booting AgentServer on http://127.0.0.1:8000 — Ctrl-C to stop.")
    print("Try: curl -X POST http://127.0.0.1:8000/invoke \")
    print("          -H 'Content-Type: application/json' \")
    print('          -d \'{"prompt":"What is 2+2?"}\'')
    server.run(host="127.0.0.1", port=8000)


if __name__ == "__main__":
    if os.getenv("LOCUS_TUTORIAL_BOOT") == "1":
        boot_live_server()
    else:
        example_server()
