#!/usr/bin/env bash
# Banner + active Simple-Browser-open for the workbench's
# `postAttachCommand`. Runs every time a VS Code client attaches.
#
# What it does:
#   1. Polls until Vite binds on :5173.
#   2. Programmatically opens the workbench in VS Code's Simple Browser
#      via `code --open-url "vscode://vscode.simpleBrowser.api.open/<url>"`.
#      This is the deterministic open path — it fires every time the
#      script runs (postAttach, manual re-run, after a tier crash + restart),
#      unlike `portsAttributes.onAutoForward: openPreview` which only
#      fires once on first port-bind and silently no-ops afterwards.
#   3. Prints a clear 🚀 banner with the URL as a manual fallback.
#   4. Tails the three tier logs to keep the terminal panel alive and
#      give the user a liveness signal.
#
# Layered defences for "the user sees the workbench":
#   - `customizations.codespaces.openFiles` opens welcome.md (always).
#   - `portsAttributes.5173.onAutoForward: openPreview` opens Simple
#     Browser on first port-bind (usually, when GitHub's tunnel cooperates).
#   - This script's `code --open-url` call opens Simple Browser
#     deterministically (every attach, every re-run).
#   - The printed URL is a manual ⌘-click fallback for the case
#     where even the active call fails (rare).

set -euo pipefail

# Codespace → forwarded URL; anything else (local devcontainer / Docker)
# → localhost.
if [ -n "${CODESPACE_NAME:-}" ]; then
  URL="https://${CODESPACE_NAME}-5173.app.github.dev"
else
  URL="http://localhost:5173"
fi

# Poll until Vite binds. postStart launches it in a detached session, so
# allow up to ~3 min for first-time codespace boot through pip + npm.
echo
echo "Waiting for Vite to bind on :5173..."
VITE_READY=0
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:5173/ > /dev/null 2>&1; then
    VITE_READY=1
    break
  fi
  sleep 3
done

# Once Vite is up, actively open the workbench in VS Code's Simple
# Browser editor pane. This is the streamlit-pattern UX (single tab,
# inside VS Code) but triggered programmatically so it works every
# time — not just on the one-shot `openPreview` port-bind moment.
# `code --open-url` is a no-op (but non-fatal) outside VS Code; local
# Docker / non-VS-Code envs just see the printed URL.
if [ "$VITE_READY" = "1" ] && command -v code >/dev/null 2>&1; then
  code --open-url "vscode://vscode.simpleBrowser.api.open/${URL}" >/dev/null 2>&1 || true
fi

cat <<EOF


  ────────────────────────────────────────────────────────────
   🚀  locus workbench is ready

   ▸  ${URL}

   The workbench is also opened as a "Simple Browser" editor tab
   inside VS Code automatically. Look for it next to welcome.md.

   Then: Provider settings → paste an OpenAI or Anthropic key
         → pick a tutorial in the sidebar → Run.
  ────────────────────────────────────────────────────────────


EOF

# Keep the panel alive so the URL stays on screen. Tail the three tier
# logs so the user can see liveness without hunting through /tmp/.
exec tail -n 0 -F /tmp/wb-backend.log /tmp/wb-bff.log /tmp/wb-web.log 2>/dev/null
