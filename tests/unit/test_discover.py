import pytest
from to_tool_manager.core.main.shared.discover import discover_methods, MethodMeta


class SyncService:
    """Service with sync methods for testing."""

    def create(self, name: str) -> str:
        """Creates a resource."""
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id}


class AsyncService:
    """Service with async methods for testing."""

    async def create(self, name: str) -> str:
        """Creates an async resource."""
        return f"Created {name}"

    async def get(self, id: int) -> dict:
        return {"id": id}


class MixedService:
    """Service with sync and async methods."""

    def get(self, id: int) -> dict:
        return {"id": id}

    async def create(self, name: str) -> str:
        return f"Created {name}"


class PrivateMethodService:
    """Service with private methods."""

    def public_method(self) -> str:
        return "public"

    def _private_method(self) -> str:
        return "private"

    def __dunder_method(self) -> str:
        return "dunder"


class TestDiscoverMethods:
    """Tests for discover_methods."""

    def test_discovers_sync_methods(self):
        """Discovers sync methods from a class."""
        methods = discover_methods(SyncService)
        names = [m.name for m in methods]
        assert "create" in names
        assert "get" in names

    def test_discovers_async_methods(self):
        """Discovers async methods from a class."""
        methods = discover_methods(AsyncService)
        names = [m.name for m in methods]
        assert "create" in names
        assert "get" in names

    def test_detects_async_methods(self):
        """Correctly detects if a method is async."""
        methods = discover_methods(AsyncService)
        for m in methods:
            assert m.is_async is True

    def test_detects_sync_methods(self):
        """Correctly detects if a method is sync."""
        methods = discover_methods(SyncService)
        for m in methods:
            assert m.is_async is False

    def test_mixed_service_methods(self):
        """Discovers sync and async methods in the same class."""
        methods = discover_methods(MixedService)
        by_name = {m.name: m for m in methods}
        assert by_name["get"].is_async is False
        assert by_name["create"].is_async is True

    def test_excludes_private_methods(self):
        """Excludes private methods."""
        methods = discover_methods(PrivateMethodService)
        names = [m.name for m in methods]
        assert "public_method" in names
        assert "_private_method" not in names

    def test_excludes_dunder_methods(self):
        """Excludes dunder methods."""
        methods = discover_methods(PrivateMethodService)
        names = [m.name for m in methods]
        assert "__dunder_method" not in names

    def test_extracts_docstring(self):
        """Extracts docstring from the method."""
        methods = discover_methods(SyncService)
        by_name = {m.name: m for m in methods}
        assert by_name["create"].docstring == "Creates a resource."

    def test_excludes_self_from_parameters(self):
        """Excludes 'self' from parameters."""
        methods = discover_methods(SyncService)
        by_name = {m.name: m for m in methods}
        assert "self" not in by_name["create"].parameters
        assert "name" in by_name["create"].parameters

    def test_returns_list_of_method_meta(self):
        """Returns list of MethodMeta."""
        methods = discover_methods(SyncService)
        assert isinstance(methods, list)
        for m in methods:
            assert isinstance(m, MethodMeta)
