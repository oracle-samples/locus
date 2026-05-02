"""Smoke tests for the deploy/helm/locus-agent chart and the root Dockerfile.

These don't run helm or docker. They validate:
- All required chart files exist with the right shape.
- `Chart.yaml` has the canonical fields.
- `values.yaml` parses and contains the keys the templates reference.
- The Dockerfile contains the expected stages and HEALTHCHECK.

If `helm` is available in PATH, also runs `helm lint` and `helm template`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CHART_DIR = REPO_ROOT / "deploy" / "helm" / "locus-agent"
DOCKERFILE = REPO_ROOT / "Dockerfile"


REQUIRED_CHART_FILES = (
    "Chart.yaml",
    "values.yaml",
    ".helmignore",
    "README.md",
    "templates/_helpers.tpl",
    "templates/deployment.yaml",
    "templates/service.yaml",
    "templates/serviceaccount.yaml",
    "templates/secret.yaml",
    "templates/hpa.yaml",
    "templates/ingress.yaml",
)


def test_dockerfile_exists_at_repo_root():
    assert DOCKERFILE.exists(), f"Dockerfile missing at {DOCKERFILE}"


def test_dockerfile_has_multistage_build():
    body = DOCKERFILE.read_text()
    assert "AS builder" in body, "expected named 'builder' stage"
    assert "AS runtime" in body, "expected named 'runtime' stage"


def test_dockerfile_uses_non_root_user():
    body = DOCKERFILE.read_text()
    assert "useradd" in body, "Dockerfile should create a non-root user"
    assert "USER locus" in body, "Dockerfile should drop privileges to that user"


def test_dockerfile_has_healthcheck():
    body = DOCKERFILE.read_text()
    assert "HEALTHCHECK" in body
    assert "/health" in body


def test_dockerfile_installs_server_extras():
    body = DOCKERFILE.read_text()
    # `[oci,server,checkpoints]` covers production deployment basics.
    assert "[oci,server,checkpoints]" in body


def test_chart_directory_exists():
    assert CHART_DIR.is_dir(), f"chart dir missing at {CHART_DIR}"


@pytest.mark.parametrize("rel_path", REQUIRED_CHART_FILES)
def test_chart_has_required_files(rel_path: str):
    path = CHART_DIR / rel_path
    assert path.exists(), f"chart file missing: {rel_path}"


def test_chart_yaml_has_canonical_fields():
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load((CHART_DIR / "Chart.yaml").read_text())
    assert data["apiVersion"] == "v2"
    assert data["name"] == "locus-agent"
    assert data["type"] == "application"
    assert "version" in data
    assert "appVersion" in data


def test_values_yaml_parses_with_expected_keys():
    yaml = pytest.importorskip("yaml")
    values = yaml.safe_load((CHART_DIR / "values.yaml").read_text())

    # Top-level sections referenced by the templates.
    for key in (
        "image",
        "replicaCount",
        "auth",
        "serviceAccount",
        "resources",
        "probes",
        "service",
        "ingress",
        "autoscaling",
        "ociBucket",
    ):
        assert key in values, f"values.yaml missing top-level key: {key}"

    # Auth shape.
    assert "secretKey" in values["auth"]
    # Probes have liveness + readiness + startup.
    for probe in ("liveness", "readiness", "startup"):
        assert probe in values["probes"], f"probes.{probe} missing"


@pytest.mark.skipif(shutil.which("helm") is None, reason="helm CLI not available")
def test_helm_lint_passes():
    """If helm is on PATH, run `helm lint` against the chart."""
    helm = shutil.which("helm")
    assert helm is not None  # narrowed by skipif; helps the type checker
    result = subprocess.run(  # noqa: S603 — args fully controlled, helm path resolved
        [helm, "lint", str(CHART_DIR)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"helm lint failed:\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


@pytest.mark.skipif(shutil.which("helm") is None, reason="helm CLI not available")
def test_helm_template_renders():
    """If helm is on PATH, render templates with default values."""
    helm = shutil.which("helm")
    assert helm is not None
    result = subprocess.run(  # noqa: S603 — args fully controlled, helm path resolved
        [
            helm,
            "template",
            "test-release",
            str(CHART_DIR),
            "--set",
            "auth.apiKey=dummy",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"helm template failed:\n--- stdout ---\n{result.stdout[:2000]}\n--- stderr ---\n{result.stderr}"
    )
    # Sanity: rendered output should include the Deployment.
    assert "kind: Deployment" in result.stdout
    assert "kind: Service" in result.stdout


def test_pyproject_has_server_extra():
    """The `server` extra should pin FastAPI + uvicorn for prod deployments."""
    text = (REPO_ROOT / "pyproject.toml").read_text()
    assert "server = [" in text
    # The block should mention FastAPI + uvicorn.
    server_block_start = text.index("server = [")
    server_block_end = text.index("]", server_block_start)
    block = text[server_block_start:server_block_end]
    assert "fastapi" in block
    assert "uvicorn" in block
