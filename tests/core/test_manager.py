import pytest
from to_tool_manager.core.manager import ToToolManager
from to_tool_manager.core.service import Service
from to_tool_manager.core.module import Module
from to_tool_manager.core.types import ErrorMap, ToolResponse
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
