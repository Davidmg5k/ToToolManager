import pytest
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
from tests.conftest import ConcreteToolMiddleware


class ConcreteMiddleware(Middleware):
    """Concrete middleware for testing."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestMiddleware:
    """Tests for the base Middleware class."""

    def test_name_property(self):
        """Middleware has name"""
        middleware = ConcreteMiddleware()
        assert middleware.name == "ConcreteMiddleware"

    def test_call_returns_callable(self):
        """__call__ returns a callable"""
        middleware = ConcreteMiddleware()

        async def mock_func(a, b):
            return "result"

        wrapped = middleware(mock_func)
        assert callable(wrapped)


class TestToolMiddleware:
    """Tests for the ToolMiddleware class."""

    def test_include_filters_methods(self):
        """include only allows listed methods"""
        mw = ConcreteToolMiddleware(include=["create", "update"])
        assert mw.is_allowed("create") == True
        assert mw.is_allowed("update") == True
        assert mw.is_allowed("get") == False
        assert mw.is_allowed("delete") == False

    def test_exclude_filters_methods(self):
        """exclude excludes listed methods"""
        mw = ConcreteToolMiddleware(exclude=["delete"])
        assert mw.is_allowed("create") == True
        assert mw.is_allowed("get") == True
        assert mw.is_allowed("delete") == False

    def test_include_takes_priority(self):
        """include takes priority over exclude"""
        mw = ConcreteToolMiddleware(include=["create"], exclude=["create"])
        assert mw.is_allowed("create") == True

    def test_no_filters_allows_all(self):
        """Without filters, all methods are allowed"""
        mw = ConcreteToolMiddleware()
        assert mw.is_allowed("create") == True
        assert mw.is_allowed("get") == True
        assert mw.is_allowed("delete") == True

    def test_include_property_returns_frozenset(self):
        """property include returns frozenset"""
        mw = ConcreteToolMiddleware(include=["create", "update"])
        assert isinstance(mw.include, frozenset)
        assert mw.include == frozenset({"create", "update"})

    def test_exclude_property_returns_frozenset(self):
        """property exclude returns frozenset"""
        mw = ConcreteToolMiddleware(exclude=["delete"])
        assert isinstance(mw.exclude, frozenset)
        assert mw.exclude == frozenset({"delete"})

    def test_include_property_none_when_not_set(self):
        """property include is None when not set"""
        mw = ConcreteToolMiddleware()
        assert mw.include is None

    def test_exclude_property_none_when_not_set(self):
        """property exclude is None when not set"""
        mw = ConcreteToolMiddleware()
        assert mw.exclude is None
