#!/usr/bin/env bash
# Boots the three workbench tiers in the background every time the
# codespace starts. Opens the workbench in VS Code's Simple Browser
# automatically once Vite is ready.

set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p /tmp

# Backend — FastAPI runner on :8100.
nohup python -m uvicorn --app-dir workbench/backend runner:app \
  --host 127.0.0.1 --port 8100 \
  > /tmp/wb-backend.log 2>&1 &
echo "[postStart] backend pid=$! → /tmp/wb-backend.log"

# BFF — Express on :3101.
(
  cd workbench/bff
  nohup npm run dev > /tmp/wb-bff.log 2>&1 &
  echo "[postStart] bff pid=$! → /tmp/wb-bff.log"
)

# Web — Vite dev server on :5173.
(
  cd workbench/web
  nohup npm run dev > /tmp/wb-web.log 2>&1 &
  echo "[postStart] web pid=$! → /tmp/wb-web.log"
)

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
