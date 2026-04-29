# Ollama

Local model runtime. `OllamaModel` calls a local Ollama server.

```python
agent = Agent(model="ollama:llama3.2", ...)
```

```bash
export OLLAMA_HOST=http://localhost:11434   # default
```

No API key — Ollama is local-first.

## Capabilities

```text
ollama:
│
├── any pulled local model     — run `ollama list` to see what is installed
├── streaming                  — token-level via the local SSE stream
├── tool calling               — works for any model that supports it
│                                (llama3.1+, qwen2.5, mistral, deepseek-r1)
└── auth                       — none · OLLAMA_HOST=http://localhost:11434 (default)
```

Whatever you `ollama pull` is available immediately. No locus change
needed.

## When to use Ollama

- **Offline development** — laptops, planes, isolated networks.
- **Deterministic tests** — no network egress; same model, same
  prompt, same seed → same output.
- **Cost-control sandboxing** — iterate on agent design with a
  free local model before swapping to a paid API.
- **Privacy-sensitive prototyping** — data never leaves the machine.

## Tool calling

Tool calling support is per-model in Ollama. As of writing:

| Model family | Tool calling |
|---|---|
| llama3.1+, llama3.2, llama3.3 | ✅ |
| llama4 | ✅ |
| qwen2.5, qwen2.5-coder | ✅ |
| mistral, mixtral | ✅ |
| deepseek-r1 | ✅ (with reasoning) |
| phi3 | ❌ (no native tool calling) |

If a model doesn't support native tool calling, the agent will
still run but the model can't invoke tools — the loop terminates
on the first turn.

## Custom Ollama server

Override the host for a remote Ollama (e.g., a shared GPU box):

```bash
export OLLAMA_HOST=http://gpu-box.internal:11434
```

The same `OllamaModel` class works against any HTTP-reachable Ollama
endpoint.

## Source

[`OllamaModel` in `models/native/ollama.py`](https://github.com/oracle-samples/locus/blob/main/src/locus/models/native/ollama.py).

## See also

- [Models overview](../models.md) — the full provider tree.
