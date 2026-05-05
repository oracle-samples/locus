# Tutorial 13: Structured Output — every part runs against a real LLM

This tutorial demonstrates structured output capabilities of the Locus
SDK. Every Part fires a real OCI gpt-5 call and prints
``[model call: X.XXs · prompt→completion tokens]`` so you can see the
network round-trip happen. The structured-output APIs being shown are
all real SDK features:

- ``locus.core.structured.extract_json``
- ``locus.core.structured.parse_structured`` / ``StructuredOutputError``
- ``locus.core.structured.create_schema_prompt`` /
  ``create_output_instructions``
- ``Agent(output_schema=YourPydanticModel)`` (constrained decoding +
  prompted-JSON fallback inside the agent loop)

Run with:
    python examples/tutorial_13_structured_output.py

## Source

```python
--8<-- "examples/tutorial_13_structured_output.py"
```
