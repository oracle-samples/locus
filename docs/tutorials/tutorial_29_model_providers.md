# Tutorial 29: Model Providers — OCI, OpenAI, Anthropic, Ollama

This tutorial covers:

- OCI GenAI — two transports:
  - OCIOpenAIModel — OpenAI-compatible /openai/v1 endpoint, real SSE
      streaming, day-0 model support (OpenAI / Meta / xAI / Mistral /
      Gemini / non-R Cohere).
  - OCIModel — OCI SDK transport, required for Cohere R-series.
- OpenAI: GPT-4o, o1, o3, gpt-5.* direct API
- Anthropic: Claude models
- Ollama: Local LLMs (Llama, Mistral, Gemma)
- Model registry: get_model("provider:model_name") — auto-routes OCI
  ids to the right transport.

Prerequisites:

- API keys for the providers you want to use

Difficulty: Beginner

## Source

```python
--8<-- "examples/tutorial_29_model_providers.py"
```
