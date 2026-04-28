# Structured output

Sometimes you want the model to *fill a shape*, not write prose.
`response_model` makes the agent return a typed object.

```python
from typing import TypedDict
from locus import Agent

class VendorPick(TypedDict):
    vendor_id: str
    score: float
    reason: str

agent = Agent(
    model="oci:openai.gpt-5.5",
    tools=[search_vendors],
    response_model=list[VendorPick],
    system_prompt="Pick three vendors. Return as a list of VendorPick objects.",
)

picks = agent.run_sync("Top three for $2M of cloud spend.").data
# picks: list[VendorPick]
```

`response_model` accepts:

- **TypedDicts** — light-weight typed dicts.
- Plain dataclasses.
- Function signatures (the agent fills the args).

The agent uses the provider's structured-output feature when available
(OpenAI / OCI OpenAI / Gemini), falls back to JSON-schema prompting +
extraction otherwise.

## Robustness

`agent.run_sync(...).data` is validated against the schema. If the
model returned malformed JSON, locus retries up to N times (configurable
via the `ModelRetryHook`). Persistent failure raises
`StructuredOutputError` with the last raw response attached.

## Tutorial

[`tutorial_13_structured_output.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_13_structured_output.py).

## See also

- [Termination](termination.md) — combine `response_model` with
  `ConfidenceMet` to terminate only when the structured output is
  confident enough.
