# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Per-event-loop ``oracledb`` async pool cache.

``oracledb`` async pools are bound to the asyncio event loop that
creates them. The moment a caller invokes :meth:`Agent.run_sync` a
second time (each call spins a fresh loop via :func:`asyncio.run`),
or FastAPI's lifespan / anyio's BlockingPortal opens a different
loop, the cached pool is attached to a dead loop and the next
``acquire`` raises::

    RuntimeError: Task ... got Future attached to a different loop

The fix is to detect a loop mismatch and rebuild. This helper does
that for every Oracle-touching backend in locus so the per-class
copies stay one line.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Protocol


class _PoolHolder(Protocol):
    """Duck-typed surface every Oracle backend already exposes.

    ``_pool`` is the cached pool; ``_pool_loop`` is the event loop it
    was created on. Backends declare these as instance attributes (or
    Pydantic private attrs) and call :func:`get_pool` to read /
    refresh.
    """

    _pool: Any
    _pool_loop: Any


async def get_pool(
    holder: _PoolHolder,
    builder: Callable[[], Any] | Callable[[], Awaitable[Any]],
) -> Any:
    """Return a pool bound to the current event loop, building if needed.

    Args:
        holder: any object with mutable ``_pool`` / ``_pool_loop``
            attributes. Most locus backends already satisfy this.
        builder: zero-arg callable that produces a fresh
            ``oracledb`` async pool. May be sync (the common case —
            ``oracledb.create_pool_async`` returns the pool directly,
            not a coroutine) or async.

    The cached pool is invalidated when the running loop changes;
    the dropped pool is left for ``oracledb`` to GC.
    """
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:  # pragma: no cover — backend methods are async
        running = None

    if holder._pool is not None and holder._pool_loop is not running:
        # Cross-loop call — drop the dead reference, reinitialise table
        # provisioning state, and rebuild below.
        holder._pool = None
        # ``_initialized`` is a sibling flag on most backends that gates
        # CREATE TABLE checks; reset it so the new pool re-verifies
        # against the database.
        if hasattr(holder, "_initialized"):
            holder._initialized = False  # type: ignore[attr-defined]

    if holder._pool is None:
        pool = builder()
        if asyncio.iscoroutine(pool):
            pool = await pool
        holder._pool = pool
        holder._pool_loop = running

    return holder._pool
