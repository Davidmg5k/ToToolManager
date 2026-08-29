"""Cross-cutting integration tests for audit fixes."""
import asyncio
import threading
import time

import pytest

from to_tool_manager.core.executor import make_safe_caller
from to_tool_manager.core.manager import ToToolManager
from to_tool_manager.core.service import Service
from to_tool_manager.core.types import ToolResponse, ToolError
from to_tool_manager.security.middleware import Middleware


class DummyService:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

    def add(self, a: int, b: int) -> int:
        return a + b


class DummyMiddleware(Middleware):
    name = "dummy"

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestRegisterMiddlewareConcurrency:
    def test_register_middleware_concurrent_with_tool_specs(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        errors = []

        def build_specs():
            try:
                specs = manager.tool_specs
                assert len(specs) == 1
            except Exception as e:
                errors.append(e)

        def register():
            try:
                manager.register_middleware(DummyMiddleware())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=build_specs) for _ in range(5)]
        threads += [threading.Thread(target=register) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        manager.refresh()
        specs = manager.tool_specs
        assert len(specs) == 1

    def test_register_middleware_invalidation_chain(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])
        initial = manager.tool_specs
        assert len(initial) == 1

        manager.register_middleware(DummyMiddleware())
        assert manager._specs is None
        assert manager._service_specs is None
        rebuilt = manager.tool_specs
        assert len(rebuilt) == 1


class TestAgentOrchestratorConcurrency:
    def test_concurrent_add_and_has(self):
        from to_tool_manager.orchestrator.agent_orchestrator import AgentOrchestrator

        class FakeAgent:
            def __init__(self, name):
                self.name = name
                self.agent = None

        orch = AgentOrchestrator()
        errors = []

        def add_agents():
            try:
                for i in range(10):
                    orch.add_agent(FakeAgent(f"agent_{threading.current_thread().ident}_{i}"))
            except Exception as e:
                errors.append(e)

        def check_agents():
            try:
                for _ in range(10):
                    orch.has_agent("nonexistent")
                    orch.get_agent("nonexistent")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_agents) for _ in range(3)]
        threads += [threading.Thread(target=check_agents) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


class TestSkipCoercion:
    def test_skip_coercion_true_skips_coerce_kwargs(self):
        call_count = 0

        class CountingService:
            def process(self, data: str) -> str:
                nonlocal call_count
                call_count += 1
                return data

        svc = Service(name="Counter", service=CountingService, skip_coercion=True)
        caller = make_safe_caller(
            svc.get_instance().process,
            skip_coercion=True,
        )

        async def run():
            return await caller(data="hello")

        result = asyncio.run(run())
        assert call_count == 1
        assert result.content == "hello"

    def test_skip_coercion_false_runs_coerce_kwargs(self):
        svc = Service(name="Dummy", service=DummyService)
        caller = make_safe_caller(
            svc.get_instance().greet,
            skip_coercion=False,
        )

        async def run():
            return await caller(name="world")

        result = asyncio.run(run())
        assert result.content == "Hello, world!"


class TestDispatchO1:
    def test_dispatch_unknown_method_includes_available(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])

        async def run():
            from to_tool_manager.core.module import _dispatch_to_services
            return await _dispatch_to_services(manager, "nonexistent", {})

        result = asyncio.run(run())
        assert result.error is not None
        assert "greet" in result.error.message
        assert "add" in result.error.message

    def test_dispatch_known_method_works(self):
        svc = Service(name="Dummy", service=DummyService)
        manager = ToToolManager([svc])

        async def run():
            from to_tool_manager.core.module import _dispatch_to_services
            return await _dispatch_to_services(manager, "greet", {"name": "test"})

        result = asyncio.run(run())
        assert result.error is None
        assert result.content[0]["result"] == "Hello, test!"
