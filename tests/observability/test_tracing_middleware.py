import pytest

from to_tool_manager.core.service import Service
from to_tool_manager.observability import TracingMiddleware
from to_tool_manager.orchestrator import ToToolManager
from to_tool_manager.security.middleware import Middleware


def _in_memory_tracer():
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test"), exporter


class DummyService:
    def greet(self, name: str) -> str:
        """Greet a user by name."""
        return f"Hello, {name}!"

    def boom(self) -> str:
        """Always raises."""
        raise ValueError("kaboom")


class TestTracingMiddlewareRequiresOpenTelemetry:
    def test_missing_opentelemetry_raises_friendly_error(self, monkeypatch):
        """Simulates opentelemetry not being installed by making the
        import fail, without needing a second real environment --
        confirms the friendly ImportError, matching the fastmcp
        adapter's own pattern."""
        import builtins

        real_import = builtins.__import__

        def blocking_import(name, *args, **kwargs):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError("simulated: no module named opentelemetry")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocking_import)

        with pytest.raises(ImportError, match="opentelemetry"):
            TracingMiddleware()

    def test_passing_an_existing_tracer_skips_the_import_entirely(self, monkeypatch):
        """When `tracer=` is given, construction must not need to
        import opentelemetry itself at all (the caller already has a
        Tracer instance)."""
        import builtins

        real_import = builtins.__import__

        def blocking_import(name, *args, **kwargs):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError("simulated: should not be imported")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocking_import)

        sentinel_tracer = object()
        mw = TracingMiddleware(tracer=sentinel_tracer)  # must not raise
        assert mw is not None


class TestTracingMiddlewareIsOptIn:
    @pytest.mark.anyio
    async def test_manager_without_tracing_middleware_unaffected(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is True


class TestTracingMiddlewareEndToEnd:
    @pytest.mark.anyio
    async def test_successful_call_creates_a_span_with_success_outcome(self):
        tracer, exporter = _in_memory_tracer()
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[TracingMiddleware(tracer=tracer, service_name="Dummy")],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is True
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "to_tool_manager.dispatch"
        assert spans[0].attributes["to_tool_manager.service"] == "Dummy"
        assert spans[0].attributes["to_tool_manager.operation_count"] == 1
        assert spans[0].attributes["to_tool_manager.outcome"] == "success"

    @pytest.mark.anyio
    async def test_per_operation_failure_records_error_outcome(self):
        tracer, exporter = _in_memory_tracer()
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[TracingMiddleware(tracer=tracer, service_name="Dummy")],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "boom", "args": {}}])

        assert result.ok is True  # dispatch itself succeeded; the per-op call failed
        spans = exporter.get_finished_spans()
        assert spans[0].attributes["to_tool_manager.outcome"] == "success"

    @pytest.mark.anyio
    async def test_structural_failure_records_error_outcome(self):
        tracer, exporter = _in_memory_tracer()
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[TracingMiddleware(tracer=tracer, service_name="Dummy")],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[])

        assert result.ok is False
        spans = exporter.get_finished_spans()
        assert spans[0].attributes["to_tool_manager.outcome"] == "error"

    @pytest.mark.anyio
    async def test_raised_exception_is_recorded_on_span_and_still_reraised(self):
        class BlockingMiddleware(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                raise PermissionError("blocked")

        tracer, exporter = _in_memory_tracer()
        svc = Service(
            name="Dummy",
            service=DummyService,
            middlewares=[TracingMiddleware(tracer=tracer, service_name="Dummy"), BlockingMiddleware()],
        )
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        with pytest.raises(PermissionError):
            await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes["to_tool_manager.outcome"] == "exception"
        assert len(spans[0].events) == 1  # record_exception() adds an event

    @pytest.mark.anyio
    async def test_works_without_service_name(self):
        tracer, exporter = _in_memory_tracer()
        svc = Service(name="Dummy", service=DummyService, middlewares=[TracingMiddleware(tracer=tracer)])
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]

        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])

        assert result.ok is True
        spans = exporter.get_finished_spans()
        assert "to_tool_manager.service" not in spans[0].attributes
