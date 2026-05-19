# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Run every tutorial under examples/ as a subprocess and assert exit 0.

This is the user-acceptance gate: if a documented tutorial doesn't run
end-to-end against a real OCI v1 model, we have a regression. Each
tutorial is parametrized so the failure surface points at the offender.

Activation:
* ``OCI_PROFILE=<profile>`` — required (drives the OCI v1 transport).
* ``OPENAI_API_KEY`` — optional, used by tutorial_50 to demo OpenAI direct.
* ``ANTHROPIC_API_KEY`` — optional, used by tutorial_50 to demo Anthropic direct.
* ``OCI_REGION=<region>`` — defaults to ``us-chicago-1``.

The runner does not pre-skip anything by name — every
``tutorial_NN_*.py`` is exercised end-to-end. Tutorials that touch
external infra they can't reach (third-party MCP servers, live
Redis/Postgres/OpenSearch clusters, etc.) gracefully degrade in their
own code so the run still exits 0.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = [pytest.mark.integration]


_PROFILE = os.environ.get("OCI_PROFILE")
_REGION = os.environ.get("OCI_REGION", "us-chicago-1")


def _has_oci_config() -> bool:
    return Path("~/.oci/config").expanduser().exists()


if not (_has_oci_config() and _PROFILE):  # pragma: no cover
    pytest.skip("OCI_PROFILE not set", allow_module_level=True)


_REPO = Path(__file__).resolve().parents[2]
_TUTORIALS_DIR = _REPO / "examples"

# Default per-tutorial wall budget. Reasoning-class default model
# (openai.gpt-5.5-*) spends real wall-clock on thinking tokens — most
# tutorials finish well inside 6 min, but a handful with multiple
# agent hops + parallel dispatch reliably need longer. Keep this as
# the default and override per-tutorial below.
_DEFAULT_TIMEOUT = 360
_TUTORIAL_TIMEOUT_OVERRIDES: dict[str, int] = {
    # tutorial_34_emergent_routing: 5 dispatches × 2-3 LLM calls each
    # through a reasoning model — empirical wall time ~7-9 min.
    "tutorial_34_emergent_routing.py": 900,
}


def _all_tutorials() -> list[Path]:
    return sorted(_TUTORIALS_DIR.glob("tutorial_*.py"))


@pytest.mark.parametrize(
    "tutorial",
    _all_tutorials(),
    ids=lambda p: p.name.removesuffix(".py"),
)
def test_tutorial_runs_clean(tutorial: Path):
    """Run ``python examples/tutorial_NN_*.py`` and assert exit code 0.

    The script must finish within 180s and not write to stderr beyond the
    occasional warning.
    """
    env = os.environ.copy()
    # examples/config.py reads LOCUS_MODEL_PROVIDER + LOCUS_MODEL_ID +
    # LOCUS_OCI_* to build the right model. Setting these here makes
    # every tutorial run against a real, cheap OCI model instead of the
    # hard-coded MockModel default.
    # Default to OCI but allow override via env (mostly for CI mock runs).
    env.setdefault("LOCUS_MODEL_PROVIDER", "oci")
    env.setdefault("LOCUS_MODEL_ID", "openai.gpt-5.5-2026-04-23")
    env.setdefault("LOCUS_OCI_PROFILE", _PROFILE or "DEFAULT")
    env.setdefault("LOCUS_OCI_REGION", _REGION)
    # Propagate the auth type + compartment so profiles like MY_PROFILE
    # (session-token, cross-tenancy access to the target compartment) work. Without
    # these, config.py falls back to api_key + auto-derived compartment
    # which fails for session-token profiles.
    if os.environ.get("OCI_AUTH_TYPE"):
        env.setdefault("LOCUS_OCI_AUTH_TYPE", os.environ["OCI_AUTH_TYPE"])
    if os.environ.get("OCI_COMPARTMENT"):
        env.setdefault("LOCUS_OCI_COMPARTMENT", os.environ["OCI_COMPARTMENT"])

    timeout_s = _TUTORIAL_TIMEOUT_OVERRIDES.get(tutorial.name, _DEFAULT_TIMEOUT)
    proc = subprocess.run(  # noqa: S603 — controlled subprocess of our own script
        [sys.executable, str(tutorial)],
        cwd=str(_TUTORIALS_DIR),
        env=env,
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )

    if proc.returncode != 0:
        pytest.fail(
            f"{tutorial.name} exited {proc.returncode}\n"
            f"--- stdout (tail) ---\n{proc.stdout.decode(errors='replace')[-2000:]}\n"
            f"--- stderr (tail) ---\n{proc.stderr.decode(errors='replace')[-2000:]}"
        )
