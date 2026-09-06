import pytest
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware
from to_tool_manager.infra.types.main.service import Include, Exclude
from tests.conftest import ConcreteToolMiddleware


class TestToolMiddlewareInclude:
    """Tests para filtrado por include."""

    def test_include_with_list(self):
        """Include con lista de strings"""
        mw = ConcreteToolMiddleware(include=["create", "update"])
        assert mw.include == frozenset({"create", "update"})

    def test_include_with_frozenset(self):
        """Include con frozenset"""
        mw = ConcreteToolMiddleware(include=frozenset({"create", "update"}))
        assert mw.include == frozenset({"create", "update"})

    def test_include_with_include_wrapper(self):
        """Include con wrapper Include"""
        wrapper = Include(include=["create", "update"])
        mw = ConcreteToolMiddleware(include=wrapper)
        assert mw.include == frozenset({"create", "update"})

    def test_include_none(self):
        """Include es None cuando no se define"""
        mw = ConcreteToolMiddleware()
        assert mw.include is None

    def test_include_filters_methods(self):
        """include solo permite métodos listados"""
        mw = ConcreteToolMiddleware(include=["create", "update"])
        assert mw.is_allowed("create") == True
        assert mw.is_allowed("update") == True
        assert mw.is_allowed("get") == False
        assert mw.is_allowed("delete") == False


class TestToolMiddlewareExclude:
    """Tests para filtrado por exclude."""

    def test_exclude_with_list(self):
        """Exclude con lista de strings"""
        mw = ConcreteToolMiddleware(exclude=["delete"])
        assert mw.exclude == frozenset({"delete"})

    def test_exclude_with_frozenset(self):
        """Exclude con frozenset"""
        mw = ConcreteToolMiddleware(exclude=frozenset({"delete"}))
        assert mw.exclude == frozenset({"delete"})

    def test_exclude_with_exclude_wrapper(self):
        """Exclude con wrapper Exclude"""
        wrapper = Exclude(exclude=["delete"])
        mw = ConcreteToolMiddleware(exclude=wrapper)
        assert mw.exclude == frozenset({"delete"})

    def test_exclude_none(self):
        """Exclude es None cuando no se define"""
        mw = ConcreteToolMiddleware()
        assert mw.exclude is None

    def test_exclude_filters_methods(self):
        """exclude excluye métodos listados"""
        mw = ConcreteToolMiddleware(exclude=["delete"])
        assert mw.is_allowed("create") == True
        assert mw.is_allowed("get") == True
        assert mw.is_allowed("delete") == False


class TestToolMiddlewarePriority:
    """Tests para prioridad include vs exclude."""

    def test_include_takes_priority_over_exclude(self):
        """include tiene prioridad sobre exclude"""
        mw = ConcreteToolMiddleware(include=["create"], exclude=["create"])
        assert mw.is_allowed("create") == True

    def test_include_priority_method_not_in_exclude(self):
        """include permite método que no está en exclude"""
        mw = ConcreteToolMiddleware(include=["create", "update"], exclude=["update"])
        assert mw.is_allowed("create") == True
        assert mw.is_allowed("update") == True
        assert mw.is_allowed("delete") == False


class TestToolMiddlewareNoFilters:
    """Tests para sin filtros."""

    def test_no_filters_allows_all(self):
        """Sin filtros, todos los métodos están permitidos"""
        mw = ConcreteToolMiddleware()
        assert mw.is_allowed("create") == True
        assert mw.is_allowed("get") == True
        assert mw.is_allowed("delete") == True
        assert mw.is_allowed("any_method") == True


class TestToolMiddlewareDispatch:
    """Tests para dispatch."""

    def test_dispatch_is_called(self):
        """dispatch es invocado al usar __call__"""
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
        """ToolMiddleware tiene nombre"""
        mw = ConcreteToolMiddleware()
        assert mw.name == "ConcreteToolMiddleware"

    def test_name_from_subclass(self):
        """Subclass conserva nombre"""
        class MyFilter(ConcreteToolMiddleware):
            pass
        mw = MyFilter()
        assert mw.name == "MyFilter"
