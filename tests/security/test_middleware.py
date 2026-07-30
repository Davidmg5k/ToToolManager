import pytest
from to_tool_manager.security.middleware import Middleware, ToolMiddleware


class SimpleMiddleware(Middleware):
    def __init__(self):
        self.called = False

    async def dispatch(self, func, /, *args, **kw):
        self.called = True
        return await func(*args, **kw)


class BlockingMiddleware(Middleware):
    async def dispatch(self, func, /, *args, **kw):
        raise PermissionError("Access denied")


class TestMiddleware:
    def test_name_property(self):
        mw = SimpleMiddleware()
        assert mw.name == "SimpleMiddleware"

    @pytest.mark.anyio
    async def test_dispatch(self):
        mw = SimpleMiddleware()

        async def dummy():
            return "ok"

        result = await mw.dispatch(dummy)
        assert result == "ok"
        assert mw.called is True

    @pytest.mark.anyio
    async def test_dispatch_blocks(self):
        mw = BlockingMiddleware()

        async def dummy():
            return "ok"

        with pytest.raises(PermissionError, match="Access denied"):
            await mw.dispatch(dummy)

    def test_call_wraps_dispatch(self):
        mw = SimpleMiddleware()

        async def dummy():
            return "ok"

        wrapped = mw(dummy)
        assert callable(wrapped)


class TestToolMiddleware:
    def test_include(self):
        mw = ToolMiddleware(include=["create", "list"])
        assert mw.is_allowed("create") is True
        assert mw.is_allowed("list") is True
        assert mw.is_allowed("delete") is False

    def test_exclude(self):
        mw = ToolMiddleware(exclude=["delete"])
        assert mw.is_allowed("create") is True
        assert mw.is_allowed("delete") is False

    def test_include_and_exclude(self):
        mw = ToolMiddleware(include=["create", "list", "delete"], exclude=["delete"])
        assert mw.is_allowed("create") is True
        assert mw.is_allowed("list") is True
        assert mw.is_allowed("delete") is False

    def test_no_filters(self):
        mw = ToolMiddleware()
        assert mw.is_allowed("anything") is True

    def test_include_property(self):
        mw = ToolMiddleware(include=["a", "b"])
        assert mw.include == frozenset({"a", "b"})

    def test_exclude_property(self):
        mw = ToolMiddleware(exclude=["c"])
        assert mw.exclude == frozenset({"c"})

    def test_include_none(self):
        mw = ToolMiddleware()
        assert mw.include is None

    def test_exclude_none(self):
        mw = ToolMiddleware()
        assert mw.exclude is None

    def test_is_allowed_with_include(self):
        mw = ToolMiddleware(include=["create"])
        assert mw.is_allowed("create") is True
        assert mw.is_allowed("delete") is False

    def test_is_allowed_with_exclude(self):
        mw = ToolMiddleware(exclude=["delete"])
        assert mw.is_allowed("create") is True
        assert mw.is_allowed("delete") is False

    def test_is_allowed_no_filters(self):
        mw = ToolMiddleware()
        assert mw.is_allowed("anything") is True
