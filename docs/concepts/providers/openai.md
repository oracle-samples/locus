# OpenAI

Direct calls to `api.openai.com` via `OpenAIModel`.

```python
agent = Agent(model="openai:gpt-5.5", ...)
agent = Agent(model="openai:o3", ...)             # reasoning model
```

```bash
export OPENAI_API_KEY=sk-...
```

## Capabilities

```text
openai:
│
├── chat completions   — gpt-* family (vision, audio, structured output)
├── reasoning models   — o-series (adds reasoning_effort: low | medium | high)
├── streaming          — real SSE, token-level
├── tool calling       — OpenAI tool-call protocol
├── structured output  — response_model / JSON schema
│
└── base_url override  — any OpenAI-compatible gateway
    ├─ Azure OpenAI
    ├─ Portkey
    ├─ LiteLLM proxy
    ├─ vLLM (self-hosted)
    └─ together.ai · fireworks · groq · any /v1-shaped endpoint
```

## Custom base URL — Azure, Portkey, LiteLLM, vLLM

`base_url` overrides the API endpoint. Any OpenAI-compatible gateway
works under the same `OpenAIModel` class:

```python
agent = Agent(
    model="openai:gpt-4o",
    model_config={"base_url": "https://api.portkey.ai/v1"},
)
```

| Gateway | `base_url` |
|---|---|
| Azure OpenAI | `https://<resource>.openai.azure.com/openai/deployments/<deployment-id>` |
| Portkey | `https://api.portkey.ai/v1` |
| LiteLLM Proxy | `https://<your-litellm-host>/v1` |
| vLLM (self-hosted) | `http://localhost:8000/v1` |
| together.ai / fireworks / groq | their published `/v1` URL |

For Azure, `api_key` carries the Azure key. For Portkey and LiteLLM,
their virtual-key system applies.

## Reasoning models

Reasoning models (`o1`, `o3`, `o4-mini`) route through the same
class. locus adds `reasoning_effort` to the request when set:

```python
agent = Agent(
    model="openai:o3",
    model_config={"reasoning_effort": "high"},
)
```

The model's thinking blocks come through as `ThinkEvent`s in the
event stream so you can show "thinking…" in your UI.

## Source

[`OpenAIModel` in `models/native/openai.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/native/openai.py).

## See also

- [Models overview](../models.md) — the full provider tree.
