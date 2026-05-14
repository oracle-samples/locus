# Tutorial 58: OCI GenAI via `OCIResponsesModel` — server-stateful (or not)

Deep dive on the OCI Responses transport. Two modes:

- **`store=False`** — ZDR-safe stateless mode. Agent sends full
  history each turn; server holds nothing. Works in every tenancy.
- **`store=True`** — server-side state. Locus threads
  `previous_response_id` between turns; only the latest-turn slice is
  sent. Requires a non-ZDR tenancy.

The only Locus primitive that bypasses on the Responses path is
`ConversationManager`. Everything else (memory, Reflexion, GSAR,
grounding, hooks, idempotency, checkpointing, output schema, streaming,
termination conditions) works identically — see
[concepts/oci-responses.md](../concepts/oci-responses.md).

## What this covers

- Part 1: stateless multi-turn (`store=False`)
- Part 2: server-side multi-turn with continuation token (`store=True`)
- Part 3: tool round-trip — `function_call` items in input,
  `function_call_output` items posted back
- Part 4: streaming via SSE

## Prerequisites

```bash
export OCI_PROFILE=<your-profile>
export OCI_REGION=us-chicago-1
export OCI_COMPARTMENT=ocid1.compartment.oc1..…
# Optional — set to 1 to also exercise store=True (skip in ZDR tenants):
export OCI_RESPONSES_STORE=0
```

## Run

```bash
python examples/tutorial_58_oci_responses.py
```

## See also

- [Tutorial 00 — three OCI transports side-by-side](tutorial_00_oci_transports.md)
- [Tutorial 57 — OCIOpenAIModel deep dive](tutorial_57_oci_openai_chat.md)
- [Concepts: OCI Responses](../concepts/oci-responses.md)
- [OCI Responses API — Oracle docs](https://docs.oracle.com/iaas/Content/generative-ai/responses-api.htm)
- [OCI OpenAI-compatible endpoints — Oracle docs](https://docs.oracle.com/iaas/Content/generative-ai/openai-compatible-api.htm)

## Source

```python
--8<-- "examples/tutorial_58_oci_responses.py"
```
