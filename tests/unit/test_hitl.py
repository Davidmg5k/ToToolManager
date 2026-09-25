"""Unit tests for HITL middlewares and shared dispatch.

Requirement: R-HITL-MW-001 (HITL middleware dispatch with retries)
Target: src/to_tool_manager/middleware/hitl.py
"""

from __future__ import annotations

import inspect
from typing import Any

from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
from to_tool_manager.middleware.hitl import (
    HumanInTheLoopMiddleware,
    HumanInTheLoopToolMiddleware,
    _build_event_func,
    run_hitl_dispatch,
)
from to_tool_manager.provider.human_in_the_loop import (
    EventEmitter,
    HumanInTheLoop,
    HumanInputRetry,
)


class RecordingEmitter(EventEmitter):
    """Stub emitter for tests."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def emit(self, event_id: str, payload: dict[str, Any]) -> None:
        self.events.append((event_id, payload))


def _make_failing_logic(fail_count: int):
    """Builds an async-def logic that fails N times, then passes.

    The contract requires an ``async def`` callable (a class with an
    async ``__call__`` is not detected by ``inspect.iscoroutinefunction``),
    so tests must supply a real coroutine function.
    """

    remaining = [fail_count]
    executed = []

    async def logic(emit, event_fn, *args, **kwargs):
        if remaining[0] > 0:
            remaining[0] -= 1
            raise HumanInputRetry()
        result = event_fn()
        if inspect.isawaitable(result):
            result = await result
        executed.append(result)

    logic.executed = executed  # type: ignore[attr-defined]
    return logic


def _make_hitl(logic, **kwargs) -> HumanInTheLoop:
    return HumanInTheLoop(RecordingEmitter(), logic, **kwargs)


class TestBuildEventFunc:
    """Tests for _build_event_func."""

    def test_wraps_func_with_kwargs(self):
        """event_fn calls func(**kwargs) and returns its result."""

        def tool(a, b):
            return a + b

        event_fn = _build_event_func(tool, {"a": 2, "b": 3})

        assert event_fn() == 5

    def test_wraps_different_kwargs(self):
        """event_fn binds its own kwargs, not the caller's."""

        def tool(name):
            return f"hi {name}"

        event_fn = _build_event_func(tool, {"name": "ana"})

        assert event_fn() == "hi ana"


class TestRunHitlDispatch:
    """Tests for the shared dispatch logic."""

    async def test_executes_tool_when_hitl_passes_first_attempt(self):
        """HITL passes immediately -> tool executes and returns result."""
        hitl = _make_hitl(_make_failing_logic(0))

        def tool(x):
            return f"value={x}"

        result = await run_hitl_dispatch(hitl, tool, 3, x=10)

        assert result == "value=10"

    async def test_retries_until_logic_passes(self):
        """Logic fails once, then succeeds -> tool still runs."""
        hitl = _make_hitl(_make_failing_logic(1))

        async def tool(x):
            return x * 2

        result = await run_hitl_dispatch(hitl, tool, 3, x=21)

        assert result == 42

    async def test_returns_error_message_when_retries_exhausted(self):
        """Logic keeps failing -> 'Maximum retries reached.' is returned."""
        hitl = _make_hitl(_make_failing_logic(99))

        result = await run_hitl_dispatch(hitl, lambda: "never", 3)

        assert result == "Maximum retries reached."

    async def test_forwards_args_to_final_call(self):
        """Positional args reach the final tool call, kwargs reach event_fn.

        Contract note: during HITL validation, ``event_fn`` receives only the
        keyword arguments (``func(**kw)``); positional ``*args`` are applied
        only on the final ``Middleware.call_func(func, *args, **kw)`` call.
        """
        hitl = _make_hitl(_make_failing_logic(0))

        def tool(*args, **kwargs):
            return args, kwargs

        result = await run_hitl_dispatch(hitl, tool, 2, 3, b=1)

        assert result == ((3,), {"b": 1})

    async def test_does_not_call_tool_when_retries_exhausted(self):
        """The tool must not execute once retries are exhausted."""
        logic = _make_failing_logic(99)
        hitl = _make_hitl(logic)

        def tool():
            raise AssertionError("tool must not run")

        result = await run_hitl_dispatch(hitl, tool, 2)

        assert result == "Maximum retries reached."
        assert logic.executed == []


class TestHumanInTheLoopMiddleware:
    """Tests for the global HITL middleware."""

    def test_is_a_middleware(self):
        """HumanInTheLoopMiddleware extends Middleware."""
        assert issubclass(HumanInTheLoopMiddleware, Middleware)

    async def test_dispatch_uses_configured_max_retries(self):
        """Defaults to 3 retries and executes the tool when valid."""
        hitl = _make_hitl(_make_failing_logic(2))
        mw = HumanInTheLoopMiddleware(hitl)

        def tool(name):
            return f"ok:{name}"

        result = await mw.dispatch(tool, name="chip")

        assert result == "ok:chip"

    async def test_dispatch_returns_error_when_retries_exhausted(self):
        """Exhausted retries yield the error message, no tool call."""
        hitl = _make_hitl(_make_failing_logic(99))
        mw = HumanInTheLoopMiddleware(hitl, max_retries=1)

        result = await mw.dispatch(lambda: "no")

        assert result == "Maximum retries reached."

    async def test_dispatch_custom_max_retries(self):
        """Custom max_retries is honored in the retry loop."""
        hitl = _make_hitl(_make_failing_logic(2))
        mw = HumanInTheLoopMiddleware(hitl, max_retries=2)

        result = await mw.dispatch(lambda: "no")

        assert result == "Maximum retries reached."


class TestHumanInTheLoopToolMiddleware:
    """Tests for the per-method HITL middleware."""

    def test_is_a_tool_middleware(self):
        """HumanInTheLoopToolMiddleware extends ToolMiddleware."""
        assert issubclass(HumanInTheLoopToolMiddleware, ToolMiddleware)

    def test_include_filters_methods(self):
        """ToolMiddleware filtering is preserved."""
        hitl = _make_hitl(_make_failing_logic(0))
        mw = HumanInTheLoopToolMiddleware(include=["create"], hitl=hitl)

        assert mw.is_allowed("create") is True
        assert mw.is_allowed("get") is False

    def test_exclude_filters_methods(self):
        """Exclude rules keep other methods allowed."""
        hitl = _make_hitl(_make_failing_logic(0))
        mw = HumanInTheLoopToolMiddleware(exclude=["delete"], hitl=hitl)

        assert mw.is_allowed("delete") is False
        assert mw.is_allowed("create") is True

    def test_signature_preserves_tool_middleware_positional_contract(self):
        """LSP: positional call valid for ToolMiddleware stays valid.

        ToolMiddleware.__init__(include, exclude) -> the override keeps
        include/exclude as the first positional parameters.
        """
        hitl = _make_hitl(_make_failing_logic(0))
        mw = HumanInTheLoopToolMiddleware(["create"], hitl=hitl)

        assert mw.is_allowed("create") is True
        assert mw.is_allowed("get") is False

    async def test_dispatch_executes_tool_when_valid(self):
        """With include filters, allowed tools run through HITL."""
        hitl = _make_hitl(_make_failing_logic(0))
        mw = HumanInTheLoopToolMiddleware(include=["run"], hitl=hitl)

        async def tool(*, a):
            return a + 1

        result = await mw.dispatch(tool, a=1)

        assert result == 2

    async def test_dispatch_returns_error_when_retries_exhausted(self):
        """Per-method middleware still returns the exhausted message."""
        hitl = _make_hitl(_make_failing_logic(99))
        mw = HumanInTheLoopToolMiddleware(hitl=hitl, max_retries=1)

        result = await mw.dispatch(lambda: "no")

        assert result == "Maximum retries reached."