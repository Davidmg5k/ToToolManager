import pytest
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
from to_tool_manager.infra.types.main.service import Include, Exclude
from tests.conftest import ConcreteToolMiddleware


class TestToolMiddlewareInclude:
    """Tests for include filtering."""

    def test_include_with_list(self):
        """Include with list of strings"""
        mw = ConcreteToolMiddleware(include=["create", "update"])
        assert mw.include == frozenset({"create", "update"})

    def test_include_with_frozenset(self):
        """Include with frozenset"""
        mw = ConcreteToolMiddleware(include=frozenset({"create", "update"}))
        assert mw.include == frozenset({"create", "update"})

    def test_include_with_include_wrapper(self):
        """Include with Include wrapper"""
        wrapper = Include(include=["create", "update"])
        mw = ConcreteToolMiddleware(include=wrapper)
        assert mw.include == frozenset({"create", "update"})

    def test_include_none(self):
        """Include is None when not set"""
        mw = ConcreteToolMiddleware()
        assert mw.include is None

    def test_include_filters_methods(self):
        """include only allows listed methods"""
        mw = ConcreteToolMiddleware(include=["create", "update"])
        assert mw.is_allowed("create") == True
        assert mw.is_allowed("update") == True
        assert mw.is_allowed("get") == False
        assert mw.is_allowed("delete") == False


class TestToolMiddlewareExclude:
    """Tests for exclude filtering."""

    def test_exclude_with_list(self):
        """Exclude with list of strings"""
        mw = ConcreteToolMiddleware(exclude=["delete"])
        assert mw.exclude == frozenset({"delete"})

    def test_exclude_with_frozenset(self):
        """Exclude with frozenset"""
        mw = ConcreteToolMiddleware(exclude=frozenset({"delete"}))
        assert mw.exclude == frozenset({"delete"})

    def test_exclude_with_exclude_wrapper(self):
        """Exclude with Exclude wrapper"""
        wrapper = Exclude(exclude=["delete"])
        mw = ConcreteToolMiddleware(exclude=wrapper)
        assert mw.exclude == frozenset({"delete"})

    def test_exclude_none(self):
        """Exclude is None when not set"""
        mw = ConcreteToolMiddleware()
        assert mw.exclude is None

    def test_exclude_filters_methods(self):
        """exclude excludes listed methods"""
        mw = ConcreteToolMiddleware(exclude=["delete"])
        assert mw.is_allowed("create") == True
        assert mw.is_allowed("get") == True
        assert mw.is_allowed("delete") == False


class TestToolMiddlewarePriority:
    """Tests for include vs exclude priority."""

    def test_include_takes_priority_over_exclude(self):
        """include takes priority over exclude"""
        mw = ConcreteToolMiddleware(include=["create"], exclude=["create"])
        assert mw.is_allowed("create") == True

    def test_include_priority_method_not_in_exclude(self):
        """include allows method not in exclude"""
        mw = ConcreteToolMiddleware(include=["create", "update"], exclude=["update"])
        assert mw.is_allowed("create") == True
        assert mw.is_allowed("update") == True
        assert mw.is_allowed("delete") == False


class TestToolMiddlewareNoFilters:
    """Tests for no filters."""

    def test_no_filters_allows_all(self):
        """Without filters, all methods are allowed"""
        mw = ConcreteToolMiddleware()
        assert mw.is_allowed("create") == True
        assert mw.is_allowed("get") == True
        assert mw.is_allowed("delete") == True
        assert mw.is_allowed("any_method") == True


class TestToolMiddlewareDispatch:
    """Tests for dispatch."""

    def test_dispatch_is_called(self):
        """dispatch is called when using __call__"""
        called = []

        class TestMW(ConcreteToolMiddleware):
            async def dispatch(self, func, /, *args, **kw):
                called.append(True)
                return await func(*args, **kw)

        mw = TestMW()

        async def mock_func():
            return "result"

        wrapped = mw(mock_func)
        assert callable(wrapped)

    def test_name_property(self):
        """ToolMiddleware has name"""
        mw = ConcreteToolMiddleware()
        assert mw.name == "ConcreteToolMiddleware"

    def test_name_from_subclass(self):
        """Subclass preserves name"""
        class MyFilter(ConcreteToolMiddleware):
            pass
        mw = MyFilter()
        assert mw.name == "MyFilter"
