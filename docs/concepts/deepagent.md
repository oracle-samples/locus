# DeepAgent

`create_deepagent` is a research-shaped `Agent` factory. It bundles
the standard deep-research configuration into one call and stays a
plain `locus.Agent` underneath — every hook, plugin, checkpointer,
and evaluation primitive from the rest of the SDK attaches normally.

## What it is

A deep agent runs a tool loop until one of three exit conditions fires:

```python
termination = (
    ToolCalled(submit_tool) & ConfidenceMet(min_confidence)
) | TokenLimit(max_tokens) | MaxIterations(max_iterations)
```

The conditions are composable, greppable, and unit-testable without a
live model. The loop exits when the work is done — not after a fixed
number of steps.

**Defaults on by default:**

- `reflexion=True` — self-evaluates every turn; rewrites the plan when
  the last step was wrong.
- `grounding=True` — scores every claim against the tool-call evidence
  trail; below-threshold claims get dropped or sent back for re-research.
- `output_schema=` — the model provider's strict structured-output mode
  enforces the Pydantic schema before the result reaches the caller.

## Quickstart

```python
from locus import create_deepagent, tool
from pydantic import BaseModel, Field


class ResearchResult(BaseModel):
    summary: str
    sources: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


@tool
def search_kb(query: str) -> list[str]:
    """Search the knowledge base."""
    return kb.query(query)


@tool
def submit_research(result: ResearchResult) -> str:
    """Submit the completed report. Call when confidence ≥ 0.85."""
    return "submitted"


agent = create_deepagent(
    model="oci:openai.gpt-5",
    tools=[search_kb, submit_research],
    system_prompt="You are a research agent. Submit when confident.",
    output_schema=ResearchResult,
    submit_tool="submit_research",
    min_confidence=0.85,
    max_iterations=20,
)

result = agent.run_sync("Summarise our Q3 pipeline coverage.")
report: ResearchResult = result.structured_output
```

## Capability layers

All are opt-in — add only what the task needs.

### Filesystem scratchspace

```python
agent = create_deepagent(
    ...
    enable_filesystem=True,  # adds write_file, read_file, ls, edit_file, glob, grep
)
```

Tools write to an ephemeral in-memory `StateBackend` by default.
Pass `backend=FilesystemBackend(root=Path("./scratch"))` for real-disk
persistence.

### Todo tracking

```python
from locus.deepagent import TodoState

todo_state = TodoState()
agent = create_deepagent(
    ...
    enable_todos=True,
    todo_state=todo_state,   # inspect after the run
)

result = agent.run_sync("...")
for todo in todo_state.items:
    print(f"[{todo.status}] {todo.content}")
```

The `write_todos` / `read_todos` tools let the agent maintain a
structured task list across reasoning steps. The `todo_state` reference
gives the caller a live view after the run.

### Subagent dispatch

```python
from locus.deepagent import SubAgentDef

symbol_analyst = SubAgentDef(
    name="symbol_analyst",
    description="Deep-dives on a single module's public API.",
    system_prompt="Inspect the given module and return its public symbols.",
    tools=[inspect_module],
    max_iterations=4,
)

agent = create_deepagent(
    ...
    subagents=[symbol_analyst],
)
```

The parent calls the child via a `task()` tool. The child runs as a
stateless one-shot; only its final answer appears in the parent's
context, not the full subagent trajectory.

### Memory files

```python
agent = create_deepagent(
    ...
    memory_files=["~/AGENTS.md", "./project-notes.md"],
)
```

`AGENTS.md`-style Markdown files are prepended to the system prompt.
Missing paths are silently skipped so defaults like
`["~/AGENTS.md", "./AGENTS.md"]` work without pre-checking.

### Conversation summarisation

```python
agent = create_deepagent(
    ...
    summarize_after_messages=40,  # trigger threshold
    summarize_keep_recent=10,     # always preserve last 10 verbatim
)
```

Activates locus's `SummarizingManager` so older turns are condensed
once the conversation exceeds the threshold. Prevents context blowout
on long research runs without losing recent reasoning steps.

## Observability

`create_deepagent` returns a standard `locus.Agent`, so all `deepagent.*`
SSE events emit automatically when a `run_context` is active:

```python
from locus.observability import run_context, get_event_bus

async with run_context() as rid:
    result = agent.run_sync("Research the observability module.")

    async for ev in get_event_bus().subscribe(rid):
        match ev.event_type:
            case "deepagent.subagent.spawned":
                print("↳ subagent:", ev.data["subagent_type"])
            case "deepagent.fs.write":
                print("  📝", ev.data["path"])
            case "deepagent.todo.added":
                print("  ☐", ev.data["content"])
            case "agent.terminate":
                print("  ✓", ev.data["final_message_preview"])
```

| Event | When |
|---|---|
| `deepagent.subagent.spawned` | `task()` dispatches a subagent |
| `deepagent.subagent.completed` | subagent returns its result |
| `deepagent.fs.read` / `deepagent.fs.write` | filesystem tool called |
| `deepagent.todo.added` / `deepagent.todo.completed` | todo state changes |

## KnowledgeProvider — multi-item scans

For research that iterates over a discoverable surface (e.g. every table
in a database schema), implement `KnowledgeProvider`:

```python
from locus.deepagent import KnowledgeProvider, KnowledgeRow, ItemRef

class SchemaProvider(KnowledgeProvider):
    def list_items(self) -> list[ItemRef]:
        return [ItemRef(id=t, label=t) for t in db.list_tables()]

    def describe_item(self, ref: ItemRef) -> str:
        return db.describe_table(ref.id)

    def to_row(self, ref: ItemRef, result: ResearchResult) -> KnowledgeRow:
        return KnowledgeRow(id=ref.id, data=result.model_dump())
```

Feed the provider into your scan loop. Each item gets its own agent
run; results are collected as typed rows.

## See also

- [Tutorial 41](../tutorials/tutorial_41_deepagent.md) — four-part
  walkthrough: basic factory, filesystem + todos, subagents, observability.
- [API reference — DeepAgent](../api/deepagent.md) — full class and
  function signatures.
- [Termination algebra](termination.md) — how `ToolCalled & ConfidenceMet`
  works under the hood.
- [SSE event catalogue](sse-events.md) — `deepagent.*` event payloads.
