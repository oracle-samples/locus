#!/usr/bin/env bash
# One-shot setup, runs once per codespace creation.
# Installs locus (editable) + the workbench's two npm projects.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "[postCreate] installing locus + dev deps"
pip install --upgrade pip
pip install -e ".[dev]"

echo "[postCreate] installing sandbox/bff deps"
(cd sandbox/bff && npm install --no-audit --no-fund)

echo "[postCreate] installing sandbox/web deps"
(cd sandbox/web && npm install --no-audit --no-fund)

echo "[postCreate] done"
