# Anthropic

Direct calls to `api.anthropic.com` via `AnthropicModel`.

```python
agent = Agent(model="anthropic:claude-sonnet", ...)
```

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Capabilities

```text
anthropic:
│
├── Claude family       — opus · sonnet · haiku
├── streaming           — real SSE, token-level
├── tool calling        — Anthropic tool-use protocol
├── structured output   — tool-as-schema pattern
│
├── prompt caching      — long system + tool blocks marked cacheable;
│                         subsequent turns pay 1/10th input cost
│
└── extended thinking   — passes thinking blocks through as ThinkEvent
```

## Prompt caching

locus marks long system prompts and tool blocks as cacheable
automatically. Subsequent turns within the cache window pay 1/10th
the input cost.

You don't have to opt in — locus reads the request shape and applies
`cache_control` to anything beyond a small threshold. To force or
suppress it, set `prompt_cache=True|False` on the model config.

## Extended thinking

When the model returns thinking blocks (Claude 4 models with
`thinking_enabled`), locus emits a `ThinkEvent` per block in the
event stream. Pipe it straight to your UI:

```python
async for event in agent.run("..."):
    match event:
        case ThinkEvent(reasoning=r) if r:
            print(f"💭 {r}")
```

## Claude on OCI

For Claude without a separate Anthropic API key, use the OCI
transport instead — same `Agent`, different prefix:

```python
agent = Agent(model="oci:anthropic.claude-sonnet", ...)
```

This routes through `OCIOpenAIModel` and inherits OCI auth, so no
`ANTHROPIC_API_KEY` is needed.

## Source

[`AnthropicModel` in `models/native/anthropic.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/native/anthropic.py).

## See also

- [Models overview](../models.md) — the full provider tree.
- [OCI Generative AI](oci.md) — Claude via OCI.
