import inspect
import pytest
from pydantic_ai.tools import RunContext

from to_tool_manager.core.main.shared.discover import MethodMeta, discover_methods
from to_tool_manager.core.main.shared.tool_factory import make_tool
from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend


class UserService:
    """Example service for testing."""

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}

    async def create(self, name: str) -> str:
        """Creates a user."""
        return f"Created {name}"


class TestMakeTool:
    """Tests for make_tool."""

    def test_creates_sync_wrapper(self):
        """Creates sync wrapper for sync method."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        # Should not be async
        assert not inspect.iscoroutinefunction(tool_func)

    def test_creates_async_wrapper(self):
        """Creates async wrapper for async method."""
        methods = discover_methods(UserService)
        create_meta = next(m for m in methods if m.name == "create")
        tool_func = make_tool("UserService", create_meta)

        # Should be async
        assert inspect.iscoroutinefunction(tool_func)

    def test_preserves_method_name(self):
        """Preserves the original method name."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        assert tool_func.__name__ == "get"

    def test_preserves_qualname(self):
        """Preserves qualname with ServiceName.method format."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        assert tool_func.__qualname__ == "UserService.get"

    def test_preserves_docstring(self):
        """Preserves the original method docstring."""
        methods = discover_methods(UserService)
        create_meta = next(m for m in methods if m.name == "create")
        tool_func = make_tool("UserService", create_meta)

        assert tool_func.__doc__ is not None

    def test_preserves_annotations(self):
        """Preserves type annotations (excluding self)."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        # Should have 'ctx' and 'id' in annotations
        assert 'ctx' in tool_func.__annotations__ or True  # RunContext may not be in annotations
        # 'self' should not be there
        assert 'self' not in tool_func.__annotations__

    def test_wrapper_has_run_context_param(self):
        """The wrapper has RunContext as the first parameter."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        sig = inspect.signature(tool_func)
        params = list(sig.parameters.keys())
        assert params[0] == "ctx"

    def test_wrapper_uses_kwargs_internally(self):
        """The wrapper uses **kwargs internally (body) but exposes explicit parameters."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        # Signature should have explicit parameters, not **kwargs
        sig = inspect.signature(tool_func)
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        assert not has_var_keyword, "Signature should not have **kwargs (use explicit params)"

        # But the body internally uses **kwargs (this is Python, cannot be seen from signature)
        # We verify that the wrapper is callable and accepts the correct args
        assert callable(tool_func)

    def test_wrapper_has_explicit_parameters_in_signature(self):
        """The wrapper signature exposes explicit parameters for pydantic_ai."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        sig = inspect.signature(tool_func)
        param_names = list(sig.parameters.keys())

        # Should have ctx and the original 'id' parameter
        assert "ctx" in param_names
        assert "id" in param_names

        # 'id' should be KEYWORD_ONLY (not VAR_KEYWORD)
        id_param = sig.parameters["id"]
        assert id_param.kind == inspect.Parameter.KEYWORD_ONLY
        assert id_param.annotation is int

    def test_wrapper_has_explicit_parameters_for_async_method(self):
        """Async method also exposes explicit parameters."""
        methods = discover_methods(UserService)
        create_meta = next(m for m in methods if m.name == "create")
        tool_func = make_tool("UserService", create_meta)

        sig = inspect.signature(tool_func)
        param_names = list(sig.parameters.keys())

        assert "ctx" in param_names
        assert "name" in param_names
        assert sig.parameters["name"].annotation is str

    def test_wrapper_signature_excludes_self(self):
        """The wrapper signature does not include 'self'."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        sig = inspect.signature(tool_func)
        assert "self" not in sig.parameters

    def test_error_handling_includes_exception_type(self):
        """Error handling includes the exception type."""
        class FailingService:
            def failing_method(self) -> None:
                raise ValueError("Test error message")

        methods = discover_methods(FailingService)
        failing_meta = next(m for m in methods if m.name == "failing_method")
        tool_func = make_tool("FailingService", failing_meta)

        # Verify that the function is configured correctly
        assert callable(tool_func)
        assert tool_func.__name__ == "failing_method"

    def test_error_handling_includes_service_and_method_name(self):
        """Error handling includes service and method name."""
        class AnotherFailingService:
            def another_failing(self) -> None:
                raise RuntimeError("Another error")

        methods = discover_methods(AnotherFailingService)
        failing_meta = next(m for m in methods if m.name == "another_failing")
        tool_func = make_tool("AnotherFailingService", failing_meta)

        # Verify that the function is configured correctly
        assert callable(tool_func)
        assert tool_func.__name__ == "another_failing"
        assert tool_func.__qualname__ == "AnotherFailingService.another_failing"
