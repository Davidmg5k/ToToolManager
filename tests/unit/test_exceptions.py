"""Unit tests for the exception hierarchy and type-wrapper dataclasses.

Requirement: R-EXC-001 (unified TTMError hierarchy and message contracts)
Targets: src/to_tool_manager/exception/*.py, src/to_tool_manager/infra/types/main/service.py
"""

from __future__ import annotations

import pytest

from to_tool_manager.exception import (
    AgentAlreadyBuiltError,
    AgentError,
    AgentNotBuiltError,
    BuilderError,
    ConfigurationError,
    DependencyNotSetError,
    InvalidResourceTypeError,
    MiddlewareError,
    MiddlewareNotInitializedError,
    MiddlewareTargetMismatchError,
    ModuleAlreadyRegisteredError,
    ModuleError,
    SelfDisableMiddlewareError,
    ServiceAlreadyRegisteredError,
    ServiceError,
    ServiceNotFoundError,
    TTMError,
    ToToolManagerAlreadyRegisteredError,
    ToToolManagerNotFoundError,
)
from to_tool_manager.exception._ttm_error import TTMError as TTMErrorDirect
from to_tool_manager.infra.types.main.service import Exclude, Include


class TestTTMError:
    """Tests for the root exception."""

    def test_all_package_exceptions_derive_from_ttm_error(self):
        """Every public exception is a TTMError (unified catchability)."""
        exceptions = [
            ConfigurationError,
            InvalidResourceTypeError,
            SelfDisableMiddlewareError,
            ServiceError,
            ServiceNotFoundError,
            ServiceAlreadyRegisteredError,
            DependencyNotSetError,
            ModuleError,
            ModuleAlreadyRegisteredError,
            AgentError,
            AgentNotBuiltError,
            AgentAlreadyBuiltError,
            MiddlewareError,
            MiddlewareNotInitializedError,
            MiddlewareTargetMismatchError,
            BuilderError,
            ToToolManagerAlreadyRegisteredError,
            ToToolManagerNotFoundError,
        ]
        for exc in exceptions:
            assert issubclass(exc, TTMError), exc.__name__

    def test_ttm_error_is_an_exception(self):
        """TTMError itself derives from Exception."""
        assert issubclass(TTMErrorDirect, Exception)


class TestConfigurationExceptions:
    """Tests for configuration errors."""

    def test_invalid_resource_type_error(self):
        """Message and attribute follow the resource type."""
        err = InvalidResourceTypeError("dict")

        assert isinstance(err, ConfigurationError)
        assert err.got_type == "dict"
        assert str(err) == "Expected Service or Module, got dict"

    def test_self_disable_middleware_error(self):
        """Message names the offending middleware."""
        err = SelfDisableMiddlewareError("Log")

        assert isinstance(err, ConfigurationError)
        assert err.middleware_name == "Log"
        assert "Log" in str(err)


class TestServiceExceptions:
    """Tests for service errors."""

    def test_service_not_found_error(self):
        """Message quotes the unknown service name."""
        err = ServiceNotFoundError("missing")

        assert isinstance(err, ServiceError)
        assert err.name == "missing"
        assert str(err) == "Unknown service 'missing'"

    def test_service_already_registered_error(self):
        """Message quotes the duplicated service name."""
        err = ServiceAlreadyRegisteredError("orders")

        assert isinstance(err, ServiceError)
        assert err.name == "orders"
        assert str(err) == "Service 'orders' already registered"

    def test_dependency_not_set_error(self):
        """Message quotes the missing attribute name."""
        err = DependencyNotSetError("conn")

        assert isinstance(err, ServiceError)
        assert err.name == "conn"
        assert str(err) == "DinamicDepend has no attribute 'conn'"


class TestModuleExceptions:
    """Tests for module errors."""

    def test_module_already_registered_error(self):
        """Message quotes the duplicated module name."""
        err = ModuleAlreadyRegisteredError("billing")

        assert isinstance(err, ModuleError)
        assert err.name == "billing"
        assert str(err) == "Module 'billing' already registered"


class TestAgentExceptions:
    """Tests for agent errors."""

    def test_agent_not_built_error(self):
        """Message instructs to call build()."""
        err = AgentNotBuiltError("OrderAgent")

        assert isinstance(err, AgentError)
        assert err.component == "OrderAgent"
        assert "build()" in str(err)

    def test_agent_already_built_error(self):
        """Message instructs that rebuild is forbidden."""
        err = AgentAlreadyBuiltError("OrderAgent")

        assert isinstance(err, AgentError)
        assert err.component == "OrderAgent"
        assert "Cannot rebuild" in str(err)


class TestMiddlewareExceptions:
    """Tests for middleware errors."""

    def test_middleware_not_initialized_error(self):
        """Default message states the sequence is None."""
        err = MiddlewareNotInitializedError()

        assert isinstance(err, MiddlewareError)
        assert str(err) == "Middleware sequence is not initialized (None)"

    def test_middleware_target_mismatch_error(self):
        """Message names the target and expected type."""
        err = MiddlewareTargetMismatchError("module", "Service")

        assert isinstance(err, MiddlewareError)
        assert err.name == "module"
        assert err.expected == "Service"
        assert "not a Service" in str(err)


class TestBuilderExceptions:
    """Tests for builder errors."""

    def test_manager_already_registered_error(self):
        """Message quotes the duplicated ToToolManager name."""
        err = ToToolManagerAlreadyRegisteredError("main")

        assert isinstance(err, BuilderError)
        assert err.name == "main"
        assert str(err) == "ToToolManager 'main' already registered"

    def test_manager_not_found_error(self):
        """Message quotes the missing ToToolManager name."""
        err = ToToolManagerNotFoundError("ghost")

        assert isinstance(err, BuilderError)
        assert err.name == "ghost"
        assert str(err) == "ToToolManager 'ghost' not found"


class TestIncludeExclude:
    """Tests for the Include/Exclude wrappers."""

    def test_include_is_frozen_and_iterable(self):
        """Include is a frozen dataclass exposing include names."""
        inc = Include(["a", "b"])

        assert inc.include == ["a", "b"]
        assert list(inc) == ["a", "b"]
        assert len(inc) == 2

        with pytest.raises(Exception):
            inc.include = ["c"]  # frozen: assignment must fail

    def test_exclude_is_frozen_and_iterable(self):
        """Exclude is a frozen dataclass exposing exclude names."""
        exc = Exclude(["x", "y", "z"])

        assert exc.exclude == ["x", "y", "z"]
        assert list(exc) == ["x", "y", "z"]
        assert len(exc) == 3

        with pytest.raises(Exception):
            exc.exclude = ["w"]  # frozen: assignment must fail

    def test_accepts_any_sequence(self):
        """Sequence input (tuple) is stored as given."""
        inc = Include(("a", "b"))

        assert inc.include == ("a", "b")
        assert len(inc) == 2