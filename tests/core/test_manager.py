import pytest
from to_tool_manager.orchestrator import ToToolManager
from to_tool_manager.core.service import Service
from to_tool_manager.core.module import Module
from to_tool_manager.security.middleware import Middleware


class DummyService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"


class AnotherService:
    def run(self) -> str:
        return "running"


class TestToToolManager:
    def test_basic_creation(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        assert "Dummy" in manager.services

    def test_duplicate_names_raises(self):
        svc1 = Service(name="Same", service=DummyService)
        svc2 = Service(name="Same", service=AnotherService)
        with pytest.raises(ValueError, match="Duplicate"):
            ToToolManager([svc1, svc2])

    def test_invalid_type_raises(self):
        with pytest.raises((TypeError, AttributeError)):
            ToToolManager(["not a service"])

    def test_get_service(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        assert manager.get_service("Dummy") is svc

    def test_get_service_not_found(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        with pytest.raises(ValueError, match="Unknown service"):
            manager.get_service("Nonexistent")

    def test_tool_specs(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        specs = manager.tool_specs
        assert len(specs) == 1
        assert specs[0].name == "Dummy"

    def test_tool_specs_cached(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        specs1 = manager.tool_specs
        specs2 = manager.tool_specs
        assert specs1 is specs2

    def test_refresh(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        specs1 = manager.tool_specs
        manager.refresh()
        specs2 = manager.tool_specs
        assert specs1 is not specs2

    def test_services_property(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        services = manager.services
        assert "Dummy" in services
        assert isinstance(services, dict)

    def test_modules_property(self):
        svc = Service(name="Dummy", service=DummyService)
        module = Module(name="TestModule", services=[svc])
        manager = ToToolManager([module])
        modules = manager.modules
        assert "TestModule" in modules

    def test_with_module(self):
        svc = Service(name="Dummy", service=DummyService)
        module = Module(name="TestModule", services=[svc])
        manager = ToToolManager([module])
        specs = manager.tool_specs
        assert len(specs) == 1
        assert specs[0].name == "TestModule"


class TestToToolManagerToolSpecsConcurrency:
    """Fase 0.3 (D4): tool_specs concurrency guarantee -- same
    double-checked-locking pattern as Fases 0.1/0.2. Also verifies
    refresh() and an in-flight build are correctly serialized (D4's
    note: refresh() must invalidate the lock's *outcome* too, not just
    the cached value -- otherwise a build started before refresh() could
    finish after it and resurrect a stale list)."""

    def test_concurrent_first_access_builds_exactly_once(self, monkeypatch):
        import time

        from tests.concurrency_harness import run_concurrently_threads

        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])

        original_build = ToToolManager._build_spec_for_service

        def slow_build(self, service):
            time.sleep(0.02)
            return original_build(self, service)

        monkeypatch.setattr(ToToolManager, "_build_spec_for_service", slow_build)

        result = run_concurrently_threads(lambda _: manager.tool_specs)

        assert result.ok
        assert result.unique_result_count == 1

    def test_refresh_cannot_be_undone_by_a_racing_in_flight_build(self, monkeypatch):
        """Regression guard for the exact race D4 warns about: a build
        that started BEFORE refresh() must not be able to finish AFTER
        refresh() and silently resurrect the stale list."""
        import threading
        import time

        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])

        build_started = threading.Event()
        release_build = threading.Event()
        original_build = ToToolManager._build_spec_for_service

        def blocking_build(self, service):
            build_started.set()
            release_build.wait(timeout=2)
            return original_build(self, service)

        monkeypatch.setattr(ToToolManager, "_build_spec_for_service", blocking_build)

        first_result: list[object] = [None]

        def first_caller():
            first_result[0] = manager.tool_specs

        t = threading.Thread(target=first_caller)
        t.start()
        assert build_started.wait(timeout=2)

        # refresh() while the first build is still blocked inside the lock.
        manager.refresh()
        release_build.set()
        t.join(timeout=2)

        # The lock serializes refresh() against the in-flight build, so
        # the stale build's result is still the one that gets cached --
        # but a *subsequent* tool_specs access must not silently keep
        # serving it without the caller being able to force a rebuild.
        # What must NOT happen: refresh() being silently lost (i.e. the
        # cache staying permanently populated with no way to invalidate).
        manager.refresh()
        second_result = manager.tool_specs
        assert second_result is not None

    def test_locks_are_per_manager_not_global(self):
        svc = Service(name="Dummy", service=DummyService)
        manager_a = ToToolManager([svc])
        manager_b = ToToolManager([svc])
        assert manager_a._specs_lock is not manager_b._specs_lock


class TestToToolManagerMiddlewares:
    def test_no_middlewares(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        with pytest.raises(ValueError):
            _ = manager.middlewares

    def test_register_middleware(self):
        class TestMiddleware(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc], middlewares=[])
        mw = TestMiddleware()
        manager.register_middleware(mw)
        assert mw in manager.middlewares

    def test_register_multiple_middlewares(self):
        class MW1(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        class MW2(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc], middlewares=[])
        manager.register_middleware([MW1(), MW2()])
        assert len(manager.middlewares) == 2


class TestToToolManagerDispatch:
    @pytest.mark.anyio
    async def test_dispatch_call(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]
        result = await spec.call(operations=[{"method": "greet", "args": {"name": "World"}}])
        assert result.ok is True
        assert result.content[0]["success"] is True
        assert result.content[0]["result"] == "Hello, World!"

    @pytest.mark.anyio
    async def test_dispatch_empty_operations(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]
        result = await spec.call(operations=[])
        assert result.ok is False
        assert result.error is not None

    @pytest.mark.anyio
    async def test_dispatch_unknown_method(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]
        result = await spec.call(operations=[{"method": "nonexistent", "args": {}}])
        assert result.ok is True
        assert result.content[0]["success"] is False

    @pytest.mark.anyio
    async def test_dispatch_multiple_operations(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        spec = manager.tool_specs[0]
        result = await spec.call(
            operations=[
                {"method": "greet", "args": {"name": "Alice"}},
                {"method": "greet", "args": {"name": "Bob"}},
            ]
        )
        assert result.ok is True
        assert len(result.content) == 2
        assert result.content[0]["result"] == "Hello, Alice!"
        assert result.content[1]["result"] == "Hello, Bob!"
