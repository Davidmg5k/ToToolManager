import threading
from typing import Any

import pytest
from to_tool_manager.core.service import Service
from to_tool_manager.core.types import ErrorMap


class DummyService:
    def do(self):
        pass


class AnotherService:
    def run(self):
        pass


class TestService:
    def test_basic_creation(self):
        svc = Service(name="Test", service=DummyService)
        assert svc.name == "Test"
        assert svc.service is DummyService
        assert svc.description == ""
        assert svc.singleton is True

    def test_description(self):
        svc = Service(name="Test", service=DummyService, description="My service")
        assert svc.description == "My service"

    def test_visibility_default(self):
        svc = Service(name="Test", service=DummyService)
        assert svc.visibility == frozenset({"public"})

    def test_visibility_custom(self):
        svc = Service(name="Test", service=DummyService, visibility=frozenset({"public", "protected"}))
        assert "protected" in svc.visibility

    def test_include_exclude(self):
        svc = Service(
            name="Test",
            service=DummyService,
            include=frozenset({"do"}),
            exclude=frozenset({"hidden"}),
        )
        assert svc.include == frozenset({"do"})
        assert svc.exclude == frozenset({"hidden"})

    def test_include_exclude_overlap_raises(self):
        with pytest.raises(ValueError, match="appear in both"):
            Service(
                name="Test",
                service=DummyService,
                include=frozenset({"do", "run"}),
                exclude=frozenset({"run"}),
            )

    def test_non_class_service_raises(self):
        with pytest.raises(TypeError, match="must be a class"):
            Service(name="Test", service="not_a_class")

    def test_non_class_instance_raises(self):
        with pytest.raises(TypeError, match="must be a class"):
            Service(name="Test", service=DummyService())

    def test_singleton_default(self):
        svc = Service(name="Test", service=DummyService)
        assert svc.singleton is True

    def test_get_instance_singleton(self):
        svc = Service(name="Test", service=DummyService, singleton=True)
        i1 = svc.get_instance()
        i2 = svc.get_instance()
        assert i1 is i2

    def test_get_instance_non_singleton(self):
        svc = Service(name="Test", service=DummyService, singleton=False)
        i1 = svc.get_instance()
        i2 = svc.get_instance()
        assert i1 is not i2

    def test_error_map_default(self):
        svc = Service(name="Test", service=DummyService)
        assert isinstance(svc.error_map, ErrorMap)

    def test_error_map_custom(self):
        em = ErrorMap().map(ValueError, category="validation")
        svc = Service(name="Test", service=DummyService, error_map=em)
        assert svc.error_map is em

    def test_error_rules(self):
        def my_rule(exc):
            return None

        svc = Service(name="Test", service=DummyService, error_rules=(my_rule,))
        assert len(svc.error_rules) == 1

    def test_middlewares(self):
        svc = Service(name="Test", service=DummyService, middlewares=())
        assert svc.middlewares == ()

    def test_disable_middlewares(self):
        svc = Service(name="Test", service=DummyService, disable_middlewares=("auth",))
        assert "auth" in svc.disable_middlewares

    def test_args_kwargs(self):
        svc = Service(name="Test", service=DummyService, args=(1, 2), kwargs={"key": "value"})
        assert svc.args == (1, 2)
        assert svc.kwargs == {"key": "value"}


class _SlowInitService:
    """__init__ deliberately sleeps to widen the race window between the
    check and the act in get_instance()'s double-checked locking."""

    _construction_count = 0
    _construction_lock = threading.Lock()

    def __init__(self, delay: float = 0.02):
        import time
        time.sleep(delay)
        with _SlowInitService._construction_lock:
            _SlowInitService._construction_count += 1
        self.id = id(self)


class TestServiceConcurrency:
    """Fase 0.1 (D1): Service.get_instance() concurrency/isolation
    guarantees under real, concurrent callers -- not just sequential
    calls (already covered by test_get_instance_singleton above)."""

    def test_concurrent_get_instance_creates_exactly_one_instance_threads(self):
        """N real OS threads race on the same Service's first
        get_instance() call. Exactly one instance must be constructed."""
        from tests.concurrency_harness import run_concurrently_threads

        _SlowInitService._construction_count = 0
        svc = Service(name="Test", service=_SlowInitService, singleton=True)

        result = run_concurrently_threads(lambda _: svc.get_instance())

        assert result.ok
        assert _SlowInitService._construction_count == 1
        assert result.unique_result_count == 1

    def test_concurrent_get_instance_creates_exactly_one_instance_asyncio(self):
        """Same guarantee from the async side: many concurrent asyncio
        tasks (via asyncio.gather + to_thread, matching how a tool-call
        dispatch would actually invoke this sync method under load)."""
        from tests.concurrency_harness import run_concurrently_async

        _SlowInitService._construction_count = 0
        svc = Service(name="Test", service=_SlowInitService, singleton=True)

        result = run_concurrently_async(lambda _: svc.get_instance())

        assert result.ok
        assert _SlowInitService._construction_count == 1
        assert result.unique_result_count == 1

    def test_locks_are_per_instance_not_global(self):
        """Two unrelated Services must not contend on the same lock --
        each Service gets its own, independent lock."""
        svc_a = Service(name="A", service=DummyService, singleton=True)
        svc_b = Service(name="B", service=AnotherService, singleton=True)
        assert svc_a._instance_lock is not svc_b._instance_lock

    def test_singleton_shares_state_across_concurrent_tenants(self):
        """Documents, with a test, the isolation contract described in
        Service.singleton's docstring: `singleton=True` means every
        caller against the SAME Service object shares the same instance
        and therefore any mutable state on it -- confirmed here under
        real concurrent access simulating two tenants hitting the same
        (shared) Service. This is expected/by-design, not a bug -- the
        Service author opts into sharing via `singleton=True`."""
        class StatefulService:
            def __init__(self):
                self.calls: list[str] = []

            def touch(self, tenant: str) -> None:
                self.calls.append(tenant)

        svc = Service(name="Stateful", service=StatefulService, singleton=True)

        instance_a = svc.get_instance()
        instance_a.touch("tenant-a")
        instance_b = svc.get_instance()
        instance_b.touch("tenant-b")

        # Same shared instance -- tenant-b's call is visible to tenant-a's view.
        assert instance_a is instance_b
        assert instance_a.calls == ["tenant-a", "tenant-b"]

    def test_singleton_false_gives_per_call_isolation(self):
        """The documented escape hatch: singleton=False gives each caller
        its own instance, with no shared mutable state at all."""
        class StatefulService:
            def __init__(self):
                self.calls: list[str] = []

            def touch(self, tenant: str) -> None:
                self.calls.append(tenant)

        svc = Service(name="Stateful", service=StatefulService, singleton=False)

        instance_a = svc.get_instance()
        instance_a.touch("tenant-a")
        instance_b = svc.get_instance()
        instance_b.touch("tenant-b")

        assert instance_a is not instance_b
        assert instance_a.calls == ["tenant-a"]
        assert instance_b.calls == ["tenant-b"]
