import logging

import pytest

from to_tool_manager.core.service import Service
from to_tool_manager.observability import LoggingMiddleware
from to_tool_manager.orchestrator import ToToolManager


class DummyService:
    def greet(self, name: str) -> str:
        """Greet a user by name."""
        return f"Hello, {name}!"

    def boom(self) -> str:
        """Always raises."""
        raise ValueError("kaboom")


class TestLoggingMiddlewareIsOptIn:
    """A manager built WITHOUT LoggingMiddleware must behave identically
    to before this middleware existed -- confirms it's genuinely opt-in,
    not wired in by default anywhere."""

    @pytest.mark.anyio
    async def test_manager_without_logging_middleware_unaffected(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is True
        assert result.content[0]["result"] == "Hello, World!"


class TestLoggingMiddlewareEndToEnd:
    """Real ToToolManager + Service + Middleware chain (matching
    tests/core/test_manager.py::TestToToolManagerDispatch's pattern) --
    no mocks of the dispatch pipeline itself, only of the logger to
    inspect what got logged."""

    @pytest.mark.anyio
    async def test_successful_call_is_not_swallowed_and_logs_info(self, caplog):
        logger = logging.getLogger("test.to_tool_manager.dispatch")
        svc = Service(name="Dummy", service=DummyService, middlewares=[LoggingMiddleware(logger=logger)])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        with caplog.at_level(logging.INFO, logger="test.to_tool_manager.dispatch"):
            result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        # The middleware must not change the actual result.
        assert result.ok is True
        assert result.content[0]["result"] == "Hello, World!"

        records = [r for r in caplog.records if r.name == "test.to_tool_manager.dispatch"]
        assert len(records) == 1
        assert records[0].levelno == logging.INFO
        assert getattr(records[0], "to_tool_manager.operation_count") == 1
        assert getattr(records[0], "to_tool_manager.success_count") == 1
        assert getattr(records[0], "to_tool_manager.failure_count") == 0

    @pytest.mark.anyio
    async def test_per_operation_failure_logs_at_warning(self, caplog):
        logger = logging.getLogger("test.to_tool_manager.dispatch")
        svc = Service(name="Dummy", service=DummyService, middlewares=[LoggingMiddleware(logger=logger)])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        with caplog.at_level(logging.INFO, logger="test.to_tool_manager.dispatch"):
            result = await spec.call(operations=[{"method": "boom", "args": {}}])

        # A per-operation error is still a "successful" batch call at the
        # ToolResponse level (result.ok) -- the manager's own error
        # handling already turned the exception into a per-op error
        # entry, it never reached the middleware as a raised exception.
        assert result.ok is True
        assert result.content[0]["success"] is False

        records = [r for r in caplog.records if r.name == "test.to_tool_manager.dispatch"]
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING

    @pytest.mark.anyio
    async def test_structural_failure_still_logged_and_not_swallowed(self, caplog):
        """An empty `operations` list is a structural failure
        (`response.error` set) rather than a per-operation one -- must
        still surface via the ToolResponse unchanged, and log at
        WARNING, not silently."""
        logger = logging.getLogger("test.to_tool_manager.dispatch")
        svc = Service(name="Dummy", service=DummyService, middlewares=[LoggingMiddleware(logger=logger)])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        with caplog.at_level(logging.INFO, logger="test.to_tool_manager.dispatch"):
            result = await spec.call(operations=[])

        assert result.ok is False

        records = [r for r in caplog.records if r.name == "test.to_tool_manager.dispatch"]
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING

    @pytest.mark.anyio
    async def test_default_logger_used_when_none_given(self):
        """Just confirms construction and dispatch work with the
        default module logger (no explicit `logger=` kwarg) -- the
        common case."""
        svc = Service(name="Dummy", service=DummyService, middlewares=[LoggingMiddleware()])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "Ada"}}])

        assert result.ok is True
        assert result.content[0]["result"] == "Hello, Ada!"
