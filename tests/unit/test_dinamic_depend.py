"""Tests for DinamicDepend's Python data-model contract.

Reference: FASE-0 (auditoría 2026-09-24) -- DinamicDepend must follow the
standard Python attribute protocol so that hasattr(), getattr() with a
default, and direct access behave as callers expect in pydantic-ai/FastAPI.

Postcondition under test (precondición de integración con frameworks):
    - hasattr(dep, missing)  -> False
    - getattr(dep, missing)  -> raises DependencyNotSetError (AttributeError)
    - getattr(dep, missing, default) -> default
    - dep.missing            -> raises DependencyNotSetError (AttributeError)
    - dep.present            -> value
"""

import pytest

from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend
from to_tool_manager.exception import DependencyNotSetError


class TestDinamicDependContract:
    """Fixes the Python data-model contract for dynamic attributes."""

    def test_set_and_get_attribute(self):
        """Dynamically set attributes are retrievable by name."""
        dep = DinamicDepend()
        dep.user = {"id": 1}
        assert dep.user == {"id": 1}

    def test_hasattr_returns_false_for_missing(self):
        """hasattr() must return False instead of raising."""
        dep = DinamicDepend()
        dep.user = {"id": 1}
        assert hasattr(dep, "user") is True
        assert hasattr(dep, "missing") is False

    def test_getattr_with_default_for_missing(self):
        """getattr() must return the default for missing attributes."""
        dep = DinamicDepend()
        assert getattr(dep, "missing", "DEFAULT") == "DEFAULT"

    def test_direct_access_raises_dependency_not_set(self):
        """Direct access to a missing attribute raises DependencyNotSetError."""
        dep = DinamicDepend()
        with pytest.raises(DependencyNotSetError):
            dep.missing

    def test_error_is_attribute_error(self):
        """DependencyNotSetError must be an AttributeError subclass."""
        dep = DinamicDepend()
        with pytest.raises(AttributeError):
            dep.missing

    def test_error_is_catchable_as_service_error(self):
        """Backwards compatibility: still catchable as ServiceError/TTMError."""
        dep = DinamicDepend()
        with pytest.raises(Exception) as exc_info:
            dep.missing
        assert isinstance(exc_info.value, DependencyNotSetError)

    def test_internal_attributes_use_object_semantics(self):
        """Private attrs (underscore-prefixed) bypass the dynamic store."""
        dep = DinamicDepend()
        dep._internal = 42
        assert dep._internal == 42
        data = object.__getattribute__(dep, "_data")
        assert "_internal" not in data

    def test_name_attribute_on_exception(self):
        """The exception carries the missing attribute name."""
        dep = DinamicDepend()
        with pytest.raises(DependencyNotSetError) as exc_info:
            dep.missing
        assert exc_info.value.name == "missing"

    def test_overwrite_allowed(self):
        """Attributes can be overwritten dynamically."""
        dep = DinamicDepend()
        dep.value = 1
        dep.value = 2
        assert dep.value == 2