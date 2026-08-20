import pytest

from to_tool_manager.core.service import Service
from to_tool_manager.core.types import ToolError, ToolResponse
from to_tool_manager.orchestrator import ToToolManager
from to_tool_manager.resilience import CircuitBreakerMiddleware, CircuitState
from to_tool_manager.security.middleware import Middleware


class DummyService:
    def greet(self, name: str) -> str:
        """Greet a user by name."""
        return f"Hello, {name}!"


class AlwaysFailsMiddleware(Middleware):
    """Fails every call with a non-ok ToolResponse -- stands in for a
    genuinely broken downstream dependency."""

    def __init__(self):
        super().__init__()
        self.call_count = 0

    async def dispatch(self, func, /, *args, **kw):
        self.call_count += 1
        return ToolResponse(
            error=ToolError(
                category=frozenset({"downstream_error"}),
                message="downstream is down",
                exception_type="RuntimeError",
                retryable=False,
            )
        )


class RaisingMiddleware(Middleware):
    def __init__(self):
        super().__init__()
        self.call_count = 0

    async def dispatch(self, func, /, *args, **kw):
        self.call_count += 1
        raise RuntimeError("boom")


class ManualFakeClock:
    """Injectable clock for deterministic OPEN -> HALF_OPEN transition
    testing, without waiting real time.monotonic() seconds."""

    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestCircuitBreakerConstruction:
    def test_rejects_invalid_failure_threshold(self):
        with pytest.raises(ValueError):
            CircuitBreakerMiddleware(failure_threshold=0)

    def test_rejects_invalid_reset_timeout(self):
        with pytest.raises(ValueError):
            CircuitBreakerMiddleware(reset_timeout=0)
        with pytest.raises(ValueError):
            CircuitBreakerMiddleware(reset_timeout=-1)

    def test_starts_closed(self):
        breaker = CircuitBreakerMiddleware()
        assert breaker.state is CircuitState.CLOSED


class TestCircuitBreakerIsOptIn:
    @pytest.mark.anyio
    async def test_manager_without_circuit_breaker_unaffected(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is True


class TestCircuitBreakerEndToEnd:
    @pytest.mark.anyio
    async def test_successful_calls_keep_circuit_closed(self):
        breaker = CircuitBreakerMiddleware(failure_threshold=3)
        svc = Service(name="Dummy", service=DummyService, middlewares=[breaker])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        for _ in range(5):
            result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])
            assert result.ok is True

        assert breaker.state is CircuitState.CLOSED

    @pytest.mark.anyio
    async def test_trips_open_after_failure_threshold(self):
        clock = ManualFakeClock()
        breaker = CircuitBreakerMiddleware(failure_threshold=3, _clock=clock)
        failing = AlwaysFailsMiddleware()
        svc = Service(name="Dummy", service=DummyService, middlewares=[breaker, failing])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        for _ in range(3):
            result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])
            assert result.ok is False

        assert breaker.state is CircuitState.OPEN
        assert failing.call_count == 3

    @pytest.mark.anyio
    async def test_open_circuit_rejects_calls_without_reaching_downstream(self):
        """Core behavior: once OPEN, calls must be rejected immediately
        -- the wrapped function/middleware chain must NOT be invoked at
        all until the reset timeout elapses."""
        clock = ManualFakeClock()
        breaker = CircuitBreakerMiddleware(failure_threshold=2, reset_timeout=60.0, _clock=clock)
        failing = AlwaysFailsMiddleware()
        svc = Service(name="Dummy", service=DummyService, middlewares=[breaker, failing])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        for _ in range(2):
            await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])
        assert breaker.state is CircuitState.OPEN
        assert failing.call_count == 2

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is False
        assert "circuit_open" in result.error.category
        assert result.error.retryable is True
        assert failing.call_count == 2  # unchanged -- the rejected call never reached `failing`

    @pytest.mark.anyio
    async def test_transitions_to_half_open_after_reset_timeout_and_recovers_on_success(self):
        clock = ManualFakeClock()
        breaker = CircuitBreakerMiddleware(failure_threshold=2, reset_timeout=10.0, _clock=clock)
        failing = AlwaysFailsMiddleware()
        svc = Service(name="Dummy", service=DummyService, middlewares=[breaker, failing])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        for _ in range(2):
            await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])
        assert breaker.state is CircuitState.OPEN

        clock.advance(10.0)
        assert breaker.state is CircuitState.HALF_OPEN

        # The probe call succeeds (downstream recovered) -- remove the
        # failing middleware's effect by swapping to a real dispatch:
        # simplest is to build a fresh manager with only the breaker,
        # simulating "downstream is healthy again".
        healthy_svc = Service(name="Dummy", service=DummyService, middlewares=[breaker])
        healthy_manager = ToToolManager([healthy_svc])
        healthy_spec = healthy_manager.tool_specs[0]

        result = await healthy_spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is True
        assert breaker.state is CircuitState.CLOSED

    @pytest.mark.anyio
    async def test_half_open_probe_failure_reopens_circuit(self):
        clock = ManualFakeClock()
        breaker = CircuitBreakerMiddleware(failure_threshold=2, reset_timeout=10.0, _clock=clock)
        failing = AlwaysFailsMiddleware()
        svc = Service(name="Dummy", service=DummyService, middlewares=[breaker, failing])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        for _ in range(2):
            await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])
        assert breaker.state is CircuitState.OPEN

        clock.advance(10.0)
        assert breaker.state is CircuitState.HALF_OPEN

        # Downstream still broken -- the probe call fails too.
        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is False
        assert breaker.state is CircuitState.OPEN
        assert failing.call_count == 3  # the 2 that tripped it + 1 probe

    @pytest.mark.anyio
    async def test_raised_exception_counts_as_failure_and_still_propagates(self):
        clock = ManualFakeClock()
        breaker = CircuitBreakerMiddleware(failure_threshold=2, _clock=clock)
        raiser = RaisingMiddleware()
        svc = Service(name="Dummy", service=DummyService, middlewares=[breaker, raiser])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert breaker.state is CircuitState.OPEN
