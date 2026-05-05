# Tutorial 14: Reasoning Patterns — every part drives a real LLM call

Every Part hits the configured GenAI provider and exercises a different
SDK capability:

- `@tool` + `Agent(tools=...)` (tool use)
- `Agent(reflexion=True)` (Reflexion loop)
- `Agent(output_schema=YourPydanticModel)` (structured output)
- `Reflector` / `evaluate_progress` (reflexion analytics)
- `GroundingEvaluator.evaluate(...)` (claim grounding)
- `CausalChain` / `build_causal_chain` (causal reasoning)

Every section prints
``[model call: X.XXs · prompt→completion tokens]`` so you can see the
network round-trip happen.

Run with:
    python examples/tutorial_14_reasoning_patterns.py

## Source

```python
--8<-- "examples/tutorial_14_reasoning_patterns.py"
```
