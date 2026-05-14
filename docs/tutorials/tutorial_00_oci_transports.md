# Tutorial 00: OCI Generative AI — the three transports

Locus exposes OCI GenAI through three different model classes. They are
not interchangeable — picking the right one depends on the model family
you're calling and whether you want server-side conversation state.

## Decision rule

Read top-to-bottom. The first match wins.

| Want… | Use |
|---|---|
| A Responses-only model (e.g. `openai.gpt-5.5-pro`), or server-side conversation state | `OCIResponsesModel` |
| A Cohere R-series model (`cohere.command-r*`) | `OCIModel` |
| Everything else | `OCIOpenAIModel` (default) |

The runtime detects `model.server_stateful` automatically — when it's
`True`, Locus sends only the latest-turn slice and threads the
continuation token via `AgentState.provider_state`. The only Locus
primitive that stands down on the Responses path is
`ConversationManager` (window/summarize have nothing to operate on when
the history lives server-side). Everything else — memory, reflexion,
GSAR, grounding, tool hooks, idempotency, checkpointing, streaming,
structured output, termination conditions — works identically on all
three transports.

## Prerequisites

```bash
export OCI_PROFILE=<your-profile>
export OCI_REGION=us-chicago-1
export OCI_COMPARTMENT=ocid1.compartment.oc1..…   # compartment with GenAI access
```

## Run

```bash
python examples/tutorial_00_oci_transports.py            # all three
python examples/tutorial_00_oci_transports.py --transport responses
python examples/tutorial_00_oci_transports.py --transport sdk
python examples/tutorial_00_oci_transports.py --transport v1
```

## See also

- [OCI Responses API concept page](../concepts/oci-responses.md)
- [Hooks](../concepts/hooks.md) — works identically on all transports
- [MCP](../concepts/mcp.md) — host-side side effects via the same hook surface

## Source

```python
--8<-- "examples/tutorial_00_oci_transports.py"
```
