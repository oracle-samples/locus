#!/usr/bin/env bash
# One-shot setup, runs once per codespace creation.
# Installs locus (editable) + the workbench's two npm projects.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "[postCreate] installing locus + dev deps"
pip install --upgrade pip
pip install -e ".[dev]"

echo "[postCreate] installing workbench/bff deps"
(cd workbench/bff && npm install --no-audit --no-fund)

echo "[postCreate] installing workbench/web deps"
(cd workbench/web && npm install --no-audit --no-fund)

echo "[postCreate] done"
