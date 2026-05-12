#!/usr/bin/env bash
# Show a clear "your workbench is here" banner the moment Vite binds.
#
# Why this exists: when a developer clicks the docs `Launch workbench`
# button, GitHub Codespaces opens VS Code Web in their browser. The
# devcontainer's `5173.onAutoForward: openBrowserOnce` triggers a SECOND
# tab with the workbench UI — but popup blockers (Safari, locked-down
# browsers) often silently swallow that tab, leaving the developer
# staring at VS Code with no idea where the playground is. This task
# fires on workspace open, waits for Vite, then prints a Cmd-clickable
# URL in a dedicated terminal panel that VS Code reveals automatically.
#
# The companion `welcome.md` is also opened as an editor tab below so
# the URL is visible in two places: the terminal banner and the
# welcome doc.

set -euo pipefail

# Only meaningful in a Codespace (where CODESPACE_NAME is exported by
# GitHub). On a local devcontainer / Docker run, fall back to localhost.
if [ -n "${CODESPACE_NAME:-}" ]; then
  URL="https://${CODESPACE_NAME}-5173.app.github.dev"
else
  URL="http://localhost:5173"
fi

# Open the welcome doc beside the editor. `code` is in PATH inside VS
# Code Codespaces and is a no-op (but non-fatal) elsewhere.
if command -v code >/dev/null 2>&1; then
  code .devcontainer/welcome.md 2>/dev/null || true
fi

# Poll until Vite binds (postStart launches it in detached sessions —
# allow up to ~3 min for first-time codespace boot through pip + npm).
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

   ⌘-click the URL above to open the workbench in a new tab.
   GitHub may have already auto-opened it; if not, this is it.

   Then: Provider settings → paste an OpenAI or Anthropic key
         → pick a tutorial in the sidebar → Run.
  ────────────────────────────────────────────────────────────


EOF

# Keep the panel alive so the URL stays on screen. Tail the three tier
# logs at low frequency so the developer can see liveness without spam.
exec tail -n 0 -F /tmp/wb-backend.log /tmp/wb-bff.log /tmp/wb-web.log 2>/dev/null
