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
