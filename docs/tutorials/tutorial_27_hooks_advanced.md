# Tutorial 27: Advanced Hooks — Write-Protected Events, Cancel, Retry

This tutorial covers:

- Write-protected event objects (read-only fields raise AttributeError)
- Cancelling tool calls via event.cancel
- Retrying model calls via event.retry
- Reverse ordering of "after" hooks

Prerequisites:

- Configure model via environment variables

Difficulty: Advanced

## Source

```python
--8<-- "examples/tutorial_27_hooks_advanced.py"
```
