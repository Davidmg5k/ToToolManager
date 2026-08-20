import pytest

from to_tool_manager.core.service import Service
from to_tool_manager.observability import InMemoryMetricsCollector, MetricsMiddleware
from to_tool_manager.orchestrator import ToToolManager

from tests.concurrency_harness import run_concurrently_threads


class DummyService:
    def greet(self, name: str) -> str:
        """Greet a user by name."""
        return f"Hello, {name}!"

    def boom(self) -> str:
        """Always raises."""
        raise ValueError("kaboom")


class TestInMemoryMetricsCollector:
    def test_record_duration_and_get_durations(self):
        collector = InMemoryMetricsCollector()
        collector.record_duration("latency", 0.1, {"service": "A"})
        collector.record_duration("latency", 0.2, {"service": "A"})

        assert collector.get_durations("latency", {"service": "A"}) == [0.1, 0.2]

    def test_get_durations_without_tags_aggregates_across_tag_combinations(self):
        collector = InMemoryMetricsCollector()
        collector.record_duration("latency", 0.1, {"service": "A"})
        collector.record_duration("latency", 0.2, {"service": "B"})

        assert sorted(collector.get_durations("latency")) == [0.1, 0.2]

    def test_increment_and_get_count(self):
        collector = InMemoryMetricsCollector()
        collector.increment("calls", {"outcome": "success"})
        collector.increment("calls", {"outcome": "success"}, value=2)
        collector.increment("calls", {"outcome": "error"})

        assert collector.get_count("calls", {"outcome": "success"}) == 3
        assert collector.get_count("calls", {"outcome": "error"}) == 1
        assert collector.get_count("calls") == 4

    def test_thread_safety_under_concurrent_increments(self):
        collector = InMemoryMetricsCollector()

        def bump(_i: int) -> None:
            collector.increment("calls", {"outcome": "success"})

        results = run_concurrently_threads(bump, n=200)
        assert results.ok, f"unexpected errors: {results.errors}"
        assert collector.get_count("calls", {"outcome": "success"}) == 200


class TestMetricsMiddlewareIsOptIn:
    @pytest.mark.anyio
    async def test_manager_without_metrics_middleware_unaffected(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is True
        assert result.content[0]["result"] == "Hello, World!"


class TestMetricsMiddlewareEndToEnd:
    @pytest.mark.anyio
    async def test_successful_call_records_duration_and_success_counter(self):
        collector = InMemoryMetricsCollector()
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[MetricsMiddleware(collector, service_name="Dummy")],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is True
        durations = collector.get_durations(
            "to_tool_manager.dispatch.duration_seconds", {"service": "Dummy", "outcome": "success"}
        )
        assert len(durations) == 1
        assert durations[0] >= 0
        assert (
            collector.get_count(
                "to_tool_manager.dispatch.calls_total", {"service": "Dummy", "outcome": "success"}
            )
            == 1
        )

    @pytest.mark.anyio
    async def test_per_operation_failure_still_counts_as_success_at_dispatch_level(self):
        """A per-operation exception is caught by the manager itself and
        turned into a per-op error entry -- the dispatch_call as a whole
        still returns ToolResponse(ok=True) with that entry marked
        failed, so the middleware records it under outcome="success"
        (the dispatch didn't raise/fail structurally). This mirrors
        LoggingMiddleware's per-operation-vs-structural distinction."""
        collector = InMemoryMetricsCollector()
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[MetricsMiddleware(collector, service_name="Dummy")],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "boom", "args": {}}])

        assert result.ok is True
        assert result.content[0]["success"] is False
        assert (
            collector.get_count(
                "to_tool_manager.dispatch.calls_total", {"service": "Dummy", "outcome": "success"}
            )
            == 1
        )

    @pytest.mark.anyio
    async def test_structural_failure_counts_as_error(self):
        collector = InMemoryMetricsCollector()
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[MetricsMiddleware(collector, service_name="Dummy")],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[])

        assert result.ok is False
        assert (
            collector.get_count(
                "to_tool_manager.dispatch.calls_total", {"service": "Dummy", "outcome": "error"}
            )
            == 1
        )

    @pytest.mark.anyio
    async def test_raised_exception_from_downstream_middleware_still_recorded_and_reraised(self):
        """Confirms the middleware never swallows an exception raised by
        whatever it wraps (e.g. a blocking auth middleware chained
        before it) -- recorded as outcome="exception" and re-raised
        unchanged."""

        from to_tool_manager.security.middleware import Middleware

        class BlockingMiddleware(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                raise PermissionError("blocked")

        collector = InMemoryMetricsCollector()
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[MetricsMiddleware(collector, service_name="Dummy"), BlockingMiddleware()],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        with pytest.raises(PermissionError):
            await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert (
            collector.get_count(
                "to_tool_manager.dispatch.calls_total", {"service": "Dummy", "outcome": "exception"}
            )
            == 1
        )

    @pytest.mark.anyio
    async def test_works_without_service_name(self):
        """service_name is optional -- confirms no crash and no
        'service' tag when omitted."""
        collector = InMemoryMetricsCollector()
        svc = Service(name="Dummy", service=DummyService, middlewares=[MetricsMiddleware(collector)])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is True
        assert collector.get_count("to_tool_manager.dispatch.calls_total", {"outcome": "success"}) == 1
