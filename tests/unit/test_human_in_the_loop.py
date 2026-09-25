"""Unit tests for human-in-the-loop provider.

Requirement: R-HITL-001 (event emission + validations cycle)
Target: src/to_tool_manager/provider/human_in_the_loop.py
"""

from __future__ import annotations

from typing import Any

import pytest

from to_tool_manager.provider.human_in_the_loop import (
    EventEmitter,
    HumanInTheLoop,
    HumanInputRetry,
)


class RecordingEmitter(EventEmitter):
    """Stub emitter that records emitted events."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def emit(self, event_id: str, payload: dict[str, Any]) -> None:
        self.events.append((event_id, payload))


class TestEventEmitter:
    """Tests for the abstract EventEmitter contract."""

    def test_cannot_instantiate_without_emit(self):
        """EventEmitter is abstract: instantiation must fail."""
        with pytest.raises(TypeError):
            EventEmitter()  # type: ignore[abstract]


class TestHumanInputRetry:
    """Tests for the retry exception."""

    def test_is_exception(self):
        """HumanInputRetry derives from Exception."""
        assert issubclass(HumanInputRetry, Exception)


class TestHumanInTheLoop:
    """Tests for the HITL coordinator."""

    async def test_execute_runs_async_logic_with_emit_and_event_fn(self):
        """Async logic receives emit_fn, event_fn and injected args."""
        emitter = RecordingEmitter()
        seen_emit: list[tuple[str, dict[str, Any]]] = []
        seen_event_fn_result: list[Any] = []

        async def logic(emit, event_fn, prefix, suffix):
            seen_emit.append(await _capture_emit(emit, "req", {"x": 1}))
            seen_event_fn_result.append(event_fn())

        hitl = HumanInTheLoop(emitter, logic, "P", "S")

        await hitl.execute(lambda: "TOOL_RESULT")

        assert seen_emit == [("req", {"x": 1})]
        assert seen_event_fn_result == ["TOOL_RESULT"]

    async def test_execute_runs_sync_logic(self):
        """Sync logic is invoked without awaiting it."""
        emitter = RecordingEmitter()
        calls: list[str] = []

        def logic(emit, event_fn):
            calls.append(event_fn())

        hitl = HumanInTheLoop(emitter, logic)

        await hitl.execute(lambda: "SYNC_OK")

        assert calls == ["SYNC_OK"]

    async def test_execute_binds_emitter_into_emit_fn(self):
        """The emit_fn exposed to logic calls the configured emitter."""
        emitter = RecordingEmitter()
        emitted: list[tuple[str, dict[str, Any]]] = []

        async def logic(emit, event_fn):
            await emit("event-123", {"tool": "order.create"})
            emitted.extend(emitter.events)

        hitl = HumanInTheLoop(emitter, logic)

        await hitl.execute(lambda: None)

        assert emitted == [("event-123", {"tool": "order.create"})]

    async def test_execute_propagates_human_input_retry(self):
        """HumanInputRetry raised by logic bubbles up to the caller."""
        emitter = RecordingEmitter()

        async def logic(emit, event_fn):
            raise HumanInputRetry()

        hitl = HumanInTheLoop(emitter, logic)

        with pytest.raises(HumanInputRetry):
            await hitl.execute(lambda: None)

    async def test_execute_passes_kwargs_to_logic(self):
        """Named arguments injected at construction reach the logic."""
        emitter = RecordingEmitter()
        captured: dict[str, Any] = {}

        async def logic(emit, event_fn, *, tool, user):
            captured["tool"] = tool
            captured["user"] = user

        hitl = HumanInTheLoop(emitter, logic, tool="order.create", user="u1")

        await hitl.execute(lambda: None)

        assert captured == {"tool": "order.create", "user": "u1"}


async def _capture_emit(
    emit, event_id: str, payload: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    await emit(event_id, payload)
    return event_id, payload