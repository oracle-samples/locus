#!/usr/bin/env bash
# postAttachCommand entry point.
#
# Runs every time a VS Code client attaches to the codespace. Does three
# things, in this order:
#
#   1. **Idempotently** start the three tiers (backend / BFF / Vite).
#      "Idempotently" because postAttach fires on every attach — second
#      attach must NOT double-launch the tiers. Each tier is launched
#      only if its port isn't already listening.
#   2. Wait for Vite to bind on :5173, then actively open VS Code's
#      Simple Browser pointed at the forwarded workbench URL. Uses the
#      correct Command-URI format `vscode://command/simpleBrowser.show?
#      <JSON-encoded args>` which VS Code Web honours.
#   3. Print a banner with the URL and tail the three tier logs so the
#      attached terminal panel stays useful.
#
# Architectural rationale: this runs in postAttachCommand, not
# postStartCommand, because `portsAttributes.onAutoForward: openPreview`
# only fires when a client is attached at the moment the port binds.
# If tiers boot in postStart (before the client attaches), the
# port-forward event is already past by the time the user shows up,
# and openPreview silently no-ops. Streamlit-example uses exactly this
# pattern — server in postAttachCommand — and the auto-open works
# reliably for their users.

set -euo pipefail

cd "$(dirname "$0")/.."

# Codespace → forwarded URL; anything else (local devcontainer / Docker)
# → localhost.
if [ -n "${CODESPACE_NAME:-}" ]; then
  URL="https://${CODESPACE_NAME}-5173.app.github.dev"
else
  URL="http://localhost:5173"
fi

# Helper: boot one tier as a fully detached process (survives this
# script's exit). Same pattern as PR #150's postStart.sh.
boot_tier() {
  local name="$1" port="$2" log="$3"; shift 3
  if ss -tlnp 2>/dev/null | grep -qE ":${port}\b"; then
    echo "[attach] $name already listening on :$port — skipping"
    return
  fi
  : > "$log"
  setsid bash -c "exec \"\$@\" >>\"$log\" 2>&1" _ "$@" < /dev/null &
  echo "[attach] $name pid=$! → $log"
}

# 1. Boot the three tiers, only if not already up.
echo "[attach] checking tier state"
boot_tier backend 8100 /tmp/wb-backend.log \
  python -m uvicorn --app-dir workbench/backend runner:app \
  --host 127.0.0.1 --port 8100
(cd workbench/bff && boot_tier bff 3101 /tmp/wb-bff.log npm run dev)
(cd workbench/web && boot_tier web 5173 /tmp/wb-web.log npm run dev)

# 2. Wait for Vite to bind, then ask VS Code to open Simple Browser.
echo "[attach] waiting for Vite on :5173..."
VITE_READY=0
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:5173/ > /dev/null 2>&1; then
    VITE_READY=1
    break
  fi
  sleep 3
done

# Build the proper Command-URI for `simpleBrowser.show`. VS Code wants
# JSON-encoded args, then URL-encoded as the query string of a
# `vscode://command/<commandId>?<args>` URI. Python is in the base
# image so this is portable.
if [ "$VITE_READY" = "1" ] && command -v code >/dev/null 2>&1; then
  ENCODED_ARGS=$(python3 -c "
import urllib.parse, json, sys
print(urllib.parse.quote(json.dumps([sys.argv[1]])))
" "$URL")
  code --open-url "vscode://command/simpleBrowser.show?${ENCODED_ARGS}" \
    >/dev/null 2>&1 || true
fi

# 3. Banner + log tail.
cat <<EOF


  ────────────────────────────────────────────────────────────
   🚀  locus workbench is ready

   ▸  ${URL}

   The workbench should be open as a "Simple Browser" editor tab
   inside VS Code right now. If your popup blocker ate it,
   ⌘-click the URL above.

   Then: Provider settings → paste an OpenAI or Anthropic key
         → pick a tutorial in the sidebar → Run.
  ────────────────────────────────────────────────────────────


EOF

exec tail -n 0 -F /tmp/wb-backend.log /tmp/wb-bff.log /tmp/wb-web.log 2>/dev/null
