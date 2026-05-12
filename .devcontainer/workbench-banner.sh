#!/usr/bin/env bash
# Banner + tier-log tail for the workbench's `postAttachCommand`.
#
# What it does (and what it deliberately doesn't):
#   - Prints the workbench URL once Vite binds, so it's easy to copy/share.
#   - Tails the three tier logs so the user can see liveness without
#     hunting through `/tmp/`.
#
# What handles the actual "open the workbench" UX:
#   - `customizations.codespaces.openFiles` (in devcontainer.json) opens
#     welcome.md as an editor tab automatically.
#   - `portsAttributes."5173".onAutoForward: "openPreview"` opens the
#     workbench in Simple Browser inside VS Code — single-tab UX, no
#     popup blocker. Same recipe streamlit-example uses, documented as
#     GitHub's "Customizable Initial Experience" pattern.
#
# This script therefore stays narrowly focused on observability; it no
# longer calls `code` to open files or URLs — those flows are now
# native devcontainer features.

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
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:5173/ > /dev/null 2>&1; then
    break
  fi
  sleep 3
done

cat <<EOF


  ────────────────────────────────────────────────────────────
   🚀  locus workbench is ready

   ▸  ${URL}

   The workbench is also embedded as a "Simple Browser" tab in
   VS Code (via portsAttributes.openPreview). Look for it next
   to welcome.md.

   Then: Provider settings → paste an OpenAI or Anthropic key
         → pick a tutorial in the sidebar → Run.
  ────────────────────────────────────────────────────────────


EOF

# Keep the panel alive so the URL stays on screen. Tail the three tier
# logs so the user can see liveness without hunting through /tmp/.
exec tail -n 0 -F /tmp/wb-backend.log /tmp/wb-bff.log /tmp/wb-web.log 2>/dev/null
