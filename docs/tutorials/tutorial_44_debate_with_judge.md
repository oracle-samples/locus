# Tutorial 44: Adversarial debate with structured-output judge

Two opposing agents argue a question. After ``N`` rounds a Judge agent
reads the transcript and emits a *structured* verdict (not free text)
that callers can pipe into a ticketing system, a database, or an audit
log.

    Round 0:  PRO argues case
    Round 0:  CON rebuts
    Round 1:  PRO responds
    Round 1:  CON responds
    ...
    Judge reads the full transcript, emits Verdict(winner, confidence,
    reasoning, key_points)

What's differentiated about Locus here:

* The transcript is built by appending each turn's output to a state
  list — using the typed reducer for ``list[Turn]`` so messages from
  parallel branches merge cleanly.
* The Judge uses Locus's ``output_schema`` so the verdict is a
  Pydantic ``Verdict`` instance, not a JSON-blob you have to parse.
* The whole debate is one ``StateGraph.execute`` call. Cancel,
  checkpoint, and GSAR judgment attach for free.

Run::

    python examples/tutorial_44_debate_with_judge.py

Difficulty: Advanced
Prerequisites: tutorial_13_structured_output, tutorial_43 (this series)

## Source

```python
--8<-- "examples/tutorial_44_debate_with_judge.py"
```
