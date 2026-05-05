# Tutorial 15: Playbooks — every part runs against a real LLM

Every Part exercises both a Locus playbook SDK feature *and* the
configured GenAI provider, so you can see the structured-execution
mechanics next to live agent reasoning. Each section prints
``[model call: X.XXs · prompt→completion tokens]`` so you can see the
network round-trip happen.

Run with:
    python examples/tutorial_15_playbooks.py

## Source

```python
--8<-- "examples/tutorial_15_playbooks.py"
```
