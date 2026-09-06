import pytest
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
from tests.conftest import ConcreteToolMiddleware


class ConcreteMiddleware(Middleware):
    """Middleware concreto para testing."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestMiddleware:
    """Tests para la clase Middleware base."""

    def test_name_property(self):
        """Middleware tiene nombre"""
        middleware = ConcreteMiddleware()
        assert middleware.name == "ConcreteMiddleware"

    def test_call_returns_callable(self):
        """__call__ retorna un callable"""
        middleware = ConcreteMiddleware()

        async def mock_func(a, b):
            return "result"

        wrapped = middleware(mock_func)
        assert callable(wrapped)


class TestToolMiddleware:
    """Tests para la clase ToolMiddleware."""

    def test_include_filters_methods(self):
        """include solo permite métodos listados"""
        mw = ConcreteToolMiddleware(include=["create", "update"])
        assert mw.is_allowed("create") == True
        assert mw.is_allowed("update") == True
        assert mw.is_allowed("get") == False
        assert mw.is_allowed("delete") == False

    def test_exclude_filters_methods(self):
        """exclude excluye métodos listados"""
        mw = ConcreteToolMiddleware(exclude=["delete"])
        assert mw.is_allowed("create") == True
        assert mw.is_allowed("get") == True
        assert mw.is_allowed("delete") == False

    def test_include_takes_priority(self):
        """include tiene prioridad sobre exclude"""
        mw = ConcreteToolMiddleware(include=["create"], exclude=["create"])
        assert mw.is_allowed("create") == True

    def test_no_filters_allows_all(self):
        """Sin filtros, todos los métodos están permitidos"""
        mw = ConcreteToolMiddleware()
        assert mw.is_allowed("create") == True
        assert mw.is_allowed("get") == True
        assert mw.is_allowed("delete") == True

    def test_include_property_returns_frozenset(self):
        """property include retorna frozenset"""
        mw = ConcreteToolMiddleware(include=["create", "update"])
        assert isinstance(mw.include, frozenset)
        assert mw.include == frozenset({"create", "update"})

    def test_exclude_property_returns_frozenset(self):
        """property exclude retorna frozenset"""
        mw = ConcreteToolMiddleware(exclude=["delete"])
        assert isinstance(mw.exclude, frozenset)
        assert mw.exclude == frozenset({"delete"})

    def test_include_property_none_when_not_set(self):
        """property include es None cuando no está definido"""
        mw = ConcreteToolMiddleware()
        assert mw.include is None

    def test_exclude_property_none_when_not_set(self):
        """property exclude es None cuando no está definido"""
        mw = ConcreteToolMiddleware()
        assert mw.exclude is None
