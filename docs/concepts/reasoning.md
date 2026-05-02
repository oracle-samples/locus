# Reasoning

A model that loops without thinking is a model that pays you to be
wrong faster. locus ships three reasoning add-ons that are each a
single argument on `Agent(...)`.

```python
agent = Agent(
    model="oci:openai.gpt-5",
    tools=[search, summarise, validate_claim],
    reflexion=True,    # self-evaluate per turn
    grounding=True,    # LLM-as-judge claim verification
    causal=True,       # cause-effect chain analysis
)
```

## Reflexion

After each tool result, the agent is asked: *"given this, was your
last step right?"* If the answer is "no", the next turn rewrites the
plan instead of stacking another tool call on top of a wrong premise.

Source: [Shinn et al., 2023](https://arxiv.org/abs/2303.11366) plus a
locus-native execution loop. Implementation in
`src/locus/reasoning/reflexion.py`. Streamed as `ReflectEvent`.

## Grounding

Before the agent finalises an answer, every factual claim is checked
against the conversation's tool results. A second model — the judge —
reads each claim and the supporting tool output and emits "supported /
unsupported / partially supported". Unsupported claims are removed or
sent back for re-research.

Source: `src/locus/reasoning/grounding.py`.

## Causal

The agent maintains a running cause-effect chain — *"did X because Y;
Y because Z"* — and checks new conclusions against it. Surfaces
contradictions that the linear chat history hides.

Source: `src/locus/reasoning/causal.py`.

## When to use

- **Reflexion** — agents that loop, especially research and
  long-running planning.
- **Grounding** — anything customer-facing where hallucinated facts
  are bad. Drug names. Account numbers. Prices.
- **Causal** — multi-step explanations where a wrong root assumption
  silently poisons everything downstream.

You can combine all three. The cost is more model calls; the win is
fewer wrong answers.

## Tutorial

[`tutorial_14_reasoning_patterns.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_14_reasoning_patterns.py).
