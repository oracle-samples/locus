# Tutorial 19: Guardrails & Security — every part runs a real Agent

Every Part fires the configured GenAI provider. Each section prints
``[model call: X.XXs · prompt→completion tokens]`` so you can see the
network round-trip happen, and the SDK feature being demonstrated
(``GuardrailsHook``, ``ContentFilterHook``, ``HookRegistry``,
``GuardrailConfig``, ``GuardrailAction``) is exercised on top of a real
agent loop wherever it makes sense.

Topics covered:

1. GuardrailsHook for comprehensive security
2. PII detection and redaction
3. Content filtering
4. Tool allowlists and blocklists
5. Custom security policies

Run with:
    python examples/tutorial_19_guardrails_security.py

## Source

```python
--8<-- "examples/tutorial_19_guardrails_security.py"
```
