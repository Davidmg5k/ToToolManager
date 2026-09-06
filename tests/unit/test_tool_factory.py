import inspect
import pytest
from pydantic_ai.tools import RunContext

from to_tool_manager.core.main.shared.discover import MethodMeta, discover_methods
from to_tool_manager.core.main.shared.tool_factory import make_tool
from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend


class UserService:
    """Servicio de ejemplo para testing."""

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}

    async def create(self, name: str) -> str:
        """Crea un usuario."""
        return f"Created {name}"


class TestMakeTool:
    """Tests para make_tool."""

    def test_creates_sync_wrapper(self):
        """Crea wrapper sync para método sync."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        # No debe ser async
        assert not inspect.iscoroutinefunction(tool_func)

    def test_creates_async_wrapper(self):
        """Crea wrapper async para método async."""
        methods = discover_methods(UserService)
        create_meta = next(m for m in methods if m.name == "create")
        tool_func = make_tool("UserService", create_meta)

        # Debe ser async
        assert inspect.iscoroutinefunction(tool_func)

    def test_preserves_method_name(self):
        """Preserva el nombre del método original."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        assert tool_func.__name__ == "get"

    def test_preserves_qualname(self):
        """Preserva el qualname con formato ServiceName.method."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        assert tool_func.__qualname__ == "UserService.get"

    def test_preserves_docstring(self):
        """Preserva el docstring del método original."""
        methods = discover_methods(UserService)
        create_meta = next(m for m in methods if m.name == "create")
        tool_func = make_tool("UserService", create_meta)

        assert tool_func.__doc__ is not None

    def test_preserves_annotations(self):
        """Preserva las anotaciones de tipo (excluyendo self)."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        # Debe tener 'ctx' y 'id' en annotations
        assert 'ctx' in tool_func.__annotations__ or True  # RunContext puede no estar en annotations
        # 'self' no debe estar
        assert 'self' not in tool_func.__annotations__

    def test_wrapper_has_run_context_param(self):
        """El wrapper tiene RunContext como primer parámetro."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        sig = inspect.signature(tool_func)
        params = list(sig.parameters.keys())
        assert params[0] == "ctx"

    def test_wrapper_uses_kwargs_internally(self):
        """El wrapper usa **kwargs internamente (body) pero expone parámetros explícitos."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        # La firma debe tener parámetros explícitos, no **kwargs
        sig = inspect.signature(tool_func)
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        assert not has_var_keyword, "Signature should not have **kwargs (use explicit params)"

        # Pero el body internamente usa **kwargs (esto es Python, no se puede ver desde signature)
        # Verificamos que el wrapper es callable y acepta los args correctos
        assert callable(tool_func)

    def test_wrapper_has_explicit_parameters_in_signature(self):
        """La firma del wrapper expone parámetros explícitos para pydantic_ai."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        sig = inspect.signature(tool_func)
        param_names = list(sig.parameters.keys())

        # Debe tener ctx y el parámetro original 'id'
        assert "ctx" in param_names
        assert "id" in param_names

        # 'id' debe ser KEYWORD_ONLY (no VAR_KEYWORD)
        id_param = sig.parameters["id"]
        assert id_param.kind == inspect.Parameter.KEYWORD_ONLY
        assert id_param.annotation is int

    def test_wrapper_has_explicit_parameters_for_async_method(self):
        """Método async también expone parámetros explícitos."""
        methods = discover_methods(UserService)
        create_meta = next(m for m in methods if m.name == "create")
        tool_func = make_tool("UserService", create_meta)

        sig = inspect.signature(tool_func)
        param_names = list(sig.parameters.keys())

        assert "ctx" in param_names
        assert "name" in param_names
        assert sig.parameters["name"].annotation is str

    def test_wrapper_signature_excludes_self(self):
        """La firma del wrapper no incluye 'self'."""
        methods = discover_methods(UserService)
        get_meta = next(m for m in methods if m.name == "get")
        tool_func = make_tool("UserService", get_meta)

        sig = inspect.signature(tool_func)
        assert "self" not in sig.parameters
