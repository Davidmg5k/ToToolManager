import pytest

from to_tool_manager.core.service import Service
from to_tool_manager.core.types import ToolError, ToolResponse
from to_tool_manager.orchestrator import ToToolManager
from to_tool_manager.resilience import RetryMiddleware
from to_tool_manager.security.middleware import Middleware


class DummyService:
    def greet(self, name: str) -> str:
        """Greet a user by name."""
        return f"Hello, {name}!"


class FlakyMiddleware(Middleware):
    """Fails with a retryable error the first N calls, then succeeds --
    stands in for a transient downstream failure (e.g. a flaky
    network call) a real RetryMiddleware would be protecting against."""

    def __init__(self, fail_times: int, retryable: bool = True):
        super().__init__()
        self.fail_times = fail_times
        self.retryable = retryable
        self.call_count = 0

    async def dispatch(self, func, /, *args, **kw):
        self.call_count += 1
        if self.call_count <= self.fail_times:
            return ToolResponse(
                error=ToolError(
                    category=frozenset({"transient"}),
                    message="transient failure",
                    exception_type="RuntimeError",
                    retryable=self.retryable,
                )
            )
        return await func(*args, **kw)


class RaisingMiddleware(Middleware):
    def __init__(self, fail_times: int, exc_type=RuntimeError):
        super().__init__()
        self.fail_times = fail_times
        self.exc_type = exc_type
        self.call_count = 0

    async def dispatch(self, func, /, *args, **kw):
        self.call_count += 1
        if self.call_count <= self.fail_times:
            raise self.exc_type("transient")
        return await func(*args, **kw)


async def _no_op_sleep(_seconds: float) -> None:
    """Replaces real backoff delays in tests so they run instantly."""


class TestRetryMiddlewareConstruction:
    def test_rejects_invalid_max_attempts(self):
        with pytest.raises(ValueError):
            RetryMiddleware(max_attempts=0)

    def test_rejects_negative_delays(self):
        with pytest.raises(ValueError):
            RetryMiddleware(base_delay=-1)
        with pytest.raises(ValueError):
            RetryMiddleware(max_delay=-1)

    def test_rejects_jitter_out_of_range(self):
        with pytest.raises(ValueError):
            RetryMiddleware(jitter=1.5)
        with pytest.raises(ValueError):
            RetryMiddleware(jitter=-0.1)


class TestRetryMiddlewareIsOptIn:
    @pytest.mark.anyio
    async def test_manager_without_retry_middleware_unaffected(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is True


class TestRetryMiddlewareEndToEnd:
    @pytest.mark.anyio
    async def test_succeeds_immediately_when_no_failure(self):
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[RetryMiddleware(max_attempts=3, _sleep=_no_op_sleep)],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is True
        assert result.content[0]["result"] == "Hello, World!"

    @pytest.mark.anyio
    async def test_retries_retryable_failure_until_success(self):
        flaky = FlakyMiddleware(fail_times=2, retryable=True)
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[RetryMiddleware(max_attempts=3, _sleep=_no_op_sleep), flaky],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is True
        assert flaky.call_count == 3  # 2 failures + 1 success, within max_attempts

    @pytest.mark.anyio
    async def test_gives_up_after_max_attempts_and_returns_last_error(self):
        flaky = FlakyMiddleware(fail_times=10, retryable=True)
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[RetryMiddleware(max_attempts=3, _sleep=_no_op_sleep), flaky],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is False
        assert flaky.call_count == 3  # exactly max_attempts, no more

    @pytest.mark.anyio
    async def test_does_not_retry_non_retryable_failure(self):
        flaky = FlakyMiddleware(fail_times=10, retryable=False)
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[RetryMiddleware(max_attempts=5, _sleep=_no_op_sleep), flaky],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is False
        assert flaky.call_count == 1  # no retries -- retryable=False must stop immediately

    @pytest.mark.anyio
    async def test_does_not_retry_raised_exception_by_default(self):
        """Core design decision under test: a raised exception (not a
        retryable ToolResponse) must propagate immediately by default,
        not be silently retried."""
        raiser = RaisingMiddleware(fail_times=10)
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[RetryMiddleware(max_attempts=5, _sleep=_no_op_sleep), raiser],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        with pytest.raises(RuntimeError):
            await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert raiser.call_count == 1  # no retries on raised exceptions by default

    @pytest.mark.anyio
    async def test_retry_on_exceptions_opts_into_retrying_raised_exceptions(self):
        raiser = RaisingMiddleware(fail_times=2, exc_type=ConnectionError)
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[
                RetryMiddleware(max_attempts=3, retry_on_exceptions=(ConnectionError,), _sleep=_no_op_sleep),
                raiser,
            ],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is True
        assert raiser.call_count == 3

    @pytest.mark.anyio
    async def test_retry_on_exceptions_does_not_catch_unlisted_exception_types(self):
        raiser = RaisingMiddleware(fail_times=10, exc_type=PermissionError)
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[
                RetryMiddleware(max_attempts=5, retry_on_exceptions=(ConnectionError,), _sleep=_no_op_sleep),
                raiser,
            ],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        with pytest.raises(PermissionError):
            await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert raiser.call_count == 1


class TestRetryMiddlewareBackoffTiming:
    @pytest.mark.anyio
    async def test_sleeps_between_attempts_with_increasing_delay(self):
        sleeps: list[float] = []

        async def recording_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        flaky = FlakyMiddleware(fail_times=10, retryable=True)
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[
                RetryMiddleware(max_attempts=3, base_delay=1.0, jitter=0.0, _sleep=recording_sleep),
                flaky,
            ],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        # max_attempts=3 -> 2 sleeps (between attempt 1->2 and 2->3), no
        # sleep after the final attempt.
        assert sleeps == [1.0, 2.0]

    @pytest.mark.anyio
    async def test_delay_is_capped_at_max_delay(self):
        sleeps: list[float] = []

        async def recording_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        flaky = FlakyMiddleware(fail_times=10, retryable=True)
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[
                RetryMiddleware(max_attempts=4, base_delay=10.0, max_delay=15.0, jitter=0.0, _sleep=recording_sleep),
                flaky,
            ],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert sleeps == [10.0, 15.0, 15.0]  # 20.0 and 40.0 would exceed max_delay, capped to 15.0
