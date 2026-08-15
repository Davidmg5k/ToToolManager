import pytest
from to_tool_manager.core.module import Module
from to_tool_manager.core.service import Service


class OrderService:
    def create(self, name: str) -> str:
        return f"Created {name}"

    def list_all(self) -> list:
        return ["order1", "order2"]


class UserService:
    def get(self, user_id: int) -> str:
        return f"User {user_id}"


class TestModule:
    def test_basic_creation(self):
        svc = Service(name="Order", service=OrderService)
        module = Module(name="OrderModule", services=[svc])
        assert module.name == "OrderModule"
        assert len(module.services) == 1

    def test_empty_services_raises(self):
        with pytest.raises(ValueError, match="at least one Service"):
            Module(name="Empty", services=[])

    def test_description(self):
        svc = Service(name="Order", service=OrderService)
        module = Module(name="OrderModule", services=[svc], description="Order management")
        assert module.description == "Order management"

    def test_system_prompt(self):
        svc = Service(name="Order", service=OrderService)
        module = Module(
            name="OrderModule",
            services=[svc],
            system_prompt="You are an order expert.",
        )
        assert module.system_prompt == "You are an order expert."

    def test_model_override(self):
        svc = Service(name="Order", service=OrderService)
        module = Module(name="OrderModule", services=[svc], model="gpt-4")
        assert module.model == "gpt-4"

    def test_subagent_mode_default(self):
        svc = Service(name="Order", service=OrderService)
        module = Module(name="OrderModule", services=[svc])
        assert module.subagent_mode == "sync"

    def test_sub_manager(self):
        svc = Service(name="Order", service=OrderService)
        module = Module(name="OrderModule", services=[svc])
        manager = module.sub_manager
        assert "Order" in manager.services


class TestModuleSubManagerConcurrency:
    """Fase 0.2 (D3): Module._get_sub_manager() concurrency guarantee --
    same double-checked-locking pattern as Service.get_instance (Fase 0.1),
    verified the same way: widen the race window on construction, then
    hammer it from many real threads."""

    def test_concurrent_construction_creates_exactly_one_sub_manager(self, monkeypatch):
        import time

        from to_tool_manager.core.manager import ToToolManager
        from tests.concurrency_harness import run_concurrently_threads

        original_init = ToToolManager.__init__

        def slow_init(self, *args, **kwargs):
            time.sleep(0.02)
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(ToToolManager, "__init__", slow_init)

        svc = Service(name="Order", service=OrderService)
        module = Module(name="OrderModule", services=[svc])

        result = run_concurrently_threads(lambda _: module._get_sub_manager())

        assert result.ok
        assert result.unique_result_count == 1
        assert module.sub_manager is result.results[0]

    def test_locks_are_per_module_not_global(self):
        svc = Service(name="Order", service=OrderService)
        module_a = Module(name="A", services=[svc])
        module_b = Module(name="B", services=[svc])
        assert module_a._sub_manager_lock is not module_b._sub_manager_lock


class TestModuleBuildToolSpec:
    def test_build_tool_spec(self):
        svc = Service(name="Order", service=OrderService)
        module = Module(name="OrderModule", services=[svc])
        spec = module.build_tool_spec()
        assert spec.name == "OrderModule"
        assert spec.metadata.get("type") == "module"

    @pytest.mark.anyio
    async def test_dispatch_operations(self):
        svc = Service(name="Order", service=OrderService)
        module = Module(name="OrderModule", services=[svc])
        spec = module.build_tool_spec()
        result = await spec.call(
            operations=[{"method": "create", "args": {"name": "Test"}}]
        )
        assert result.ok is True
        assert result.content[0]["success"] is True

    @pytest.mark.anyio
    async def test_dispatch_multiple_services(self):
        svc1 = Service(name="Order", service=OrderService)
        svc2 = Service(name="User", service=UserService)
        module = Module(name="MixedModule", services=[svc1, svc2])
        spec = module.build_tool_spec()
        result = await spec.call(
            operations=[
                {"method": "create", "args": {"name": "Order1"}},
                {"method": "get", "args": {"user_id": 1}},
            ]
        )
        assert result.ok is True
        assert len(result.content) == 2

    @pytest.mark.anyio
    async def test_dispatch_empty_operations(self):
        svc = Service(name="Order", service=OrderService)
        module = Module(name="OrderModule", services=[svc])
        spec = module.build_tool_spec()
        result = await spec.call(operations=[])
        assert result.ok is False
        assert result.error is not None

    @pytest.mark.anyio
    async def test_dispatch_unknown_method(self):
        svc = Service(name="Order", service=OrderService)
        module = Module(name="OrderModule", services=[svc])
        spec = module.build_tool_spec()
        result = await spec.call(
            operations=[{"method": "nonexistent", "args": {}}]
        )
        assert result.ok is True
        assert result.content[0]["success"] is False
