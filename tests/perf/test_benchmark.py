import time
import pytest
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.middleware.middleware import Middleware
from tests.conftest import ConcreteToolMiddleware


class UserService:
    """Servicio de usuarios para testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}


class SlowMiddleware(ConcreteToolMiddleware):
    """Middleware que simula latencia."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestBenchmark:
    """Tests de rendimiento (NRF-001)."""

    def test_service_creation_latency(self):
        """Service se crea en menos de 10ms"""
        start = time.perf_counter()
        for _ in range(100):
            Service(
                name="User",
                service=UserService,
                instructions="Gestión de usuarios"
            )
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 10, f"Service creation avg: {avg_ms:.2f}ms (>10ms)"

    def test_build_as_capability_latency(self):
        """build_as_capability() completa en menos de 10ms"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        start = time.perf_counter()
        for _ in range(100):
            service.build_as_capability()
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 10, f"build_as_capability() avg: {avg_ms:.2f}ms (>10ms)"

    def test_resolve_middlewares_latency(self):
        """_resolve_middlewares() completa en menos de 10ms"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            middleware=[SlowMiddleware(), SlowMiddleware()]
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service],
            middlewares=[SlowMiddleware(), SlowMiddleware(), SlowMiddleware()]
        )
        start = time.perf_counter()
        for _ in range(100):
            manager._resolve_middlewares(service)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 10, f"_resolve_middlewares() avg: {avg_ms:.2f}ms (>10ms)"

    def test_build_agent_latency(self):
        """build_agent() completa en menos de 50ms"""
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        start = time.perf_counter()
        manager = ToToolManager(
            name="TestManager",
            resources=[service]
        )
        manager.build_agent()
        elapsed = time.perf_counter() - start
        elapsed_ms = elapsed * 1000
        assert elapsed_ms < 50, f"build_agent() took: {elapsed_ms:.2f}ms (>50ms)"

    def test_middleware_overhead(self):
        """Overhead de middleware es < 1ms por llamada"""
        call_count = 0

        class CounterMiddleware(ConcreteToolMiddleware):
            async def dispatch(self, func, /, *args, **kw):
                nonlocal call_count
                call_count += 1
                return await func(*args, **kw)

        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios",
            middleware=[CounterMiddleware(), CounterMiddleware(), CounterMiddleware()]
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service]
        )

        start = time.perf_counter()
        for _ in range(100):
            manager._resolve_middlewares(service)
        elapsed = time.perf_counter() - start
        avg_per_call_ms = (elapsed / (100 * 3)) * 1000  # 3 middlewares per call
        assert avg_per_call_ms < 1, f"Middleware overhead: {avg_per_call_ms:.4f}ms (>1ms)"
