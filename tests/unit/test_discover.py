import pytest
from to_tool_manager.core.main.shared.discover import discover_methods, MethodMeta


class SyncService:
    """Servicio con métodos sync para testing."""

    def create(self, name: str) -> str:
        """Crea un recurso."""
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id}


class AsyncService:
    """Servicio con métodos async para testing."""

    async def create(self, name: str) -> str:
        """Crea un recurso async."""
        return f"Created {name}"

    async def get(self, id: int) -> dict:
        return {"id": id}


class MixedService:
    """Servicio con métodos sync y async."""

    def get(self, id: int) -> dict:
        return {"id": id}

    async def create(self, name: str) -> str:
        return f"Created {name}"


class PrivateMethodService:
    """Servicio con métodos privados."""

    def public_method(self) -> str:
        return "public"

    def _private_method(self) -> str:
        return "private"

    def __dunder_method(self) -> str:
        return "dunder"


class TestDiscoverMethods:
    """Tests para discover_methods."""

    def test_discovers_sync_methods(self):
        """Descubre métodos sync de una clase."""
        methods = discover_methods(SyncService)
        names = [m.name for m in methods]
        assert "create" in names
        assert "get" in names

    def test_discovers_async_methods(self):
        """Descubre métodos async de una clase."""
        methods = discover_methods(AsyncService)
        names = [m.name for m in methods]
        assert "create" in names
        assert "get" in names

    def test_detects_async_methods(self):
        """Detecta correctamente si un método es async."""
        methods = discover_methods(AsyncService)
        for m in methods:
            assert m.is_async is True

    def test_detects_sync_methods(self):
        """Detecta correctamente si un método es sync."""
        methods = discover_methods(SyncService)
        for m in methods:
            assert m.is_async is False

    def test_mixed_service_methods(self):
        """Descubre métodos sync y async en la misma clase."""
        methods = discover_methods(MixedService)
        by_name = {m.name: m for m in methods}
        assert by_name["get"].is_async is False
        assert by_name["create"].is_async is True

    def test_excludes_private_methods(self):
        """Excluye métodos privados."""
        methods = discover_methods(PrivateMethodService)
        names = [m.name for m in methods]
        assert "public_method" in names
        assert "_private_method" not in names

    def test_excludes_dunder_methods(self):
        """Excluye métodos dunder."""
        methods = discover_methods(PrivateMethodService)
        names = [m.name for m in methods]
        assert "__dunder_method" not in names

    def test_extracts_docstring(self):
        """Extrae docstring del método."""
        methods = discover_methods(SyncService)
        by_name = {m.name: m for m in methods}
        assert by_name["create"].docstring == "Crea un recurso."

    def test_excludes_self_from_parameters(self):
        """Excluye 'self' de los parámetros."""
        methods = discover_methods(SyncService)
        by_name = {m.name: m for m in methods}
        assert "self" not in by_name["create"].parameters
        assert "name" in by_name["create"].parameters

    def test_returns_list_of_method_meta(self):
        """Retorna lista de MethodMeta."""
        methods = discover_methods(SyncService)
        assert isinstance(methods, list)
        for m in methods:
            assert isinstance(m, MethodMeta)
