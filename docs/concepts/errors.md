# Errors

Every exception raised from within Locus subclasses a single root
`LocusError`. One handler catches any Locus-originated failure:

```python
from locus.core.errors import LocusError

try:
    await agent.run(prompt, thread_id=thread_id)
except LocusError as exc:
    logger.exception("agent run failed", extra={"kind": exc.kind})
    raise
```

!!! info "Available from 0.2"
    The `LocusError` hierarchy lands in MR !54. In 0.1, errors
    propagate as `ValueError`, `RuntimeError`, `ImportError`, etc.
    with no common superclass. Pin `locus>=0.2` to use the
    hierarchy.

## Hierarchy

```
LocusError
├── ToolError
│   ├── ToolNotFoundError
│   ├── ToolValidationError
│   └── ToolExecutionError
├── ModelError
│   ├── ModelAuthError
│   ├── ModelThrottledError
│   └── ModelResponseError
├── CheckpointError
│   ├── CheckpointNotFoundError
│   └── CheckpointSerializationError
├── RAGError
│   ├── EmbeddingError
│   └── VectorStoreError
├── ValidationError          (public-API boundary input)
└── ConfigError              (invalid/missing configuration)
```

Each subclass carries a stable snake_case `kind` string for
structured logging and metrics — the class name may change, the
`kind` won't. Full reference lands once MR !54 merges.

## `kind` for metrics

```python
except LocusError as exc:
    metrics.counter("agent.errors", tags={"kind": exc.kind}).increment()
    raise
```

## Chained causes

Every constructor accepts a `cause=...` keyword so the original
exception is preserved as `__cause__`:

```python
raise CheckpointSerializationError(
    f"failed to serialize state for {thread_id}",
    cause=underlying_exc,
)
```
