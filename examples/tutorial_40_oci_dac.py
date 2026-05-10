# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 40: OCI Dedicated AI Cluster (DAC) endpoints

This tutorial covers locus's DAC support. A DAC is OCI's
provisioned-capacity serving mode for OCI GenAI: instead of pay-per-token
inference against a shared model id, you address a dedicated endpoint
by its OCID (``ocid1.generativeaiendpoint.oc1.<region>....``) and
inference is routed to your cluster.

Locus auto-detects DAC OCIDs and routes them through the SDK
transport (``OCIModel``) — the V1 OpenAI-compatible transport can't
speak ``DedicatedServingMode``. Both non-streaming ``complete()`` and
real SSE ``stream()`` work end-to-end against a DAC.

This tutorial covers:

- Part 1: how DAC routing is decided (``ocid1.generativeaiendpoint.``
  prefix → ``OCIModel``).
- Part 2: configure an ``Agent`` against a DAC endpoint.
- Part 3: drive ``complete()`` against the DAC with one prompt.
- Part 4: drive ``stream()`` and watch SSE deltas come back.
- Part 5: wire the DAC into a tool-using ``Agent`` so the model sitting
  on dedicated capacity can call your @tool functions.

Prerequisites:
- ``oci`` SDK installed (``pip install -e ".[oci]"``).
- An OCI profile with permission to invoke the DAC endpoint.
- The DAC endpoint OCID, the compartment OCID, and the region.

Set these env vars (kept out of the source so the tutorial works for
any DAC):

  export OCI_DAC_ENDPOINT_OCID=ocid1.generativeaiendpoint.oc1.uk-london-1....
  export OCI_DAC_COMPARTMENT_ID=ocid1.compartment.oc1....
  export OCI_DAC_REGION=uk-london-1
  export OCI_PROFILE=MY_DAC_PROFILE

Without those env vars Parts 2-5 print the wiring snippet and skip.

Difficulty: Intermediate
"""

from __future__ import annotations

import asyncio
import os


# =============================================================================
# Part 1: Auto-routing
# =============================================================================


def example_routing() -> None:
    """How locus decides to use the SDK transport for DAC OCIDs."""
    print("=== Part 1: Auto-routing ===\n")

    print("locus.models.registry inspects the model id with three rules:")
    print()
    print("  1. ocid1.generativeaiendpoint.<region>....   → OCIModel (SDK)")
    print("  2. cohere.command-r-*                         → OCIModel (SDK)")
    print("  3. everything else                            → OCIOpenAIModel (V1)")
    print()
    print("So both calls route to the SDK transport:")
    print()
    print('  Agent(model="oci:cohere.command-r-plus-08-2024")  # rule 2')
    print('  Agent(model="oci:ocid1.generativeaiendpoint....")  # rule 1')
    print()
    print("DAC needs the SDK transport because DedicatedServingMode")
    print("(endpoint_id=...) is part of the OCI proprietary chat shape,")
    print("not the OpenAI-compatible /v1/chat/completions endpoint.")


# =============================================================================
# Part 2: Configure an Agent against a DAC
# =============================================================================


def _dac_env_ready() -> bool:
    return bool(
        os.environ.get("OCI_DAC_ENDPOINT_OCID") and os.environ.get("OCI_DAC_COMPARTMENT_ID")
    )


def example_configure_agent() -> None:
    """Build an Agent pointed at a DAC. Just like any other model."""
    print("\n=== Part 2: Configure Agent against a DAC ===\n")

    if not _dac_env_ready():
        print("OCI_DAC_ENDPOINT_OCID / OCI_DAC_COMPARTMENT_ID not set.")
        print()
        print("Wiring (with the env vars set):")
        print("""
  from locus import Agent
  from locus.models import get_model

  # Pre-build the model — DAC needs provider-specific kwargs that
  # Agent's strict AgentConfig doesn't accept on the keyword path.
  region = os.environ["OCI_DAC_REGION"]
  model = get_model(
      f"oci:{os.environ['OCI_DAC_ENDPOINT_OCID']}",
      compartment_id=os.environ["OCI_DAC_COMPARTMENT_ID"],
      profile_name=os.environ.get("OCI_PROFILE", "DEFAULT"),
      service_endpoint=(
          f"https://inference.generativeai.{region}.oci.oraclecloud.com"
      ),
  )
  agent = Agent(
      model=model,
      system_prompt="You are a concise assistant.",
  )
""")
        return

    from locus import Agent
    from locus.models import get_model

    region = os.environ.get("OCI_DAC_REGION", "us-chicago-1")
    model = get_model(
        f"oci:{os.environ['OCI_DAC_ENDPOINT_OCID']}",
        compartment_id=os.environ["OCI_DAC_COMPARTMENT_ID"],
        profile_name=os.environ.get("OCI_PROFILE", "DEFAULT"),
        service_endpoint=f"https://inference.generativeai.{region}.oci.oraclecloud.com",
    )
    agent = Agent(
        model=model,
        system_prompt="You are a concise assistant. Reply briefly.",
        max_iterations=2,
    )
    print(f"Agent configured against DAC endpoint in {region}.")
    print(f"  underlying model class:  {type(agent._model).__name__}")
    print("  serving mode (DAC):       DedicatedServingMode (set by client)")


# =============================================================================
# Part 3: complete() — single round-trip
# =============================================================================


async def example_complete() -> None:
    """Fire one chat at the DAC and print what comes back."""
    print("\n=== Part 3: complete() against the DAC ===\n")

    if not _dac_env_ready():
        print("Skipping — env vars not set.")
        return

    from locus.core.messages import Message
    from locus.models.providers.oci import OCIAuthType, OCIModel

    region = os.environ.get("OCI_DAC_REGION", "us-chicago-1")
    model = OCIModel(
        model_id=os.environ["OCI_DAC_ENDPOINT_OCID"],
        compartment_id=os.environ["OCI_DAC_COMPARTMENT_ID"],
        profile_name=os.environ.get("OCI_PROFILE", "DEFAULT"),
        auth_type=OCIAuthType.API_KEY,
        service_endpoint=f"https://inference.generativeai.{region}.oci.oraclecloud.com",
        max_tokens=128,
    )

    response = await model.complete(
        messages=[
            Message.user("In one sentence, what model are you?"),
        ],
        tools=None,
    )
    content = (response.message.content or "").strip()
    print(f"Reply:        {content!r}")
    print(f"usage:        {response.usage}")
    print(f"stop_reason:  {response.stop_reason}")


# =============================================================================
# Part 4: stream() — real SSE deltas
# =============================================================================


async def example_stream() -> None:
    """Stream from the DAC and print each delta as it arrives."""
    print("\n=== Part 4: stream() against the DAC ===\n")

    if not _dac_env_ready():
        print("Skipping — env vars not set.")
        return

    from locus.core.messages import Message
    from locus.models.providers.oci import OCIAuthType, OCIModel

    region = os.environ.get("OCI_DAC_REGION", "us-chicago-1")
    model = OCIModel(
        model_id=os.environ["OCI_DAC_ENDPOINT_OCID"],
        compartment_id=os.environ["OCI_DAC_COMPARTMENT_ID"],
        profile_name=os.environ.get("OCI_PROFILE", "DEFAULT"),
        auth_type=OCIAuthType.API_KEY,
        service_endpoint=f"https://inference.generativeai.{region}.oci.oraclecloud.com",
        max_tokens=64,
    )

    print("Streaming reply (chunks shown inline):")
    print("  ", end="", flush=True)
    async for event in model.stream(
        messages=[Message.user("Count from 1 to 5, separated by commas.")],
        tools=None,
    ):
        if event.content:
            print(event.content, end="", flush=True)
        if event.done:
            break
    print()


# =============================================================================
# Part 5: Agent + tool against the DAC
# =============================================================================


async def example_agent_with_tool() -> None:
    """Wire a tool-using Agent on top of the DAC.

    The DAC endpoint sees the same tool schema your on-demand models
    do — locus passes the OpenAI-style tool definitions in the
    ``GenericChatRequest.tools`` field. Whether the model on the
    other end emits structured tool calls (OpenAI format,
    ``message.tool_calls``) or text-format tool calls (Qwen's
    ``<tool_call>{...}</tool_call>`` XML wrapper, etc.) depends on
    the model and the deployment configuration:

    - **OpenAI / Llama / Cohere on OCI** — emit structured
      ``tool_calls``. Locus extracts them automatically.
    - **Qwen on a DAC** — by default emits ``<tool_call>`` text
      blocks. Locus's parser doesn't extract these, so
      ``result.metrics.tool_calls`` will be 0 even though the model
      "called" the tool in its content. Two options to fix:
        (a) Configure the DAC to enable OpenAI-compatible tool-call
            output (Qwen3 family supports this via
            ``--enable-auto-tool-choice`` on the deployment).
        (b) Wrap the agent with a parser that extracts the
            ``<tool_call>`` blocks from ``result.message`` and
            re-issues them as locus ToolCall objects.

    This part of the tutorial just shows the wiring — what the model
    does with it depends on the model.
    """
    print("\n=== Part 5: Agent + @tool against the DAC ===\n")

    if not _dac_env_ready():
        print("Skipping — env vars not set.")
        return

    from locus import Agent
    from locus.models import get_model
    from locus.tools.decorator import tool

    @tool(name="add_two_numbers")
    def add_two_numbers(a: int, b: int) -> int:
        """Return the sum of two integers."""
        return a + b

    region = os.environ.get("OCI_DAC_REGION", "us-chicago-1")
    model = get_model(
        f"oci:{os.environ['OCI_DAC_ENDPOINT_OCID']}",
        compartment_id=os.environ["OCI_DAC_COMPARTMENT_ID"],
        profile_name=os.environ.get("OCI_PROFILE", "DEFAULT"),
        service_endpoint=f"https://inference.generativeai.{region}.oci.oraclecloud.com",
    )
    agent = Agent(
        model=model,
        tools=[add_two_numbers],
        system_prompt="You can call add_two_numbers when asked to add. Reply briefly.",
        max_iterations=4,
    )

    result = await asyncio.to_thread(
        agent.run_sync,
        "Use the add_two_numbers tool to add 7 and 35, then state the result in one sentence.",
    )
    print(f"final message:        {result.message.strip()[:200]}")
    print(f"iterations:           {result.metrics.iterations}")
    print(f"locus tool calls:     {result.metrics.tool_calls}")
    if "<tool_call>" in (result.message or ""):
        print()
        print("Note: the model emitted a <tool_call> text block instead of a")
        print("structured tool_call. See the docstring for how to handle this")
        print("(deployment flag or post-processing parser).")


# =============================================================================
# Main
# =============================================================================


async def _async_main() -> None:
    example_routing()
    example_configure_agent()
    await example_complete()
    await example_stream()
    await example_agent_with_tool()


if __name__ == "__main__":
    asyncio.run(_async_main())
