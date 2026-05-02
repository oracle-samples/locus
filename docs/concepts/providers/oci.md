# OCI Generative AI

OCI Generative AI is locus's **day-1 target** and the most capable
provider in the box. It exposes 90+ models — OpenAI commercial
families, Meta Llama, Anthropic Claude, Google Gemini, xAI Grok,
Mistral, and Cohere — through Oracle's hosted inference service.
**When OCI ships a new model id, locus already supports it** — you
just pass the new id.

The headline value over the direct providers:

- **One auth surface.** Same `OCI_PROFILE` mechanism on a laptop, in
  CI, or running on OCI Compute / OKE / Functions.
- **Day-0 model coverage.** New OpenAI / Anthropic / Llama models
  reach OCI on the day they're released.
- **No per-provider API keys.** GPT, Claude, Llama all bill through
  your OCI tenancy.
- **Dedicated AI Cluster (DAC) endpoints** for predictable latency
  and isolation when on-demand isn't enough.

## When to pick OCI

| You want… | This is the right provider |
|---|---|
| GPT, Claude, Llama, Cohere, Gemini, Grok, Mistral all in one place | ✓ |
| Production inference on Oracle infrastructure (OKE / Compute / Functions) | ✓ |
| One auth surface across laptop, CI, OCI workloads | ✓ |
| Provisioned-capacity inference via [DAC](../../how-to/oci-dac.md) | ✓ |
| To avoid managing per-provider API keys | ✓ |
| Bleeding-edge OpenAI features the day they ship | use [OpenAI](openai.md) direct — OCI sometimes lags by hours/days |
| Local development without auth setup | use [Ollama](ollama.md) instead |

## Two transports under one prefix

OCI Generative AI exposes its inference service in two ways. locus
speaks both and **picks the right one automatically from the model
id** — you don't have to know which transport a model uses to call
it.

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
├── SDK transport · OCIModel         OCI Generative AI Python SDK
│   └─ cohere.command-r*  — Cohere R-series only (native API only)
│
└── DAC endpoints     · OCIModel     DedicatedServingMode
    └─ ocid1.generativeaiendpoint....   — provisioned capacity
```

### V1 transport — `/openai/v1` (OpenAI-compatible)

`OCIOpenAIModel` calls
`https://inference.generativeai.<region>.oci.oraclecloud.com/openai/v1/chat/completions`.

This is the **default path for the majority of OCI models**:
OpenAI commercial, Meta Llama, xAI Grok, Mistral, Google Gemini, and
Claude on OCI. The wire format is identical to OpenAI's, so anything
you know about prompting OpenAI carries over: real SSE streaming,
OpenAI-style function calling, structured output, vision input.

```python
agent = Agent(model="oci:openai.gpt-5")           # OpenAI commercial
agent = Agent(model="oci:meta.llama-3.3-70b-instruct")  # Meta Llama
agent = Agent(model="oci:anthropic.claude-sonnet")  # Claude — no Anthropic key needed
```

### SDK transport — OCI native API

`OCIModel` calls the OCI Generative AI Python SDK directly. It's
used **only for Cohere R-series** (`cohere.command-r-*`), which OCI
exposes through the native API rather than the OpenAI-compatible
gateway. Cohere R has its own request shape (separate `message` +
`chat_history` instead of a flat `messages` array).

```python
agent = Agent(model="oci:cohere.command-r-plus-08-2024")  # SDK transport
```

### DAC endpoints — dedicated capacity

When you've provisioned a Dedicated AI Cluster (DAC), OCI gives you
a **generative AI endpoint OCID**. Pass it as the model id and locus
auto-routes through the SDK transport with `DedicatedServingMode`:

```python
agent = Agent(
    model=get_model(
        "oci:ocid1.generativeaiendpoint.oc1.<region>....",
        compartment_id="ocid1.compartment.oc1...",
        profile_name="DEFAULT",
    ),
)
```

[Full DAC how-to →](../../how-to/oci-dac.md) — covers Qwen-on-DAC,
streaming, tool-call quirks per model.

## Transport selection — automatic

You don't pick the transport. locus looks at the model id and
chooses:

| Model id pattern | Transport |
|---|---|
| `ocid1.generativeaiendpoint....` | SDK + `DedicatedServingMode` (DAC) |
| `cohere.command-r-*` | SDK + `OnDemandServingMode` |
| `openai.*` / `meta.*` / `xai.*` / `mistral.*` / `google.*` / `anthropic.*` | V1 (OpenAI-compatible) |

Need to override? Set `LOCUS_OCI_TRANSPORT=v1` or `LOCUS_OCI_TRANSPORT=sdk`.

## One auth surface — laptop, CI, OCI workloads

Same `OCI_PROFILE` env var everywhere. `OCI_AUTH_TYPE` selects the
signer:

| Auth type | Where it works | What you set |
|---|---|---|
| `api_key` | Laptop with `~/.oci/config` profile | `OCI_AUTH_TYPE=api_key`, `OCI_PROFILE=DEFAULT` |
| `session_token` | Federated SSO laptop | `oci session authenticate` first; then `OCI_AUTH_TYPE=session_token` |
| `instance_principal` | OCI Compute · OKE pods | `OCI_AUTH_TYPE=instance_principal` (no key file needed) |
| `resource_principal` | OCI Functions · serverless | `OCI_AUTH_TYPE=resource_principal` (provider-injected) |

```bash
export OCI_PROFILE=DEFAULT
export OCI_AUTH_TYPE=api_key
```

**No code change between environments — only the env var differs.**
That's the value: prototype on your laptop, deploy to OKE, route
through Compute. Same `Agent` instance, same model id, three
different signers.

## Region

OCI Generative AI is offered in `us-chicago-1`, `eu-frankfurt-1`,
`uk-london-1`, `sa-saopaulo-1`, and a growing list. The region baked
into your profile is the default; override with `OCI_REGION`:

```bash
export OCI_REGION=us-chicago-1
```

## Practical wiring — laptop dev → OKE production

```python
# Same code on your laptop and on OKE:
from locus import Agent

agent = Agent(
    model="oci:openai.gpt-5",
    system_prompt="You are a helpful assistant.",
)
```

```bash
# Laptop:
export OCI_PROFILE=DEFAULT
export OCI_AUTH_TYPE=api_key

# OKE pod:
export OCI_AUTH_TYPE=instance_principal
# (no profile / key file — OKE injects the principal at runtime)
```

The agent doesn't care. That's the OCI provider's whole pitch.

## Common gotchas

| Symptom | Likely cause |
|---|---|
| `404 Not Authorized` (yes, 404 not 403) | OCI's standard permission-denied disguise. Your principal lacks `inspect generative-ai-endpoints` policy in the compartment. |
| `model_id not found` | Model id doesn't exist in your tenancy's region. Check `oci generative-ai model list --region <region>`. |
| `compartment_id is required` | DAC endpoints enforce it even when on-demand wouldn't. Pass `compartment_id=` on the model. |
| Streaming yields one big chunk | DAC endpoint rejected `is_stream`. The fall-back path swallows the failure and emits the full response as one chunk; check `OCI_LOG_REQUESTS=1`. |
| Cohere R model fails on V1 | Force the SDK transport: `LOCUS_OCI_TRANSPORT=sdk`. |

## Source

| | |
|---|---|
| `OCIOpenAIModel` (V1) | [`src/locus/models/providers/oci/openai_compat.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/providers/oci/openai_compat.py) |
| `OCIModel` (SDK + DAC) | [`src/locus/models/providers/oci/__init__.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/providers/oci/__init__.py) |
| Per-family request builders | [`src/locus/models/providers/oci/models/`](https://github.com/oracle-samples/locus/tree/main/src/locus/models/providers/oci/models) |
| Routing | [`src/locus/models/registry.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/registry.py) — `_make_oci()` |

## See also

- [Models overview](../models.md) — the full provider tree.
- [OCI GenAI models how-to](../../how-to/oci-models.md) — auth setup, region selection, debugging.
- [OCI Dedicated AI Cluster (DAC)](../../how-to/oci-dac.md) — provisioned-capacity endpoints.
- [OpenAI](openai.md) — direct OpenAI when OCI lags.
- [Anthropic](anthropic.md) — Claude direct when OCI lags.
- [Ollama](ollama.md) — local development before swapping to OCI.
