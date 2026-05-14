#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""Tutorial 58: OCI GenAI via OCIResponsesModel — server-stateful (or not).

Locus's third OCI transport, :class:`OCIResponsesModel`, talks to
``/openai/v1/responses`` — the same endpoint OpenAI's Responses API
uses. It exists for two reasons:

  1. Reach Responses-only OCI models (``openai.gpt-5.5-pro`` today,
     more later) that the chat/completions endpoint rejects.
  2. Push conversation state to the OCI side so multi-turn doesn't
     re-send the full history each request.

This tutorial covers both modes:

  Part 1 — Stateless / Zero Data Retention (``store=False``)
            Required for enterprise OCI tenancies with ZDR enabled.
            The model sends ``store: false``, drops
            ``previous_response_id``, advertises
            ``server_stateful=False`` so the agent runs in
            chat/completions-like full-history mode but still over the
            Responses endpoint. ZDR tenants still unlock
            Responses-only models.

  Part 2 — Server-side state (``store=True``, default)
            Non-ZDR tenancies. The server persists each response and
            Locus references it on the next turn via
            ``provider_state["previous_response_id"]``. Only the
            latest-turn slice is sent — payloads stay small.

  Part 3 — Tools end-to-end through the Responses input shape
            Tool calls become ``function_call`` items in the input;
            results become ``function_call_output`` items keyed by
            ``call_id``. The agent loop's hook surface (idempotency,
            ``on_before_tool_call`` / ``on_after_tool_call``) works
            identically to the other transports.

  Part 4 — Streaming via SSE
            ``output_text.delta`` events arrive as
            :class:`ModelChunkEvent` instances with ``content`` set.

The only Locus primitive that bypasses on the Responses path is
:class:`ConversationManager` (window/summarize have nothing to operate
on when the server owns the history). Everything else — memory,
Reflexion, GSAR, grounding, hooks, idempotency, checkpointing, output
schema, streaming, termination conditions — works identically. See
``docs/concepts/oci-responses.md`` for the full matrix.

Prerequisites:
  export OCI_PROFILE=<your-profile>
  export OCI_REGION=us-chicago-1
  export OCI_COMPARTMENT=ocid1.compartment.…
  export OCI_RESPONSES_STORE=0     # set to 1 to also run Part 2 (skip if your tenant has ZDR)

Difficulty: Intermediate
"""

from __future__ import annotations

import asyncio
import os
import sys

from locus.agent import Agent
from locus.core.events import ModelChunkEvent, TerminateEvent
from locus.core.messages import Message
from locus.models.providers.oci import OCIResponsesModel
from locus.tools.decorator import tool


def _env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.stderr.write(f"missing env var {name} — see prerequisites in the tutorial docstring\n")
        sys.exit(2)
    return val


REGION = os.environ.get("OCI_REGION", "us-chicago-1")
COMPARTMENT = os.environ.get("OCI_COMPARTMENT")
STORE_ENABLED = os.environ.get("OCI_RESPONSES_STORE", "0") == "1"


def _make_model(*, store: bool) -> OCIResponsesModel:
    return OCIResponsesModel(
        model="openai.gpt-5",  # any Responses-supported model id; gpt-5.5-pro for Pro
        profile=_env("OCI_PROFILE"),
        region=REGION,
        compartment_id=COMPARTMENT,
        store=store,
    )


# =============================================================================
# Part 1 — Stateless / ZDR-friendly (store=False)
# =============================================================================


async def part1_stateless_multiturn() -> None:
    """Multi-turn with store=False: agent sends full history each turn,
    server holds no state. Works in every tenancy including ZDR.
    """
    print("=== Part 1: stateless multi-turn (store=False, ZDR-safe) ===\n")
    model = _make_model(store=False)
    print(f"  server_stateful (instance): {model.server_stateful}  ← False = stateless\n")

    msgs = [
        Message.system("You remember user-shared facts and recall them on demand."),
        Message.user("My favorite color is purple. Just acknowledge."),
    ]
    r1 = await model.complete(msgs)
    print(f"  turn 1 reply: {(r1.message.content or '').strip()[:80]!r}")
    print(f"  turn 1 provider_state: {r1.provider_state}  ← empty in stateless mode\n")

    # Turn 2: hand the model the full history including its prior reply.
    msgs2 = [*msgs, r1.message, Message.user("What is my favorite color?")]
    r2 = await model.complete(msgs2)
    print(f"  turn 2 reply: {(r2.message.content or '').strip()[:120]!r}")
    print(f"  → recalled 'purple' from history: {'purple' in (r2.message.content or '').lower()}\n")

    await model.aclose()


# =============================================================================
# Part 2 — Server-side state (store=True, default; non-ZDR only)
# =============================================================================


async def part2_server_state_multiturn() -> None:
    """Multi-turn with store=True: server holds the thread; Locus threads
    `previous_response_id` between turns. Skipped if OCI_RESPONSES_STORE!=1.
    """
    print("=== Part 2: server-side state (store=True, non-ZDR) ===\n")
    if not STORE_ENABLED:
        print("  skipped — set OCI_RESPONSES_STORE=1 to run (only works in non-ZDR tenancies)\n")
        return

    model = _make_model(store=True)
    print(f"  server_stateful (instance): {model.server_stateful}  ← True = stateful\n")

    r1 = await model.complete(
        [
            Message.system("You remember user-shared facts and recall them on demand."),
            Message.user("My favorite color is purple. Just acknowledge."),
        ]
    )
    print(f"  turn 1 reply: {(r1.message.content or '').strip()[:80]!r}")
    print(f"  turn 1 provider_state: {r1.provider_state}\n")

    # Turn 2: send ONLY the new user message; server picks up via continuation id.
    r2 = await model.complete(
        [Message.user("What is my favorite color?")],
        provider_state=r1.provider_state,
    )
    print(f"  turn 2 reply: {(r2.message.content or '').strip()[:120]!r}")
    print(f"  turn 2 provider_state: {r2.provider_state}  ← new continuation id\n")

    await model.aclose()


# =============================================================================
# Part 3 — Tool round-trip
# =============================================================================


@tool
def get_temperature(city: str) -> str:
    """Return the current temperature for a city in Celsius (fake)."""
    return f"The temperature in {city} is 18 C."


async def part3_tool_roundtrip() -> None:
    """Full Agent + @tool flow through OCIResponsesModel. Tool call →
    server returns ``function_call`` item → agent runs the tool client-side
    → posts back ``function_call_output`` → server produces final answer.
    """
    print("=== Part 3: tool round-trip (store=False) ===\n")
    model = _make_model(store=False)
    agent = Agent(
        model=model,
        tools=[get_temperature],
        max_iterations=4,
        system_prompt="Use get_temperature to answer temperature questions.",
    )

    final: TerminateEvent | None = None
    async for ev in agent.run("What's the temperature in Paris?"):
        if isinstance(ev, TerminateEvent):
            final = ev
            break

    assert final is not None
    print(f"  reply:      {(final.final_message or '').strip()}")
    print(f"  iterations: {final.iterations_used}")
    print(f"  tool_calls: {final.total_tool_calls}\n")
    await model.aclose()


# =============================================================================
# Part 4 — Streaming via SSE
# =============================================================================


async def part4_streaming() -> None:
    """Stream tokens from the Responses endpoint. Same ModelChunkEvent
    surface as every other Locus model — the SSE translation is
    invisible to the agent layer.
    """
    print("=== Part 4: streaming ===\n")
    model = _make_model(store=False)
    print("  streamed: ", end="", flush=True)
    chunks = 0
    async for event in model.stream(
        [Message.system("Be brief."), Message.user("Count to five, one number per line.")]
    ):
        if isinstance(event, ModelChunkEvent) and event.content:
            print(event.content, end="", flush=True)
            chunks += 1
    print(f"\n  ({chunks} chunks)\n")
    await model.aclose()


# =============================================================================
# Main
# =============================================================================


async def _amain() -> None:
    await part1_stateless_multiturn()
    await part2_server_state_multiturn()
    await part3_tool_roundtrip()
    await part4_streaming()


def main() -> None:
    print("=" * 70)
    print("Tutorial 58 — OCI Responses transport (OCIResponsesModel)")
    print("=" * 70 + "\n")
    print(f"OCI_PROFILE              = {os.environ.get('OCI_PROFILE', '(unset)')}")
    print(f"OCI_REGION               = {REGION}")
    print(f"OCI_COMPARTMENT          = {(COMPARTMENT or '(unset)')[:60]}...")
    print(
        f"OCI_RESPONSES_STORE      = {'1 (try store=True too)' if STORE_ENABLED else '0 (ZDR-safe only)'}\n"
    )

    asyncio.run(_amain())

    print("=" * 70)
    print("See also: docs/concepts/oci-responses.md")
    print("=" * 70)


if __name__ == "__main__":
    main()
