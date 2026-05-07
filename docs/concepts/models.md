# Model providers

A model is a string. Pick the provider's prefix; locus picks the
client.

```python
# tools, system_prompt, and other kwargs are the same across all providers
Agent(model="oci:openai.gpt-5")                 # OCI → V1
Agent(model="oci:cohere.command-r-plus")         # OCI → SDK
Agent(model="oci:meta.llama-3.3-70b-instruct")  # OCI → V1
Agent(model="openai:gpt-4o")                    # OpenAI direct
Agent(model="anthropic:claude-sonnet")           # Anthropic direct
Agent(model="ollama:llama3.2")                   # local
```

The same `Agent` works against any provider — only the model id and
the credentials change.

## The provider tree at a glance

```text
locus.models
│
├── oci:                                   ── Oracle Generative AI · day-0
│   │
│   ├── V1 transport · OCIOpenAIModel
│   │   ├─ openai.*          — OpenAI commercial chat + reasoning
│   │   ├─ meta.*            — Meta Llama family
│   │   ├─ xai.*             — xAI Grok family
│   │   ├─ mistral.*         — Mistral family
│   │   ├─ google.*          — Google Gemini family
│   │   └─ anthropic.*       — Anthropic Claude on OCI
│   │
│   ├── SDK transport · OCIModel
│   │   └─ cohere.command-r* — Cohere R-series (native API only)
│   │
│   └── auth                  — api_key · session_token ·
│                               instance_principal · resource_principal
│
├── openai:                                ── OpenAI direct · OpenAIModel
│   ├─ chat completions       — gpt-* family
│   ├─ reasoning models       — o-series (adds reasoning_effort)
│   └─ base_url override      — Azure · Portkey · LiteLLM · vLLM ·
│                               together.ai · fireworks · groq
│
├── anthropic:                             ── Anthropic direct · AnthropicModel
│   ├─ Claude family          — opus · sonnet · haiku
│   ├─ prompt caching         — long blocks marked cacheable;
│   │                           subsequent turns pay 1/10th input cost
│   └─ extended thinking      — thinking blocks → ThinkEvent
│
├── ollama:                                ── Local LLMs · OllamaModel
│   └─ any pulled local model — llama, mistral, qwen, deepseek-r1 …
│
└── custom:                                ── register_provider("myco", MyModel)
    └─ implement BaseModel    — complete · stream · count_tokens
```

Pick the prefix that matches your auth surface.

| Provider | Detail page |
|---|---|
| **OCI Generative AI** | [OCI →](providers/oci.md) |
| **OpenAI** | [OpenAI →](providers/openai.md) |
| **Anthropic** | [Anthropic →](providers/anthropic.md) |
| **Ollama** | [Ollama →](providers/ollama.md) |

## Custom providers

Implement the `BaseModel` Protocol — three methods (`complete`,
`stream`, `count_tokens`) — and you are a first-class provider. No
adapter layer, no inheritance from `OpenAIModel`. Register the class
with the prefix you want; it becomes a valid model id.

```python
from locus.models import register_provider
from locus.models.base import BaseModel

class MyModel(BaseModel):
    async def complete(self, request): ...
    async def stream(self, request): ...
    def count_tokens(self, text): ...

register_provider("myco", lambda model_id, **kw: MyModel(model_id, **kw))

agent = Agent(model="myco:my-model-id")
```

Source: [`register_provider` in `models/registry.py:21`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/registry.py#L21).

## Provider failover & pooling

For high-availability deployments, wrap the model in a pool:

```python
from locus.models.pooled import PooledModel

agent = Agent(
    model=PooledModel(
        primary="oci:openai.gpt-5",
        fallbacks=["openai:gpt-4o", "anthropic:claude-sonnet"],
    ),
    # tools=..., system_prompt=...,
)
```

The pool tries the primary first; on `RateLimitError`, `TimeoutError`,
or persistent 5xx it fails over to the next entry. Source:
[`PooledModel` in `models/pooled.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/pooled.py).

## Tutorial

[`tutorial_29_model_providers.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_29_model_providers.py)
exercises all four providers with the same agent.

## Source

| Area | Path |
|---|---|
| Provider registry | [`models/registry.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/registry.py) |
| `OpenAIModel` | [`models/native/openai.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/native/openai.py) |
| `AnthropicModel` | [`models/native/anthropic.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/native/anthropic.py) |
| `OllamaModel` | [`models/native/ollama.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/native/ollama.py) |
| `OCIOpenAIModel` (V1) | [`models/providers/oci/openai_compat.py:163`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/providers/oci/openai_compat.py#L163) |
| `OCIModel` (SDK) | [`models/providers/oci/__init__.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/providers/oci/__init__.py) |
| `PooledModel` | [`models/pooled.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/pooled.py) |
