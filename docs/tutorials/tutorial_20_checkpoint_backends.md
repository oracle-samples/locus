# Tutorial 20: Checkpoint Backends

This tutorial demonstrates different checkpoint storage backends
for persisting agent state and conversation history.

Topics covered:

1. Memory checkpointer (development)
2. SQLite backend (local persistence)
3. File checkpointer (simple storage)
4. Backend interface and operations
5. Backend selection patterns

Note: Redis, PostgreSQL, and cloud backends require additional setup.

Run with:
    python examples/tutorial_20_checkpoint_backends.py

## Source

```python
--8<-- "examples/tutorial_20_checkpoint_backends.py"
```
