import pytest
from to_tool_manager.orchestrator.shared.agent_support import AgentSupport
from to_tool_manager.core.service import Service


class DummyService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"


class AnotherService:
    def run(self) -> str:
        return "running"


class TestAgentSupport:
    def test_init(self):
        support = AgentSupport(model="openai:gpt-4o")
        assert support.services == []
        assert support.modules == []

    def test_init_with_middleware(self):
        from to_tool_manager.security.middleware import Middleware

        class TestMiddleware(Middleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        support = AgentSupport(model="openai:gpt-4o", middleware=[TestMiddleware()])
        assert support.services == []

    def test_manager_property_not_initialized(self):
        support = AgentSupport(model="openai:gpt-4o")
        with pytest.raises(RuntimeError, match="Manager not initialized"):
            _ = support._manager

    def test_agent_property_not_initialized(self):
        support = AgentSupport(model="openai:gpt-4o")
        with pytest.raises(RuntimeError, match="Agent not initialized"):
            _ = support.agent

    def test_add_service(self):
        support = AgentSupport(model="openai:gpt-4o")
        support.add_service("Dummy", DummyService)
        assert len(support.services) == 1
        assert support.services[0].name == "Dummy"

    def test_add_multiple_services(self):
        support = AgentSupport(model="openai:gpt-4o")
        support.add_service("Dummy", DummyService)
        support.add_service("Another", AnotherService)
        assert len(support.services) == 2

    def test_add_module(self):
        support = AgentSupport(model="openai:gpt-4o")
        svc = Service(name="Dummy", service=DummyService)
        support.add_module("TestModule", [svc])
        assert len(support.modules) == 1
        assert support.modules[0].name == "TestModule"

    def test_add_services_to_module(self):
        support = AgentSupport(model="openai:gpt-4o")
        svc1 = Service(name="Dummy", service=DummyService)
        support.add_module("TestModule", [svc1])

        svc2 = Service(name="Another", service=AnotherService)
        support.add_services_to_module("TestModule", [svc2])

        module = support.modules[0]
        assert len(module.services) == 2

    def test_add_services_to_module_not_found(self):
        support = AgentSupport(model="openai:gpt-4o")
        svc = Service(name="Dummy", service=DummyService)
        with pytest.raises(ValueError, match="Module 'Nonexistent' not found"):
            support.add_services_to_module("Nonexistent", [svc])

    def test_add_services_to_module_duplicate_name(self):
        support = AgentSupport(model="openai:gpt-4o")
        svc1 = Service(name="Dummy", service=DummyService)
        support.add_module("TestModule", [svc1])

        svc2 = Service(name="Dummy", service=AnotherService)
        with pytest.raises(ValueError, match="Service 'Dummy' already exists"):
            support.add_services_to_module("TestModule", [svc2])

    def test_services_property_returns_copy(self):
        support = AgentSupport(model="openai:gpt-4o")
        support.add_service("Dummy", DummyService)
        services = support.services
        services.clear()
        assert len(support.services) == 1

    def test_modules_property_returns_copy(self):
        support = AgentSupport(model="openai:gpt-4o")
        svc = Service(name="Dummy", service=DummyService)
        support.add_module("TestModule", [svc])
        modules = support.modules
        modules.clear()
        assert len(support.modules) == 1