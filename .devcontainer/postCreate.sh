#!/usr/bin/env bash
# One-shot setup, runs once per codespace creation.
# Installs locus (editable) + the workbench's two npm projects.

set -euo pipefail

cd "$(dirname "$0")/.."

# Install locus with:
# - [dev]      — ruff/mypy/pytest/etc.
# - [llm]      — openai + anthropic + ollama + oci. The workbench backend
#                imports these eagerly to build providers, so any one of
#                them missing crashes runner.py before serving a request.
# Plus fastapi + python-multipart — runner.py uses FastAPI directly, but
# fastapi isn't a transitive dep of locus-sdk's [dev] extra (fastmcp pulls
# starlette, not fastapi).
echo "[postCreate] installing locus + dev/llm deps + workbench backend deps"
pip install --upgrade pip
pip install -e ".[dev,llm]" fastapi python-multipart

# Always fetch from the public npm registry. Some contributors generate
# `package-lock.json` on Oracle's corp network, which rewrites every
# package's `resolved` URL to an internal mirror that codespaces (and
# external users) can't reach. The explicit `--registry` flag plus the
# committed lockfiles using public URLs (this PR) defends against both.
echo "[postCreate] installing workbench/bff deps"
(cd workbench/bff && npm install --no-audit --no-fund --registry=https://registry.npmjs.org/)

echo "[postCreate] installing workbench/web deps"
(cd workbench/web && npm install --no-audit --no-fund --registry=https://registry.npmjs.org/)

echo "[postCreate] done"
