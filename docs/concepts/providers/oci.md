# OCI Generative AI

OCI is the day-1 target. **90+ models, two transports under one
class hierarchy, day-0 model support.** When OCI ships a new model
id, locus already supports it.

OCI exposes its inference service in two ways. locus speaks both
and picks the right one automatically from the model id. You do not
have to know which transport a model uses to call it.

## Model families

```text
oci:                                 (one prefix · two transports)
│
├── V1 transport · OCIOpenAIModel    /openai/v1/chat/completions
│   ├─ openai.*       — OpenAI commercial chat + reasoning
│   ├─ meta.*         — Meta Llama family
│   ├─ xai.*          — xAI Grok family
│   ├─ mistral.*      — Mistral family
│   ├─ google.*       — Google Gemini family
│   └─ anthropic.*    — Anthropic Claude on OCI (no separate API key)
│
└── SDK transport · OCIModel         OCI Generative AI Python SDK
    └─ cohere.command-r*  — Cohere R-series only (native API only)
```

## V1 transport — `/openai/v1` (OpenAI-compatible)

`OCIOpenAIModel` calls
`https://inference.generativeai.<region>.oci.oraclecloud.com/openai/v1/chat/completions`.

Used for the majority of OCI models: OpenAI commercial, Meta Llama,
xAI Grok, Mistral, Google Gemini, and Anthropic on OCI. Real SSE
streaming, OpenAI-style function calling, structured output. The
wire format is identical to OpenAI's — anything you know about
prompting OpenAI directly carries over.

## SDK transport — OCI native API

`OCIModel` calls the OCI Generative AI Python SDK directly. Used
**only for Cohere R-series** (`cohere.command-r-*`), which OCI
exposes through the native API rather than the OpenAI-compatible
gateway.

## Transport selection — automatic

```python
# Both work; the transport is picked from the model id:
agent = Agent(model="oci:openai.gpt-5.5")           # → V1 (OCIOpenAIModel)
agent = Agent(model="oci:cohere.command-r-plus")    # → SDK (OCIModel)
```

Override with `LOCUS_OCI_TRANSPORT=v1` or `=sdk` if you ever need to
force one path.

## Auth — one surface for every environment

Same `OCI_PROFILE` mechanism on the laptop, in CI, and on OCI
workloads. `OCI_AUTH_TYPE` selects the signer:

| Auth type | Where it works |
|---|---|
| `api_key` | Laptop with `~/.oci/config` profile |
| `session_token` | Federated SSO laptop · `oci session authenticate` |
| `instance_principal` | OCI Compute · OKE pods |
| `resource_principal` | OCI Functions · serverless |

```bash
export OCI_PROFILE=DEFAULT
export OCI_AUTH_TYPE=api_key      # or session_token / instance_principal / resource_principal
```

No code change between environments — only the env var differs.

## Region

OCI Generative AI is offered in `us-chicago-1`, `eu-frankfurt-1`,
`uk-london-1`, `sa-saopaulo-1`, and a growing list. Pass `OCI_REGION`
to override the region baked into your profile:

```bash
export OCI_REGION=us-chicago-1
```

## Source

| | |
|---|---|
| `OCIOpenAIModel` (V1) | [`models/providers/oci/openai_compat.py:163`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/providers/oci/openai_compat.py#L163) |
| `OCIModel` (SDK) | [`models/providers/oci/__init__.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/providers/oci/__init__.py) |
| Submodel providers (Cohere, Generic) | [`models/providers/oci/models/`](https://github.com/oracle-samples/locus/tree/main/src/locus/models/providers/oci/models) |

## See also

- [OCI GenAI models how-to](../../how-to/oci-models.md) — auth setup, region selection, debugging.
- [Models overview](../models.md) — the full provider tree.
