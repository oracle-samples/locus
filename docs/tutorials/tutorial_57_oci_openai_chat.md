# Tutorial 57: OCI GenAI via `OCIOpenAIModel` — the default transport

Deep dive on Locus's default OCI transport, which speaks the
OpenAI-compatible endpoint at `/openai/v1/chat/completions`. Right for
the vast majority of agents — covers every OCI model family in one
class, no Project OCID dependency, native streaming, native structured
output.

## What this covers

- Basic completion against a single model family
- Streaming responses (SSE → `ModelChunkEvent`)
- Tool calling end-to-end
- Structured output via Pydantic schema
- Swapping model families without changing the model class

## Prerequisites

```bash
export OCI_PROFILE=<your-profile>
export OCI_REGION=us-chicago-1
export OCI_COMPARTMENT=ocid1.compartment.oc1..…
```

## Run

```bash
python examples/tutorial_57_oci_openai_chat.py
```

## See also

- [Tutorial 00 — three OCI transports side-by-side](tutorial_00_oci_transports.md)
- [Tutorial 58 — OCI Responses transport](tutorial_58_oci_responses.md)

## Source

```python
--8<-- "examples/tutorial_57_oci_openai_chat.py"
```
