# 👋 locus workbench — welcome

You've just clicked the **Launch workbench** button. While this VS Code
window finishes booting, a **separate browser tab** is opening with the
workbench UI itself.

## Where's the workbench?

Look for a new tab in your browser at:

> `https://<this-codespace>-5173.app.github.dev`

The actual URL is printed in the terminal panel below (look for the
🚀 banner). **⌘-click** that URL to open it.

If your browser blocks the auto-popup, just click the URL from the
terminal. Same destination.

## Two-click flow

1. Open the workbench tab (above).
2. **Provider settings** → paste an OpenAI or Anthropic API key →
   pick a tutorial in the sidebar → **Run**.

OCI options in **Provider settings** won't work here — they need a
local `~/.oci/config` that doesn't exist in this Codespace. Use OpenAI
or Anthropic for the in-browser path. (For OCI, clone the repo and run
the workbench locally; see [`docs/workbench.md`](../docs/workbench.md).)

## What's running

Three tiers are auto-started by `postStart.sh`:

| Tier | Port | Process |
|---|---|---|
| FastAPI runner (Python) | 8100 | `uvicorn workbench.backend.runner:app` |
| BFF (Node Express) | 3101 | `tsx watch workbench/bff/src/server.ts` |
| Vite dev server (web UI) | 5173 | `vite` in `workbench/web/` |

Logs at `/tmp/wb-backend.log`, `/tmp/wb-bff.log`, `/tmp/wb-web.log` —
the banner terminal panel tails all three.

## Restarting tiers (if they die)

```bash
# Manually re-fire the lifecycle scripts:
bash .devcontainer/postStart.sh
```

## Further reading

- [`docs/workbench.md`](../docs/workbench.md) — the public workbench page
- [`docs/index.md`](../docs/index.md) — locus SDK landing page
- [`workbench/README.md`](../workbench/README.md) — three-tier
  architecture explained
- [`examples/`](../examples/) — 55 progressive tutorials, all runnable
  from the workbench
