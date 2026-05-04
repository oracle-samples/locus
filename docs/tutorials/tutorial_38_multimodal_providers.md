# Tutorial 38: Multi-modal providers — web search, web fetch, image, speech

This tutorial covers:

- Setting `web_search=`, `web_fetch=`, `image_generator=`, `speech_provider=`
  on Agent / AgentConfig — locus auto-registers a matching `@tool` so the
  model can call the capability the same way it calls a hand-written tool.
- The four Protocols under `locus.providers` — bring your own backend
  (Bing, trafilatura, OCI Vision, OCI Speech) by implementing the
  one-method contract.
- Live demo of `HTTPXWebFetcher` against `https://example.com` — the
  only built-in provider that doesn't need an API key.

Prerequisites:

- Configure model via environment variables (see examples/config.py).
- Optional: `OPENAI_API_KEY` to enable the OpenAI-backed providers.

Difficulty: Intermediate

## Source

```python
--8<-- "examples/tutorial_38_multimodal_providers.py"
```
