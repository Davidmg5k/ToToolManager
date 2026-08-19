import asyncio

import pytest

from to_tool_manager.core.service import Service
from to_tool_manager.orchestrator import ToToolManager
from to_tool_manager.resilience import TimeoutMiddleware


class SlowService:
    def fast(self) -> str:
        """Returns immediately."""
        return "ok"

    async def slow(self, delay: float) -> str:
        """Sleeps for `delay` seconds before returning."""
        await asyncio.sleep(delay)
        return "finished"


class TestTimeoutMiddlewareConstruction:
    def test_rejects_non_positive_seconds(self):
        with pytest.raises(ValueError):
            TimeoutMiddleware(seconds=0)
        with pytest.raises(ValueError):
            TimeoutMiddleware(seconds=-1.0)

    def test_seconds_property(self):
        mw = TimeoutMiddleware(seconds=5.0)
        assert mw.seconds == 5.0


class TestTimeoutMiddlewareIsOptIn:
    """A manager built WITHOUT TimeoutMiddleware must behave identically
    to before this middleware existed -- a slow call just runs to
    completion, uninterrupted."""

    @pytest.mark.anyio
    async def test_manager_without_timeout_middleware_unaffected(self):
        svc = Service(name="Slow", service=SlowService)
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "slow", "args": {"delay": 0.01}}])

        assert result.ok is True
        assert result.content[0]["result"] == "finished"


class TestTimeoutMiddlewareEndToEnd:
    @pytest.mark.anyio
    async def test_fast_call_within_timeout_succeeds_normally(self):
        svc = Service(name="Slow", service=SlowService, middlewares=[TimeoutMiddleware(seconds=1.0)])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "fast", "args": {}}])

        assert result.ok is True
        assert result.content[0]["result"] == "ok"

    @pytest.mark.anyio
    async def test_slow_call_exceeding_timeout_returns_timeout_error(self):
        """The call must actually be cancelled and time out -- not raise
        an unhandled exception, and not hang past the deadline."""
        svc = Service(name="Slow", service=SlowService, middlewares=[TimeoutMiddleware(seconds=0.05)])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await asyncio.wait_for(
            spec.call(operations=[{"method": "slow", "args": {"delay": 5.0}}]),
            timeout=2.0,  # test-level safety net; the middleware itself should return well before this
        )

        assert result.ok is False
        assert result.error is not None
        assert "timeout" in result.error.category
        assert result.error.retryable is True

    @pytest.mark.anyio
    async def test_timeout_does_not_raise_to_caller(self):
        """A raised TimeoutError/CancelledError reaching the agent
        framework as an unhandled exception would be a regression --
        confirms the middleware always returns a ToolResponse, never
        propagates the cancellation."""
        svc = Service(name="Slow", service=SlowService, middlewares=[TimeoutMiddleware(seconds=0.05)])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        try:
            result = await asyncio.wait_for(
                spec.call(operations=[{"method": "slow", "args": {"delay": 5.0}}]),
                timeout=2.0,
            )
        except (TimeoutError, asyncio.CancelledError):
            pytest.fail("TimeoutMiddleware must not let the timeout propagate as a raised exception")

        assert result.ok is False
