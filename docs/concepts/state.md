# State

`AgentState` is the single typed record of everything a run knows. It
is an immutable Pydantic model — every mutation returns a new instance
— which means the state round-trips through JSON cleanly, survives
checkpointing, and can be compared across turns.

```python
from locus.core.state import AgentState
from locus.core.messages import Message, Role

state = AgentState(agent_id="my-agent", max_iterations=20)
state = state.with_message(Message(role=Role.USER, content="hi"))
state = state.with_confidence(0.85)
```

## Fields

| Field | Type | Meaning |
|---|---|---|
| `agent_id` | `str` | Identifier carried across turns. |
| `run_id` | `str` (UUID) | Unique to this run. |
| `messages` | `list[Message]` | Full conversation, in order. |
| `tool_executions` | `list[ToolExecution]` | Every tool call with its arguments, result, and duration. |
| `reasoning_steps` | `list[ReasoningStep]` | Think / Execute / Reflect steps. |
| `iteration` | `int` | Current ReAct iteration index. |
| `max_iterations` | `int` | Upper bound before termination. |
| `confidence` | `float` | Reflexion signal 0.0–1.0. |
| `confidence_threshold` | `float` | Early-stop threshold. |
| `terminal_tools` | `frozenset[str]` | Tool names that end the run. |
| `token_budget` | `int \| None` | Optional token cap. |
| `total_tokens_used` | `int` | Running total. |
| `errors` | `list[str]` | Any tool/model errors. |
| `metadata` | `dict[str, Any]` | User-supplied context. |

## Round-trip through JSON

```python
data = state.to_checkpoint()           # → dict[str, Any]
restored = AgentState.from_checkpoint(data)
assert restored == state
```

Every checkpointer uses this pair under the hood. If you build a custom
checkpointer, all you have to do is serialize `to_checkpoint()` and
rehydrate with `from_checkpoint()`.

## Reducers

When running multi-agent graphs, you sometimes want two parallel
branches to each modify the state, then merge the result. Locus ships
with reducers for that:

- `add_messages` — extend message list
- `merge_dict` / `deep_merge_dict`
- `append_list` / `unique_append_list`
- `add_numbers`, `max_value`, `min_value`, `first_value`, `last_value`
- `set_union`

Reducers are opt-in at the graph level — a plain agent run doesn't use
them. See `locus.core.reducers`.
