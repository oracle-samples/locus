# 👋 locus workbench — welcome

You've just clicked **Launch workbench**. The three workbench tiers
(FastAPI runner + Node BFF + Vite web) are starting in the
`workbench` terminal panel right now.

## How to open the workbench UI

When the `workbench` terminal banner says `🚀 locus workbench is ready`,
**one click gets you to the playground**. Use whichever you prefer:

1. **⌘-click the URL** in the workbench terminal panel — opens the
   workbench in a new browser tab.
2. **Click the `Workbench` row** in the **PORTS** panel (bottom of
   VS Code) → **Preview in Editor** — opens the workbench as a
   Simple Browser tab right inside VS Code.
3. **Cmd-Shift-P** → "Simple Browser: Show" → paste the URL — same
   thing, manually.

We **wanted** the Simple Browser tab to auto-open with no clicks, and
the devcontainer does try (via `portsAttributes.5173.onAutoForward:
"openPreview"` and a `code --open-url` call from
`workbench-attach.sh`), but Codespaces VS Code Web doesn't reliably
honor either mechanism from a shell context. So one manual click is
the documented path.

## Two-click run flow once the workbench is open

1. **Provider settings** → paste an OpenAI or Anthropic API key →
   pick a tutorial in the sidebar → **Run**.

OCI options in **Provider settings** won't work here — they need a
local `~/.oci/config` that doesn't exist in this Codespace. Use
OpenAI or Anthropic for the in-browser path. (For OCI, clone the
repo and run the workbench locally; see
[`docs/workbench.md`](../docs/workbench.md).)

## What's running

Three tiers auto-started by `.devcontainer/workbench-attach.sh` in
the `workbench` terminal panel:

| Tier | Port | Process |
|---|---|---|
| FastAPI runner (Python) | 8100 | `uvicorn workbench.backend.runner:app` |
| BFF (Node Express) | 3101 | `tsx watch workbench/bff/src/server.ts` |
| Vite dev server (web UI) | 5173 | `vite` in `workbench/web/` |

Logs at `/tmp/wb-backend.log`, `/tmp/wb-bff.log`, `/tmp/wb-web.log` —
the `workbench` terminal panel tails all three.

## Restarting tiers (if they die)

```bash
bash .devcontainer/workbench-attach.sh
```

The script is idempotent — any tier already listening on its port
is left alone; only crashed tiers get relaunched.

## Further reading

- [`docs/workbench.md`](../docs/workbench.md) — the public workbench
  page
- [`docs/index.md`](../docs/index.md) — locus SDK landing page
- [`workbench/README.md`](../workbench/README.md) — three-tier
  architecture explained
- [`examples/`](../examples/) — 55 progressive tutorials, all runnable
  from the workbench
