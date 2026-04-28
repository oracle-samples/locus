# Agent Server

`AgentServer` is the reference HTTP wrapper — drop in an `Agent`,
expose `/invoke` and `/stream` over FastAPI, ship.

```python
from locus.server import AgentServer

server = AgentServer(
    agent=my_agent,
    title="Booking concierge",
    cors_origins=["https://app.example.com"],
)

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=8080)
```

## Endpoints

| Path | Method | Body | Returns |
|---|---|---|---|
| `/invoke` | POST | `{"prompt": "...", "thread_id": "..."}` | full `RunResult` JSON |
| `/stream` | POST | same | `text/event-stream` SSE of typed events |
| `/health` | GET | — | liveness probe |
| `/threads/{tid}` | GET | — | conversation history (if checkpointer set) |
| `/threads/{tid}` | DELETE | — | drop a thread |

## Thread persistence

If the underlying `Agent` has a checkpointer, the server honours
`X-Session-ID` (or `thread_id` in the body) for cross-request
continuity. Same browser tab → same thread → same context.

## Streaming

```js
const ev = new EventSource("/stream", { method: "POST", body: ... });
ev.addEventListener("tool_start",   e => …);
ev.addEventListener("tool_complete", e => …);
ev.addEventListener("model_chunk",   e => …);   // token-level
ev.addEventListener("terminate",     e => …);
```

Every typed event is its own SSE event-name; the `data:` payload is
the JSON-serialised event.

## Deployment

The server is plain FastAPI — deploy it however you deploy FastAPI.
On OCI:

- **OCI Functions** — `AgentServer` runs in a function with
  `mangum`-style adapter.
- **OKE / Container Instances** — `docker build` and ship.
- **Compute** — `uvicorn locus.server:run --port 8080`.

Auth, rate-limiting, and logging are FastAPI middleware concerns —
locus does not own them.

## Tutorial

[`tutorial_28_agent_server.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_28_agent_server.py).

## Source

`src/locus/server/`.
