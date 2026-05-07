# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Unit tests for locus.observability.bus_hook — EventBusHook."""

from __future__ import annotations

import asyncio

import pytest

from locus.core.state import AgentState
from locus.observability.bus_hook import EventBusHook
from locus.observability.context import set_run_id
from locus.observability.event_bus import StreamEvent, get_event_bus, reset_event_bus


@pytest.fixture(autouse=True)
def _reset():
    reset_event_bus()
    yield
    reset_event_bus()


def _make_state() -> AgentState:
    return AgentState()


class TestEventBusHook:
    def test_name(self) -> None:
        assert EventBusHook(run_id="r1").name == "EventBusHook"

    def test_priority_is_int(self) -> None:
        assert isinstance(EventBusHook(run_id="r1").priority, int)

    @pytest.mark.asyncio
    async def test_before_invocation_emits_started_event(self) -> None:
        rid = "hook-test-1"
        set_run_id(rid)
        hook = EventBusHook(run_id=rid)
        bus = get_event_bus()
        events: list[StreamEvent] = []

        async def collect():
            async for ev in bus.subscribe(rid):
                events.append(ev)
                return  # first event is enough

        task = asyncio.create_task(collect())
        await asyncio.sleep(0)
        state = _make_state()
        await hook.on_before_invocation("test prompt", state)
        await asyncio.wait_for(task, timeout=2.0)

        assert len(events) >= 1
        assert any("invocation" in e.event_type for e in events)

    @pytest.mark.asyncio
    async def test_after_invocation_emits_completed_event(self) -> None:
        rid = "hook-test-2"
        set_run_id(rid)
        hook = EventBusHook(run_id=rid)
        bus = get_event_bus()
        events: list[StreamEvent] = []

        async def collect():
            async for ev in bus.subscribe(rid):
                events.append(ev)
                return

        task = asyncio.create_task(collect())
        await asyncio.sleep(0)
        state = _make_state()
        await hook.on_after_invocation(state, success=True)
        await asyncio.wait_for(task, timeout=2.0)

        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_events_carry_correct_run_id(self) -> None:
        rid = "hook-run-id-check"
        set_run_id(rid)
        hook = EventBusHook(run_id=rid)
        bus = get_event_bus()
        events: list[StreamEvent] = []

        async def collect():
            async for ev in bus.subscribe(rid):
                events.append(ev)
                return

        task = asyncio.create_task(collect())
        await asyncio.sleep(0)
        await hook.on_before_invocation("p", _make_state())
        await asyncio.wait_for(task, timeout=2.0)

        assert all(e.run_id == rid for e in events)

    @pytest.mark.asyncio
    async def test_iteration_start_emits_event(self) -> None:
        rid = "hook-iter"
        set_run_id(rid)
        hook = EventBusHook(run_id=rid)
        bus = get_event_bus()
        events: list[StreamEvent] = []

        async def collect():
            async for ev in bus.subscribe(rid):
                events.append(ev)
                return

        task = asyncio.create_task(collect())
        await asyncio.sleep(0)
        await hook.on_iteration_start(1, _make_state())
        await asyncio.wait_for(task, timeout=2.0)

        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_no_crash_without_subscriber(self) -> None:
        hook = EventBusHook(run_id="no-sub")
        # Should not raise even with no subscriber
        await hook.on_before_invocation("prompt", _make_state())
        await hook.on_after_invocation(_make_state(), success=True)
