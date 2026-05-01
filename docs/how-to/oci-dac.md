# OCI Dedicated AI Cluster (DAC) endpoints

OCI GenAI exposes two serving modes:

- **On-demand** — pay-per-token against a shared model id (`openai.gpt-5.5`,
  `cohere.command-r-plus-08-2024`, …). What `Agent(model="oci:openai.gpt-5.5")`
  has been using by default.
- **Dedicated AI Cluster (DAC)** — provisioned capacity exposed as a
  *generative AI endpoint* OCID
  (`ocid1.generativeaiendpoint.oc1.<region>....`). Inference is routed
  to your cluster, with predictable latency and isolation guarantees.

Locus auto-routes DAC endpoint OCIDs to the SDK transport (`OCIModel`)
because the V1 OpenAI-compatible endpoint doesn't speak
`DedicatedServingMode`. Pass the endpoint OCID exactly the way you'd
pass a model id:

```python
from locus import Agent

agent = Agent(
    model="oci:ocid1.generativeaiendpoint.oc1.<region>....<id>",
    compartment_id="ocid1.compartment.oc1...",   # required for DAC
    profile_name="DEFAULT",                      # any profile in ~/.oci/config
    system_prompt="...",
)
```

Behind the scenes:

```text
get_model("oci:ocid1.generativeaiendpoint....")
  → OCIModel(model_id="ocid1.generativeaiendpoint....")
  → OCIClient.get_serving_mode(...)
       returns DedicatedServingMode(endpoint_id=...)
  → SDK chat() routes to your DAC.
```

## Streaming

`OCIModel.stream()` flips `is_stream=True` on the underlying
`GenericChatRequest` / `CohereChatRequest` and iterates the SSE event
stream the SDK returns. Works for both on-demand and DAC serving
modes, and for both Generic (Llama / OpenAI / xAI / Mistral / Gemini
on OCI) and Cohere R-series request shapes:

```python
async for event in agent.run("Plan Q3"):
    if isinstance(event, ModelChunkEvent) and event.content:
        print(event.content, end="", flush=True)
```

Each SSE event carries a JSON delta. The provider's
`parse_stream_chunk()` extracts text deltas and tool-call deltas; if
the endpoint rejects `is_stream` (some custom DAC deployments do),
the stream falls back to the non-streaming `complete()` path and
yields a single chunk with the full content — so a misconfigured
endpoint never hard-fails the stream.

## Auth

DAC endpoints accept the same auth methods as on-demand:

| Method | When | Kwarg |
|---|---|---|
| API key | local dev with `~/.oci/config` | `profile_name="DEFAULT"` |
| Session token | corporate SSO | `auth_type="security_token", profile_name="..."` |
| Instance principal | OCI VM / OKE / Functions | `auth_type="instance_principal"` |
| Resource principal | OCI Functions, Data Science | `auth_type="resource_principal"` |

`compartment_id` is **required** for DAC — the dedicated endpoint
exists in a specific compartment, and the SDK validates the
`compartment_id` field on every chat request.

## Tutorial-style env-var workflow

`examples/config.py`'s `_pick_oci_transport()` recognises DAC OCIDs
and routes them to the SDK transport automatically:

```bash
export LOCUS_MODEL_PROVIDER=oci
export LOCUS_MODEL_ID="ocid1.generativeaiendpoint.oc1.<region>....<id>"
export LOCUS_OCI_PROFILE=MY_PROFILE
export LOCUS_OCI_COMPARTMENT="ocid1.compartment.oc1..."
python examples/tutorial_01_basic_agent.py
```

`LOCUS_OCI_TRANSPORT=sdk` forces the SDK transport explicitly if you
have a hosted model that uses an OCID-shaped name but isn't a real
DAC endpoint.

## Things that go wrong

| Symptom | Likely cause |
|---|---|
| `404 Not Found` on chat | Endpoint OCID is from a different region than the SDK is talking to. Pass the right `service_endpoint=` (or set `LOCUS_OCI_REGION`) to match the endpoint's region. |
| `compartment_id is required` | Pass `compartment_id=` on `Agent()` — DAC enforces it even when on-demand wouldn't. |
| Stream yields one big chunk instead of deltas | The endpoint rejected `is_stream`. The fall-back path swallows the failure and emits the full response as one chunk; check `OCI_LOG_REQUESTS=1` to see the API error. |
| `You are not authorized to perform this request` | The principal you're authenticating with doesn't have the `inspect generative-ai-endpoints` policy in the endpoint's compartment. |

## Where the wiring lives

- [`src/locus/models/registry.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/registry.py)
  — DAC OCIDs are detected by `lowered.startswith("ocid1.generativeaiendpoint.")`
  and routed to `OCIModel`.
- [`src/locus/models/providers/oci/client.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/providers/oci/client.py)
  — `OCIClient.get_serving_mode()` returns `DedicatedServingMode(endpoint_id=...)`
  for OCID-shaped model ids.
- [`src/locus/models/providers/oci/__init__.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/providers/oci/__init__.py)
  — `OCIModel.stream()` does the real SSE iteration.
- [`tests/unit/test_oci_dac.py`](https://github.com/oracle-samples/locus/blob/main/tests/unit/test_oci_dac.py)
  — 12 unit tests covering routing, serving-mode selection, and stream-chunk parsing.

## Related

- [OCI GenAI](../concepts/providers/oci.md) — overview of the V1 vs SDK transports.
- [OCI models how-to](oci-models.md) — full transport story for on-demand.
