#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Tutorial 07: durable agent threads on Oracle Database 26ai.

In-memory and on-disk checkpointers are fine for local development —
when the process restarts, the conversation is gone. This tutorial
wires Locus's ``oracle_checkpointer`` adapter against an Oracle Cloud
Infrastructure (OCI) Autonomous Database 26ai so agent threads survive
process restarts, scale out across replicas, and can be picked up from
another machine.

Key concepts:

- ``oracle_checkpointer(...)`` returns a ``StorageBackendAdapter``
  wrapped around ``OracleBackend``. It writes the ``AgentState`` JSON
  to a CLOB column keyed by ``thread_id``.
- ``cp.save(state, thread_id=...)`` persists; ``cp.load(thread_id)``
  rehydrates the same ``AgentState`` (messages, metrics, all of it).
- ``cp.list_threads()`` enumerates every persisted conversation — the
  primitive admin dashboards use to enumerate sessions.
- The vector store from tutorial 05 and this checkpointer can share a
  single Autonomous Database wallet.

The demo simulates two sessions: session 1 writes a few turns, session
2 (a "different process") loads the same thread id and appends more.
The state survives between them.

Run it::

    export ORACLE_DSN=mydb_low                   # tnsnames alias
    export ORACLE_USER=locus_app                 # least-privileged app schema
    export ORACLE_PASSWORD='<app-password>'
    export ORACLE_WALLET=~/.oci/wallets/mydb
    export ORACLE_WALLET_PASSWORD='<wallet-pw>'  # if the wallet is encrypted

    python examples/tutorial_07_oracle_26ai_checkpointer.py

If ``ORACLE_DSN`` / ``ORACLE_PASSWORD`` aren't set the tutorial prints
the wiring snippet and exits cleanly — no traceback, no
half-initialised state.

Difficulty: Intermediate. Self-contained — no prior tutorial required.
"""

from __future__ import annotations

import asyncio
import os
import sys

from locus.core.messages import Message
from locus.core.state import AgentState
from locus.memory.backends import oracle_checkpointer


_REQUIRED_ENV = (
    "ORACLE_DSN",
    "ORACLE_USER",
    "ORACLE_PASSWORD",
    "ORACLE_WALLET",
)


THREAD_ID = "tutorial_07_thread"


def _missing_env() -> list[str]:
    return [name for name in _REQUIRED_ENV if not os.environ.get(name)]


def _print_skip_banner(missing: list[str]) -> None:
    print("\n--- Tutorial 07: Oracle 26ai checkpointer ---")
    print(
        "Required environment variables not set; skipping the live demo so "
        "this file still runs cleanly in CI.\n"
    )
    print("Missing:")
    for name in missing:
        print(f"  - {name}")
    print(
        "\nProvision an Autonomous Database, drop its wallet under "
        "$ORACLE_WALLET, then set the variables above and re-run."
    )
    print("\nMinimal wiring (what the live path below builds):")
    print(
        """
    from locus.memory.backends import oracle_checkpointer

    cp = oracle_checkpointer(
        dsn=os.environ["ORACLE_DSN"],
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        wallet_location=os.environ["ORACLE_WALLET"],
        wallet_password=os.environ.get("ORACLE_WALLET_PASSWORD", ""),
        table_name="locus_checkpoints",
    )
    await cp.save(state, thread_id="my_thread")
    resumed = await cp.load("my_thread")
        """.rstrip()
    )


def _build_checkpointer():
    return oracle_checkpointer(
        dsn=os.environ["ORACLE_DSN"],
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        wallet_location=os.path.expanduser(os.environ["ORACLE_WALLET"]),
        wallet_password=os.environ.get("ORACLE_WALLET_PASSWORD", ""),
        table_name="locus_tutorial_07",
    )


async def first_run() -> None:
    """Session 1 — user starts a conversation; we persist it to 26ai."""
    print("\n--- Session 1: write the first turns to Oracle 26ai ---")
    cp = _build_checkpointer()

    state = AgentState(agent_id="tutorial_06")
    state = state.with_message(Message.system("You are a concise SRE assistant."))
    state = state.with_message(Message.user("p99 on checkout-api spiked at 14:02."))
    state = state.with_message(
        Message.assistant(
            "Pulling the checkout-api dashboard. Will compare against the "
            "previous 24h baseline and flag anything > 2σ."
        )
    )

    await cp.save(state, thread_id=THREAD_ID)
    print(f"Saved thread {THREAD_ID!r} with {len(state.messages)} messages.")
    print("Listing every persisted thread:")
    for tid in await cp.list_threads():
        print(f"  - {tid}")


async def second_run() -> None:
    """Session 2 — different process, same thread id; resume and append."""
    print("\n--- Session 2: load from Oracle 26ai and continue ---")
    cp = _build_checkpointer()

    resumed = await cp.load(THREAD_ID)
    print(f"Loaded {len(resumed.messages)} messages from {THREAD_ID!r}.")
    for m in resumed.messages:
        role = getattr(m, "role", "?")
        text = (getattr(m, "content", "") or "")[:80]
        print(f"  [{role}] {text}")

    resumed = resumed.with_message(Message.user("Anything similar in the last week?"))
    resumed = resumed.with_message(
        Message.assistant(
            "Two prior spikes in the past 14 days, both correlated with "
            "deploy windows. Sharing the trace links and the deploy IDs."
        )
    )

    await cp.save(resumed, thread_id=THREAD_ID)
    print(
        f"\nThread now persisted with {len(resumed.messages)} messages — "
        "durable across restarts, replicas, and operator handoffs."
    )


async def main() -> None:
    missing = _missing_env()
    if missing:
        _print_skip_banner(missing)
        return

    await first_run()
    await second_run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
