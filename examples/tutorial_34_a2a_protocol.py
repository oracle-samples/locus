"""
Tutorial 34: A2A Protocol — Agent-to-Agent Communication

This tutorial covers:
- A2AServer: expose agent as HTTP endpoint
- A2AClient: call remote agents
- Agent card discovery
- Cross-framework interop

Prerequisites:
- pip install fastapi uvicorn
- Configure model via environment variables

Difficulty: Advanced
"""

from config import get_model

from locus.a2a import A2AServer
from locus.agent import Agent, AgentConfig


# =============================================================================
# Part 1: Create an A2A Server
# =============================================================================


def example_a2a_server():
    """Expose an agent as an A2A-compatible endpoint."""
    print("=== A2A Protocol ===\n")

    model = get_model()

    agent = Agent(config=AgentConfig(
        system_prompt="You are a research assistant. Answer concisely.",
        max_iterations=3, model=model,
    ))

    server = A2AServer(
        agent=agent,
        name="Research Agent",
        description="Researches topics and provides summaries",
        skills=["research", "analysis"],
    )

    # Test with FastAPI TestClient
    from fastapi.testclient import TestClient

    client = TestClient(server.app)

    # Agent card (discovery)
    r = client.get("/agent-card")
    card = r.json()
    print(f"Agent Card: {card['name']} — {card['description']}")
    print(f"Skills: {card['skills']}")

    # Invoke
    r = client.post("/a2a/invoke", json={
        "messages": [{"role": "user", "content": "What is quantum computing?", "metadata": {}}],
        "metadata": {},
    })
    data = r.json()
    print(f"\nInvoke: {data['messages'][0]['content'][:100]}...")
    print(f"Status: {data['status']}")

    print("\nTo run as a real server:")
    print("  server.run(host='0.0.0.0', port=8001)")
    print("\nA2AClient usage:")
    print('  client = A2AClient(url="http://localhost:8001")')
    print('  response = await client.invoke("What is AI?")')


if __name__ == "__main__":
    example_a2a_server()
