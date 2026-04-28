"""
Tutorial 28: Agent Server — Deploy Agents as HTTP APIs

This tutorial covers:
- AgentServer: wrap any agent as a FastAPI app
- POST /invoke: synchronous invocation
- POST /stream: SSE streaming
- GET /health: health check

Prerequisites:
- pip install fastapi uvicorn
- Configure model via environment variables

Difficulty: Intermediate
"""

from config import get_model

from locus.agent import Agent, AgentConfig
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

    # Invoke
    r = client.post("/invoke", json={"prompt": "What is 2+2?"})
    data = r.json()
    print(f"POST /invoke: {data['message']} (success={data['success']})")

    # Stream
    r = client.post("/stream", json={"prompt": "Name 3 colors."})
    print(f"POST /stream: status={r.status_code}")

    print("\nTo run as a real server:")
    print("  server.run(host='0.0.0.0', port=8000)")


if __name__ == "__main__":
    example_server()
