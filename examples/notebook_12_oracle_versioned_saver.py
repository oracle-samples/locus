#!/usr/bin/env python3
# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Notebook 12: versioned checkpoint history on Oracle Database 26ai.

Notebook 07's ``oracle_checkpointer`` keeps **one row per thread** —
``MERGE`` on save means the latest write wins and history is destructive.
That's the right shape for most agent threads. But when you need a
LangGraph-shape *history-preserving* saver — one row per
``(thread_id, checkpoint_ns, checkpoint_id)`` plus a sibling table for
intra-step pending writes — reach for :class:`OracleCheckpointSaver`.

It is the locus-native equivalent of ``langgraph-oracledb``'s
``OracleSaver`` / ``AsyncOracleSaver`` — same two-table schema, same
method surface — but with **zero** langchain / langgraph imports. The
same Autonomous Database wallet drives both this saver and the
single-row ``oracle_checkpointer`` side-by-side, so you can mix and
match per workload.

Key concepts:

- Two physical tables: ``<table>_checkpoints`` (one row per
  ``(thread_id, checkpoint_ns, checkpoint_id)`` with ``parent_checkpoint_id``
  walking the lineage) and ``<table>_writes`` (pending intra-step writes
  keyed by ``task_id`` + monotonic ``idx``).
- ``put(...)`` inserts; never upserts. Re-saving a different
  ``checkpoint_id`` for the same thread *appends* — that's the whole
  point of the versioned shape.
- ``get(thread_id=...)`` with no ``checkpoint_id`` returns the newest
  row; ``list_checkpoints(...)`` enumerates the lineage newest-first.
- ``put_writes(...)`` is idempotent: it replaces any prior writes for
  the same ``(thread, ns, checkpoint, task)`` tuple, so retries are
  safe.

Run it::

    export ORACLE_DSN=mydb_low                   # tnsnames alias
    export ORACLE_USER=locus_app                 # least-privileged app schema
    export ORACLE_PASSWORD='<app-password>'
    export ORACLE_WALLET=~/.oci/wallets/mydb
    export ORACLE_WALLET_PASSWORD='<wallet-pw>'  # if encrypted

    python examples/notebook_12_oracle_versioned_saver.py

If those env vars aren't set the tutorial prints the wiring snippet and
exits cleanly — no traceback, no half-initialised state.

Difficulty: Intermediate. Self-contained — no prior tutorial required.
"""

from __future__ import annotations

import asyncio
import os
import sys

from locus.memory.backends import OracleCheckpointSaver


_REQUIRED_ENV = (
    "ORACLE_DSN",
    "ORACLE_USER",
    "ORACLE_PASSWORD",
    "ORACLE_WALLET",
)

# Single base prefix — the saver derives _checkpoints and _writes from
# it. Drop both at the end of the demo so the notebook is re-runnable.
TABLE_PREFIX = "locus_notebook_12"
THREAD_ID = "t1"


def _missing_env() -> list[str]:
    return [name for name in _REQUIRED_ENV if not os.environ.get(name)]


def _print_skip_banner(missing: list[str]) -> None:
    print("\n--- Notebook 12: OracleCheckpointSaver (versioned history) ---")
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
    from locus.memory.backends import OracleCheckpointSaver

    saver = OracleCheckpointSaver(
        dsn=os.environ["ORACLE_DSN"],
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        wallet_location=os.environ["ORACLE_WALLET"],
        wallet_password=os.environ.get("ORACLE_WALLET_PASSWORD", ""),
        table_name="locus_notebook_12",   # creates _checkpoints + _writes
    )
    await saver.put(thread_id="t1", checkpoint_id="v1",
                    checkpoint_data={"step": 1})
    await saver.put(thread_id="t1", checkpoint_id="v2",
                    parent_checkpoint_id="v1",
                    checkpoint_data={"step": 2})
    latest = await saver.get(thread_id="t1")
        """.rstrip()
    )


def _build_saver() -> OracleCheckpointSaver:
    return OracleCheckpointSaver(
        dsn=os.environ["ORACLE_DSN"],
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        wallet_location=os.path.expanduser(os.environ["ORACLE_WALLET"]),
        wallet_password=os.environ.get("ORACLE_WALLET_PASSWORD", ""),
        table_name=TABLE_PREFIX,
    )


async def _drop_tables(saver: OracleCheckpointSaver) -> None:
    """Drop both demo tables so the notebook is re-runnable."""
    pool = await saver._get_pool()  # noqa: SLF001 — cleanup helper, not public API
    async with pool.acquire() as conn, conn.cursor() as cursor:
        for table in (f"{TABLE_PREFIX}_writes", f"{TABLE_PREFIX}_checkpoints"):
            try:
                await cursor.execute(f"DROP TABLE {table} PURGE")
            except Exception as exc:  # pragma: no cover — cleanup is best-effort
                print(f"  (cleanup) DROP TABLE {table} skipped: {exc}")
        await conn.commit()


async def append_checkpoints(saver: OracleCheckpointSaver) -> None:
    """Write two checkpoints with a parent lineage v1 -> v2."""
    print("\n--- 1. Append two checkpoints with parent lineage ---")
    await saver.put(
        thread_id=THREAD_ID,
        checkpoint_id="v1",
        checkpoint_data={"step": 1, "note": "first"},
    )
    await saver.put(
        thread_id=THREAD_ID,
        checkpoint_id="v2",
        parent_checkpoint_id="v1",
        checkpoint_data={"step": 2, "note": "second"},
    )
    print(f"  put v1 (no parent), v2 (parent=v1) on thread {THREAD_ID!r}")
    print(
        "\n  Both rows live in <prefix>_checkpoints; the latest write does "
        "NOT overwrite v1. That's what 'history-preserving' means."
    )


async def write_pending(saver: OracleCheckpointSaver) -> None:
    """Stash pending channel writes against the v2 checkpoint."""
    print("\n--- 2. put_writes: intra-step durability ---")
    await saver.put_writes(
        thread_id=THREAD_ID,
        checkpoint_id="v2",
        task_id="node-a",
        writes=[("channel-x", "pending-1"), ("channel-y", "pending-2")],
    )
    print("  Saved 2 pending writes for (thread=t1, checkpoint=v2, task=node-a).")
    print(
        "\n  put_writes is idempotent — a retry for the same "
        "(thread, ns, checkpoint, task) replaces the prior set; "
        "the saver deletes-then-inserts in one transaction."
    )


async def read_back(saver: OracleCheckpointSaver) -> None:
    """Show the three read paths: latest, history, pending writes."""
    print("\n--- 3. Read back: latest / history / pending writes ---")

    latest = await saver.get(thread_id=THREAD_ID)
    assert latest is not None
    print(f"  get(thread_id={THREAD_ID!r})  -> checkpoint_id={latest['checkpoint_id']!r}")
    print(f"      parent={latest['parent_checkpoint_id']!r}")
    print(f"      checkpoint={latest['checkpoint']!r}")

    history = await saver.list_checkpoints(thread_id=THREAD_ID)
    print(f"\n  list_checkpoints(thread_id={THREAD_ID!r}) -> {len(history)} rows (newest first):")
    for row in history:
        print(f"      - id={row['checkpoint_id']!r}  parent={row['parent_checkpoint_id']!r}")

    writes = await saver.get_writes(thread_id=THREAD_ID, checkpoint_id="v2")
    print(f"\n  get_writes(thread=t1, checkpoint=v2) -> {len(writes)} pending writes:")
    for w in writes:
        print(
            f"      - task={w['task_id']!r} idx={w['idx']} channel={w['channel']!r} value={w['value']!r}"
        )


async def main() -> None:
    missing = _missing_env()
    if missing:
        _print_skip_banner(missing)
        return

    print("Opening pool against Oracle 26ai…")
    saver = _build_saver()
    try:
        await append_checkpoints(saver)
        await write_pending(saver)
        await read_back(saver)
        print(
            "\n--- 4. delete_thread cascades both tables ---"
            f"\n  delete_thread({THREAD_ID!r}) — removes every checkpoint "
            "AND every pending write for the thread, in one transaction."
        )
        await saver.delete_thread(THREAD_ID)
        print(
            "\nReach for OracleCheckpointSaver when you want LangGraph-shape "
            "history-preserving checkpoints. The single-row "
            "oracle_checkpointer in notebook 07 shares the same connection "
            "envelope and can coexist on the same Autonomous Database."
        )
    finally:
        print("\n--- Cleanup: drop the demo tables ---")
        await _drop_tables(saver)
        await saver.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
