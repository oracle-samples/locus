# Model providers

A model is a string. Pick the provider's prefix; locus picks the
client.

```python
agent = Agent(model="oci:openai.gpt-5.5", ...)
agent = Agent(model="oci:cohere.command-r-plus-08-2024", ...)
agent = Agent(model="oci:meta.llama-3.3-70b-instruct", ...)
agent = Agent(model="openai:gpt-4o", ...)
agent = Agent(model="anthropic:claude-sonnet-4-5", ...)
agent = Agent(model="ollama:llama3.2", ...)
```

The same `Agent` works against any provider — only the model id and
the credentials change. No adapter shim, no LangChain detour.

---

## OCI Generative AI — first class

OCI is the day-1 target. 90+ models, **two transports under one
class hierarchy**, day-0 model support — when OCI ships a new model
id, locus already supports it.

OCI exposes its inference service in two ways. locus speaks both,
and picks the right one automatically from the model id. You do not
have to know which transport a model uses to call it.

### V1 transport — `/openai/v1` (OpenAI-compatible)

`OCIOpenAIModel` calls the OpenAI-compatible endpoint at
`https://inference.generativeai.<region>.oci.oraclecloud.com/openai/v1/chat/completions`.

Use this for the majority of OCI models — OpenAI commercial,
Meta Llama, xAI Grok, Mistral, Google Gemini, Anthropic on OCI.

| Family | Example model ids |
|---|---|
| OpenAI | `oci:openai.gpt-5.5`, `oci:openai.o3`, `oci:openai.gpt-4o` |
| Meta Llama | `oci:meta.llama-3.3-70b-instruct`, `oci:meta.llama-4-scout-17b-16e-instruct` |
| xAI Grok | `oci:xai.grok-4-fast-reasoning`, `oci:xai.grok-3-mini` |
| Mistral | `oci:mistral.large-2407` |
| Google Gemini | `oci:google.gemini-2.5-pro`, `oci:google.gemini-2.5-flash` |
| Anthropic on OCI | `oci:anthropic.claude-sonnet-4-5` |

Real SSE streaming, tool/function calling in OpenAI's tool-call
format, structured output. The wire format is identical to OpenAI's,
so anything you know about prompting OpenAI directly transfers.

### Regular transport — OCI SDK

`OCIModel` calls the native OCI Generative AI SDK
(`oci.generative_ai_inference`). Use it for Cohere R-series and any
model OCI exposes only through the native API.

| Family | Example model ids |
|---|---|
| Cohere R-series | `oci:cohere.command-r-plus-08-2024`, `oci:cohere.command-a-03-2025` |
| Cohere embeddings | `oci:cohere.embed-multilingual-v3.0` |
| Cohere rerank | `oci:cohere.rerank-v3.5` |

The SDK transport handles Cohere's chat shape (`chat_history`,
`documents`, `connectors`) cleanly — locus translates the
locus message protocol into Cohere's expected payload. Streaming and
tool calls work the same as on V1; the difference is invisible to
the agent.

### Picking the transport

The default is automatic — locus reads the model family prefix and
routes accordingly. To force a transport for a specific model id,
set the env var:

```bash
LOCUS_OCI_TRANSPORT=v1   # force /openai/v1
LOCUS_OCI_TRANSPORT=sdk  # force OCI SDK
```

Useful when a model is briefly available on both endpoints during a
rollout, or when one transport is degraded.

### Auth

One auth surface covers laptops, CI, and OCI workload identity. No
provider-specific key management.

| Auth type | Where it works |
|---|---|
| **api_key** | Laptop with `~/.oci/config` profile |
| **session_token** | `oci session authenticate`, federated SSO |
| **instance_principal** | OCI compute (no key required) |
| **resource_principal** | OCI Functions, OKE workloads |

Set `OCI_PROFILE` and `OCI_AUTH_TYPE` and the rest is automatic.
Both transports share this signer — switching from V1 to SDK does
not require re-authenticating. See the
[OCI models how-to](../how-to/oci-models.md) for end-to-end
examples per auth type.

### Region

`OCI_REGION` selects the inference endpoint. The home region in your
profile is independent — locus reads `OCI_REGION` first, then the
profile, then defaults to `us-chicago-1` (where most GenAI models
live).

```bash
export OCI_REGION=us-chicago-1     # GenAI inference
export OCI_PROFILE=DEFAULT   # any profile in ~/.oci/config
export OCI_AUTH_TYPE=api_key       # or session_token / instance_principal / resource_principal
```

---

## OpenAI

`OpenAIModel` calls `api.openai.com` directly.

```python
agent = Agent(model="openai:gpt-4o", ...)
agent = Agent(model="openai:o3", ...)
agent = Agent(model="openai:gpt-5", ...)
```

```bash
export OPENAI_API_KEY=sk-...
```

Real SSE streaming, function calling, structured output, vision.
Reasoning models (`o1`, `o3`) route through the same class — locus
adds the `reasoning_effort` parameter when present.

### Custom base URL — Azure / proxies / Portkey

`base_url` can be overridden to point at any OpenAI-compatible
gateway (Azure OpenAI, Portkey, LiteLLM proxy, vLLM):

```python
agent = Agent(
    model="openai:gpt-4o",
    model_config={"base_url": "https://api.portkey.ai/v1"},
)
```

The same class handles Azure OpenAI when `base_url` points at the
deployment endpoint and `api_key` carries the Azure key.

---

## Anthropic

`AnthropicModel` calls `api.anthropic.com` directly.

```python
agent = Agent(model="anthropic:claude-sonnet-4-5", ...)
agent = Agent(model="anthropic:claude-opus-4-7", ...)
agent = Agent(model="anthropic:claude-haiku-4-5", ...)
```

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Real SSE streaming, tool calling (Anthropic's tool-use protocol),
structured output via tool-as-schema, and **prompt caching** —
locus marks long system prompts and tool blocks as cacheable
automatically, so subsequent turns pay 1/10th the input cost.

For Claude on OCI (no API key needed, OCI auth instead) use the
OCI transport: `oci:anthropic.claude-sonnet-4-5`.

---

## Ollama

`OllamaModel` calls a local Ollama server.

```python
agent = Agent(model="ollama:llama3.2", ...)
```

```bash
export OLLAMA_HOST=http://localhost:11434  # default
```

Useful for offline development and tests where you do not want any
network egress. Tool calling and streaming both work as long as the
underlying model supports them.

---

## Custom providers

Implement the `BaseModel` protocol — three methods (`complete`,
`stream`, `count_tokens`) — and you are a first-class provider. No
adapter layer, no inheritance from `OpenAIModel`. Register the
class with the registry and your prefix becomes a valid model id.

```python
from locus.models import register_provider, BaseModel

class MyModel(BaseModel):
    async def complete(self, ...): ...
    async def stream(self, ...): ...
    def count_tokens(self, ...): ...

register_provider("myco", MyModel)
agent = Agent(model="myco:my-model-id", ...)
```

---

## Tutorial

[`tutorial_29_model_providers.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_29_model_providers.py)
covers all five providers end-to-end with the same agent.

## Source

`src/locus/models/`. Native providers under `native/`, OCI under
`providers/oci/` (V1 in `openai_compat.py`, SDK in
`models/generic.py`).
