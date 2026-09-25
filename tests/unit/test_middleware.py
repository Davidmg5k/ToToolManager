import asyncio
from to_tool_manager.core.middleware.middleware import (
    Middleware,
    NodeMiddleware,
    NodeWrapper,
)
from tests.conftest import ConcreteToolMiddleware


class ConcreteMiddleware(Middleware):
    """Concrete middleware for testing."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class SyncDispatchMiddleware(Middleware):
    """Middleware with a synchronous dispatch (returns value directly)."""

    def dispatch(self, func, /, *args, **kw):
        return "direct-result"


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

    def test_call_wraps_async_func_and_executes(self):
        """__call__ wraps an async func and dispatch runs it (middleware.py:37)."""
        middleware = ConcreteMiddleware()

        async def mock_func(a, b):
            return f"result-{a}-{b}"

        wrapped = middleware(mock_func)
        assert asyncio.run(wrapped(1, 2)) == "result-1-2"

    def test_call_wraps_sync_func_and_executes(self):
        """__call__ wraps a sync func; sync path returns its result (middleware.py:32)."""
        middleware = ConcreteMiddleware()

        def mock_func(a, b):
            return f"sync-{a}-{b}"

        wrapped = middleware(mock_func)
        assert asyncio.run(wrapped(1, 2)) == "sync-1-2"

    def test_call_awaits_sync_func_returning_awaitable(self):
        """_to_awaitable awaits a sync func that returns an awaitable (middleware.py:31)."""
        middleware = ConcreteMiddleware()

        def mock_func():
            async def inner():
                return "inner-result"
            return inner()

        wrapped = middleware(mock_func)
        assert asyncio.run(wrapped()) == "inner-result"

    def test_call_sync_dispatch_returns_direct_value(self):
        """sync_wrapper returns the dispatch result when not awaitable (middleware.py:43-45)."""
        middleware = SyncDispatchMiddleware()

        def mock_func():
            return "ignored"

        wrapped = middleware(mock_func)
        assert asyncio.run(wrapped()) == "direct-result"


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


class RecordingNodeMiddleware(NodeMiddleware):
    """NodeMiddleware that records hook calls."""

    def __init__(self):
        self.before_run_calls = 0
        self.after_run_calls = 0

    async def before_run(self, node, ctx):
        self.before_run_calls += 1

    async def after_run(self, node, ctx, next_node):
        self.after_run_calls += 1
        return next_node


class PassiveNodeMiddleware(NodeMiddleware):
    """NodeMiddleware that does NOT override after_run (uses default)."""


class SimpleNode:
    """Simple node that returns an End marker."""

    def __init__(self):
        self.result = "done"

    async def run(self, ctx):
        from pydantic_graph import End
        return End(self.result)


class TestNodeMiddleware:
    """Tests for the NodeMiddleware base class."""

    def test_name_property(self):
        """NodeMiddleware.name returns the class name (middleware.py:181)."""
        mw = RecordingNodeMiddleware()
        assert mw.name == "RecordingNodeMiddleware"

    def test_before_transition_default_true(self):
        """before_transition returns True by default (middleware.py:195)."""
        mw = RecordingNodeMiddleware()
        assert asyncio.run(mw.before_transition("source", "target", None)) is True

    def test_after_run_default_returns_next_node(self):
        """after_run returns the next node by default (middleware.py:212)."""
        from pydantic_graph import End

        mw = PassiveNodeMiddleware()
        end = End("done")
        result = asyncio.run(mw.after_run(SimpleNode(), None, end))
        assert result is end


class TestNodeWrapper:
    """Tests for the NodeWrapper class."""

    def test_run_applies_middlewares_around_node(self):
        """NodeWrapper.run calls before_run/after_run around the node (middleware.py:242-253)."""
        from pydantic_graph import End, GraphRunContext

        mw = RecordingNodeMiddleware()
        WrappedNode = type(
            "WrappedNode",
            (NodeWrapper,),
            {"_wrapped_node_type": SimpleNode, "_middlewares_attr": [mw]},
        )
        ctx = GraphRunContext(state=None, deps=None)
        result = asyncio.run(WrappedNode().run(ctx))
        assert isinstance(result, End)
        assert mw.before_run_calls == 1
        assert mw.after_run_calls == 1
