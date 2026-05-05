#!/usr/bin/env bash
# Boots the three workbench tiers in the background every time the
# codespace starts. Logs go to /tmp/wb-*.log. The Codespaces "Ports"
# panel will surface the public URL for 5173 once Vite is ready.

set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p /tmp

# Backend — FastAPI runner on :8100. Use the project's installed locus
# package; PYTHONPATH src so any local-only modules resolve.
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

# Wait briefly for Vite to bind so the port-forward UI surfaces a URL.
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf http://127.0.0.1:5173/ > /dev/null; then
    echo "[postStart] workbench UI ready at http://127.0.0.1:5173/"
    break
  fi
  sleep 1
done

echo "[postStart] tail logs:"
echo "  tail -f /tmp/wb-backend.log /tmp/wb-bff.log /tmp/wb-web.log"
