#!/usr/bin/env bash
# Boots the three workbench tiers in the background every time the
# codespace starts. Opens the workbench in VS Code's Simple Browser
# automatically once Vite is ready.

set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p /tmp

# Boot a tier as a fully-detached process so it survives after the
# devcontainer lifecycle hook (this script) exits.
#
# Why we can't just `nohup ... &`:
#   - `nohup` only sets SIG_IGN on SIGHUP. `tsx watch` and `vite dev`
#     install their own signal handlers that overwrite that. When the
#     codespace lifecycle subshell ends, those tiers receive SIGHUP via
#     the controlling terminal and exit cleanly — leaving the backend
#     (Python uvicorn, which doesn't override SIG_IGN on SIGHUP) as the
#     only survivor. Symptom: backend on :8100 alive, BFF on :3101 and
#     Vite on :5173 silently dead a few seconds after this script
#     returns.
#   - `setsid` puts the process in a fresh session with no controlling
#     terminal, so no SIGHUP is ever delivered. `< /dev/null` plus
#     stdout/stderr redirected closes the last fd that could carry a
#     signal.
boot_tier() {
  local name="$1" log="$2"; shift 2
  setsid bash -c "exec \"\$@\" >>\"$log\" 2>&1" _ "$@" < /dev/null &
  echo "[postStart] $name pid=$! → $log"
}

# Backend — FastAPI runner on :8100.
: > /tmp/wb-backend.log
boot_tier backend /tmp/wb-backend.log \
  python -m uvicorn --app-dir workbench/backend runner:app \
  --host 127.0.0.1 --port 8100

# BFF — Express on :3101.
: > /tmp/wb-bff.log
(cd workbench/bff && boot_tier bff /tmp/wb-bff.log npm run dev)

# Web — Vite dev server on :5173.
: > /tmp/wb-web.log
(cd workbench/web && boot_tier web /tmp/wb-web.log npm run dev)

# Wait for Vite to bind, then open workbench in VS Code Simple Browser.
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:5173/ > /dev/null 2>&1; then
    echo "[postStart] workbench UI ready"
    # Open in VS Code Simple Browser panel so the workbench fills the screen.
    code --open-url "vscode://vscode.simpleBrowser.api.open/http://127.0.0.1:5173/" 2>/dev/null || true
    break
  fi
  sleep 1
done

echo "[postStart] logs: tail -f /tmp/wb-backend.log /tmp/wb-bff.log /tmp/wb-web.log"
