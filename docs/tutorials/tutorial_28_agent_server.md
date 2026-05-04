# Tutorial 28: Agent Server — Deploy Agents as HTTP APIs

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

## Source

```python
--8<-- "examples/tutorial_28_agent_server.py"
```
