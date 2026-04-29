"""
Tutorial 28: Agent Server — Deploy Agents as HTTP APIs

This tutorial covers:
- AgentServer: wrap any agent as a FastAPI app
- POST /invoke: synchronous invocation
- POST /stream: SSE streaming
- GET /threads/{tid}: load a persisted thread
- DELETE /threads/{tid}: drop a persisted thread
- GET /health: health check

Threads are scoped to the bearer-principal hash so two API keys sharing
one server can't read each other's conversations.

Prerequisites:
- pip install fastapi uvicorn
- Configure model via environment variables

Difficulty: Intermediate
"""

from config import get_model

from locus.agent import Agent, AgentConfig
from locus.memory.backends.memory import MemoryCheckpointer
from locus.server import AgentServer


# =============================================================================
# Part 1: Create and configure the server
# =============================================================================


def example_server():
    """Create an agent server with health, invoke, and stream endpoints."""
    print("=== Agent Server ===\n")

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

    print("\nTo run as a real server:")
    print("  server.run(host='0.0.0.0', port=8000)")
    print("\nWith api_key= set, every /threads call is principal-scoped:")
    print("  AgentServer(agent=agent, api_key='secret')")
    print("  # Two clients with different bearer tokens see different threads")
    print("  # for the same client-supplied thread_id.")


if __name__ == "__main__":
    example_server()
