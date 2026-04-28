# Tools

Tools are the agent's way of affecting the world. You write a regular
Python function, decorate it, and pass it to `Agent(tools=[...])`. The
`@tool` decorator introspects the signature and docstring to build a
JSON-schema description the model can call.

```python
from locus import tool

@tool
def search(query: str, limit: int = 10) -> list[str]:
    """Search the knowledge base for `query`, up to `limit` results."""
    return backend.search(query, limit)
```

The docstring becomes the tool description. Parameters are taken
from the signature — type hints drive the JSON schema. Defaults are
optional parameters.

## Idempotent tools

Some tools have side effects you never want duplicated — bookings,
transfers, writes. Mark them idempotent:

```python
@tool(idempotent=True)
def book_flight(flight_id: str, customer_id: str) -> dict:
    """Book the flight. Re-issuing the same (flight_id, customer_id)
    within a single run returns the prior result; the body is not
    re-executed."""
    return billing.charge_and_book(flight_id, customer_id)
```

When the model re-issues a tool call with the same
`(name, arguments)` that already ran in this agent run, the ReAct
loop reuses the prior result instead of invoking the function again.
Useful for defending against:

- Models that repeat calls after seeing the result.
- Network glitches where a call looks failed but actually succeeded.
- Users re-prompting "do X" when X has already been done.

This is a Locus-specific primitive; LangChain, LangGraph, and Strands
do not ship it.

## Custom names and descriptions

Override the defaults via keyword arguments:

```python
@tool(name="find_customer", description="Look up a customer by email.")
async def _find(email: str) -> Customer:
    ...
```

Both sync and async bodies are supported. Sync bodies run in a
thread-pool executor so the event loop is not blocked.

## Parallel vs sequential execution

The agent decides based on `config.tool_execution`:

- `"concurrent"` (default) — tool calls run in parallel via
  `asyncio.gather`.
- `"sequential"` — tool calls run one at a time. Pick this when tool
  side effects must be ordered.

## Error handling

If a tool raises, the exception is caught at the executor boundary,
wrapped as a `ToolResult(success=False, error=...)`, and passed to the
model so it can react. The original exception is chained as the cause
on a `ToolExecutionError` (see [Errors](errors.md)).
