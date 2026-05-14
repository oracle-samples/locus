#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""Tutorial 57: OCI GenAI via OCIOpenAIModel — the default transport.

This is the deep dive on Locus's default OCI transport,
:class:`OCIOpenAIModel`, which speaks OCI's OpenAI-compatible endpoint
at ``/openai/v1/chat/completions``. It is the right choice for the
vast majority of agents:

  - Covers every OCI model family in one transport (OpenAI commercial,
    Meta, Mistral, xAI, Gemini, non-R-series Cohere).
  - Day-0 support for new models OCI ships on the endpoint — no Locus
    update required.
  - Fully stateless on the wire (Locus owns the conversation history,
    hooks, tool calls, memory).
  - No Project OCID dependency.
  - Native streaming, native structured output via ``response_format``.

For Responses-only models or server-side conversation state, see
:mod:`tutorial_58_oci_responses` and :mod:`tutorial_00_oci_transports`.

This tutorial walks through:

  Part 1 — Basic completion against a single model family
  Part 2 — Streaming responses (SSE → ``ModelChunkEvent``)
  Part 3 — Tool calling end-to-end
  Part 4 — Structured output (Pydantic schema → typed parsed result)
  Part 5 — Swap model families with the same model class

Prerequisites:
  export OCI_PROFILE=<your-profile>            # ~/.oci/config profile
  export OCI_REGION=us-chicago-1               # GenAI inference region
  export OCI_COMPARTMENT=ocid1.compartment.…   # with GenAI policy

Difficulty: Beginner / Intermediate
"""

from __future__ import annotations

import asyncio
import os
import sys

from pydantic import BaseModel

from locus.agent import Agent
from locus.core.events import ModelChunkEvent
from locus.core.messages import Message
from locus.models.providers.oci import OCIOpenAIModel
from locus.tools.decorator import tool


def _env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.stderr.write(f"missing env var {name} — see prerequisites in the tutorial docstring\n")
        sys.exit(2)
    return val


REGION = os.environ.get("OCI_REGION", "us-chicago-1")
COMPARTMENT = os.environ.get("OCI_COMPARTMENT")


def _make_model(model_id: str) -> OCIOpenAIModel:
    """One factory — same class, swap the model id per part."""
    return OCIOpenAIModel(
        model=model_id,
        profile=_env("OCI_PROFILE"),
        region=REGION,
        compartment_id=COMPARTMENT,
    )


# =============================================================================
# Part 1 — Basic completion
# =============================================================================


def part1_basic() -> None:
    """One-shot completion against an OCI-hosted model."""
    print("=== Part 1: basic completion ===\n")
    model = _make_model("meta.llama-3.3-70b-instruct")
    agent = Agent(model=model, system_prompt="Answer in one sentence.")
    result = agent.run_sync("What is the capital of Australia?")
    print(f"  reply: {result.message.strip()}\n")


# =============================================================================
# Part 2 — Streaming
# =============================================================================


async def part2_streaming() -> None:
    """Stream tokens from the model as they arrive."""
    print("=== Part 2: streaming ===\n")
    model = _make_model("openai.gpt-5")
    print("  streamed: ", end="", flush=True)
    chunks = 0
    async for event in model.stream(
        [Message.system("Be brief."), Message.user("List 3 fruits, comma-separated.")]
    ):
        if isinstance(event, ModelChunkEvent) and event.content:
            print(event.content, end="", flush=True)
            chunks += 1
    print(f"\n  ({chunks} chunks)\n")


# =============================================================================
# Part 3 — Tool calling end-to-end
# =============================================================================


@tool
def get_time_in_city(city: str) -> str:
    """Return the current local time for a city (fake — always 14:30)."""
    return f"It is 14:30 in {city}."


def part3_tool_calling() -> None:
    """Agent picks the tool, the runtime executes it, model summarizes."""
    print("=== Part 3: tool calling ===\n")
    model = _make_model("openai.gpt-5")
    agent = Agent(
        model=model,
        tools=[get_time_in_city],
        max_iterations=4,
        system_prompt="Use get_time_in_city to answer time questions.",
    )
    result = agent.run_sync("What time is it in Tokyo?")
    print(f"  reply:      {result.message.strip()}")
    print(f"  iterations: {result.metrics.iterations}")
    print(f"  tool_calls: {result.metrics.tool_calls}\n")


# =============================================================================
# Part 4 — Structured output
# =============================================================================


class Weather(BaseModel):
    city: str
    temperature_c: int
    condition: str


def part4_structured_output() -> None:
    """Coerce the model to a Pydantic schema natively (OCI passes the
    JSON Schema through to the model's structured-output mode)."""
    from locus.agent import AgentConfig

    print("=== Part 4: structured output (Weather schema) ===\n")
    model = _make_model("openai.gpt-5")
    agent = Agent(
        config=AgentConfig(
            model=model,
            system_prompt="Return a weather report as JSON.",
            output_schema=Weather,
        )
    )
    result = agent.run_sync("Make up a sunny weather report for Lisbon.")
    parsed: Weather | None = result.parsed
    print(f"  parsed: {parsed!r}")
    print(f"  type:   {type(parsed).__name__}\n")


# =============================================================================
# Part 5 — Same class, different families
# =============================================================================


def part5_model_swap() -> None:
    """The same OCIOpenAIModel works against every family OCI ships on v1."""
    print("=== Part 5: same class, swap families ===\n")
    families = [
        "openai.gpt-5",
        "meta.llama-3.3-70b-instruct",
        "xai.grok-4-fast-non-reasoning",
        "cohere.command-a-03-2025",
    ]
    for fam in families:
        try:
            model = _make_model(fam)
            agent = Agent(model=model, system_prompt="Answer in three words or fewer.")
            result = agent.run_sync("Largest planet?")
            print(f"  {fam:42s} → {result.message.strip()}")
        except Exception as e:  # noqa: BLE001 — model availability varies per tenancy
            print(f"  {fam:42s} → [unavailable: {type(e).__name__}]")
    print()


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    print("=" * 70)
    print("Tutorial 57 — OCI GenAI via OCIOpenAIModel (chat/completions)")
    print("=" * 70 + "\n")
    print(f"OCI_PROFILE     = {os.environ.get('OCI_PROFILE', '(unset)')}")
    print(f"OCI_REGION      = {REGION}")
    print(f"OCI_COMPARTMENT = {(COMPARTMENT or '(unset)')[:60]}...\n")

    part1_basic()
    asyncio.run(part2_streaming())
    part3_tool_calling()
    part4_structured_output()
    part5_model_swap()

    print("=" * 70)
    print("Next: Tutorial 58 — OCI Responses transport (OCIResponsesModel)")
    print("=" * 70)


if __name__ == "__main__":
    main()
