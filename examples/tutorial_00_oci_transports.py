# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 00: OCI Generative AI — the three transports

Locus exposes OCI GenAI through three different transports. They are
not interchangeable — picking the right one depends on the model
family you're calling and whether you want server-side conversation
state. This tutorial constructs an agent against each one, runs the
same prompt, and explains when to use which.

Pick the right one by reading from the top — the first one that
applies wins.

  1. ``OCIResponsesModel`` — server-stateful, /openai/v1/responses
     - The model family is Responses-only on OCI (e.g. openai.gpt-5.5-pro).
     - You want OCI to hold the conversation thread between turns and
       reference it by previous_response_id (cheap multi-turn).
     - You're OK with one Locus primitive standing down:
       ``ConversationManager`` (no client-side history to shape).
     - Everything else — memory, hooks, reflexion, GSAR, grounding,
       idempotency, output schema, streaming, termination — still works.

  2. ``OCIModel`` — native OCI SDK, /20231130/actions/v1
     - The model family is Cohere R-series (cohere.command-r*).
       The OpenAI-compat endpoint rejects R-series; this is the only
       path that works for those models.
     - You're using workload identity that the openai SDK + httpx
       signer combo can't handle cleanly (rare).

  3. ``OCIOpenAIModel`` — OpenAI-compat, /openai/v1/chat/completions
     - Anything else. This is the default. Covers all OCI model
       families (Cohere non-R, Meta, Mistral, OpenAI, xAI, Gemini) in
       one transport. No Project OCID dependency, fully stateless,
       supports streaming and structured outputs natively.

Prerequisites:
- An OCI config profile at ~/.oci/config that can reach the GenAI
  inference endpoint in your region. Set:
    export OCI_PROFILE=<your-profile>
    export OCI_REGION=us-chicago-1                  # or your region
    export OCI_COMPARTMENT=ocid1.compartment.oc1..… # compartment with GenAI access
- Run with --transport responses|sdk|v1|all (default: all)

Difficulty: Beginner
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any


def _env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.stderr.write(
            f"missing env var {name} — see the prerequisites in the tutorial docstring\n"
        )
        sys.exit(2)
    return val


# =============================================================================
# Transport 1 — OCIResponsesModel (server-stateful Responses API)
# =============================================================================


def example_responses_transport() -> None:
    """Server-stateful: OCI holds the thread, we reference it by id.

    The agent runtime detects ``model.server_stateful = True`` and
    automatically:
      - Sends only the latest-turn slice instead of the full history.
      - Threads ``provider_state`` (the continuation token) across calls.
      - Skips ``ConversationManager`` strategies (nothing to trim
        client-side when the history lives server-side).

    Everything else — tool hooks, idempotency, output schema, streaming,
    reflexion, GSAR — works identically to the other transports.
    """
    from locus.agent import Agent
    from locus.models.providers.oci import OCIResponsesModel

    print("=== Transport 1: OCIResponsesModel (server-stateful) ===\n")

    model = OCIResponsesModel(
        # gpt-5.5-pro is *only* reachable via Responses on OCI today.
        # Regular gpt-5.5 works on both transports.
        model="openai.gpt-5.5-pro",
        profile=_env("OCI_PROFILE"),
        region=os.environ.get("OCI_REGION", "us-chicago-1"),
        compartment_id=os.environ.get("OCI_COMPARTMENT"),
        # project_ocid=...  # optional; required only by some Responses features
    )

    agent = Agent(model=model, system_prompt="Answer in one short sentence.")
    result = agent.run_sync("What is the largest mammal on Earth?")
    print(f"  reply:           {result.message.strip()}")
    print(f"  iterations:      {result.metrics.iterations}")
    # After the first turn, AgentState carries the continuation id so a
    # follow-up agent.run(...) on the same thread_id resumes server-side.
    print(f"  server_stateful: {type(model).server_stateful}")
    print()


# =============================================================================
# Transport 2 — OCIModel (native OCI SDK, for Cohere R-series)
# =============================================================================


def example_sdk_transport() -> None:
    """Cohere R-series only. The OpenAI-compat endpoint rejects them.

    OCIModel speaks OCI's proprietary chat shape via the official OCI
    Python SDK. Use ``cohere.command-r`` / ``cohere.command-r-plus``
    here — every other model family goes through the v1 transport.
    """
    from locus.agent import Agent
    from locus.models.providers.oci import OCIModel

    print("=== Transport 2: OCIModel (native SDK, Cohere R-series) ===\n")

    model = OCIModel(
        model_id="cohere.command-r-plus-08-2024",
        profile_name=_env("OCI_PROFILE"),
        auth_type="api_key",  # session/instance/resource also supported
        compartment_id=os.environ.get("OCI_COMPARTMENT"),
        service_endpoint=(
            f"https://inference.generativeai.{os.environ.get('OCI_REGION', 'us-chicago-1')}"
            ".oci.oraclecloud.com"
        ),
    )

    agent = Agent(model=model, system_prompt="Answer in one short sentence.")
    result = agent.run_sync("What is the largest mammal on Earth?")
    print(f"  reply:           {result.message.strip()}")
    print(f"  iterations:      {result.metrics.iterations}")
    print(f"  server_stateful: {getattr(type(model), 'server_stateful', False)}")
    print()


# =============================================================================
# Transport 3 — OCIOpenAIModel (OpenAI-compat /openai/v1, default)
# =============================================================================


def example_v1_transport() -> None:
    """The default. Use this for everything except Cohere R-series and
    Responses-only models.

    Covers OpenAI / Meta / Mistral / xAI / Gemini / non-R Cohere via
    one consistent OpenAI-compatible shape. Day-0 model support — when
    OCI ships a new model on this endpoint, no Locus update needed.
    """
    from locus.agent import Agent
    from locus.models.providers.oci import OCIOpenAIModel

    print("=== Transport 3: OCIOpenAIModel (/openai/v1, default) ===\n")

    model = OCIOpenAIModel(
        model="meta.llama-3.3-70b-instruct",
        profile=_env("OCI_PROFILE"),
        region=os.environ.get("OCI_REGION", "us-chicago-1"),
        compartment_id=os.environ.get("OCI_COMPARTMENT"),
    )

    agent = Agent(model=model, system_prompt="Answer in one short sentence.")
    result = agent.run_sync("What is the largest mammal on Earth?")
    print(f"  reply:           {result.message.strip()}")
    print(f"  iterations:      {result.metrics.iterations}")
    print(f"  server_stateful: {getattr(type(model), 'server_stateful', False)}")
    print()


# =============================================================================
# Side-by-side comparison table
# =============================================================================


def print_comparison() -> None:
    """A quick decision table the reader can refer back to."""
    print("=== Decision table ===\n")
    rows: list[tuple[str, str, str, str]] = [
        ("Endpoint", "/openai/v1/responses", "/20231130/actions/v1", "/openai/v1/chat/completions"),
        ("Class", "OCIResponsesModel", "OCIModel", "OCIOpenAIModel"),
        ("Stateful?", "server-side", "stateless", "stateless"),
        (
            "Model families",
            "openai, xai, gemini (Responses-only)",
            "cohere.command-r*",
            "all (default)",
        ),
        ("Project OCID", "optional", "no", "no"),
        ("ConversationManager", "skipped", "applies", "applies"),
        ("Memory / hooks / GSAR", "all apply", "all apply", "all apply"),
        ("Streaming", "yes (SSE)", "yes", "yes (SSE)"),
        ("Structured output", "yes", "limited", "yes"),
    ]
    width = max(len(r[0]) for r in rows) + 2
    cols = [width, 26, 24, 30]
    header = ("Field", "Responses (server-stateful)", "OCIModel (SDK)", "OCIOpenAIModel (v1)")
    print(" ".join(f"{c:<{w}}" for c, w in zip(header, cols, strict=False)))
    print(" ".join("-" * w for w in cols))
    for r in rows:
        print(" ".join(f"{c:<{w}}" for c, w in zip(r, cols, strict=False)))
    print()


# =============================================================================
# Main
# =============================================================================


async def _amain(which: str) -> None:
    if which in ("all", "responses"):
        try:
            example_responses_transport()
        except Exception as e:  # noqa: BLE001 — surface clearly to the reader
            print(f"  [responses transport raised: {type(e).__name__}: {e}]\n")
    if which in ("all", "sdk"):
        try:
            example_sdk_transport()
        except Exception as e:  # noqa: BLE001
            print(f"  [sdk transport raised: {type(e).__name__}: {e}]\n")
    if which in ("all", "v1"):
        try:
            example_v1_transport()
        except Exception as e:  # noqa: BLE001
            print(f"  [v1 transport raised: {type(e).__name__}: {e}]\n")
    print_comparison()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--transport",
        choices=("all", "responses", "sdk", "v1"),
        default="all",
        help="which transport to demo (default: all)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Tutorial 00: OCI Generative AI — the three transports")
    print("=" * 70)
    print()
    print(f"OCI_PROFILE     = {os.environ.get('OCI_PROFILE', '(unset)')}")
    print(f"OCI_REGION      = {os.environ.get('OCI_REGION', 'us-chicago-1 (default)')}")
    print(f"OCI_COMPARTMENT = {os.environ.get('OCI_COMPARTMENT', '(unset)')[:60]}...")
    print()

    asyncio.run(_amain(args.transport))

    print("=" * 70)
    print("Next: Tutorial 01 — Basic Agent")
    print("=" * 70)


if __name__ == "__main__":
    main()
