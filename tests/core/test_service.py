import pytest
from to_tool_manager.core.service import Service
from to_tool_manager.core.discovery import Visibility
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
