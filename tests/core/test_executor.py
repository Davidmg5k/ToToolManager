import pytest
from to_tool_manager.core.executor import make_safe_caller, _classify
from to_tool_manager.core.types import ErrorMap, ToolResponse


def sync_func(x: int, y: int) -> int:
    return x + y


async def async_func(x: int, y: int) -> int:
    return x + y


def failing_func() -> str:
    raise ValueError("bad input")


async def async_failing_func() -> str:
    raise FileNotFoundError("not found")


def timeout_func() -> str:
    raise TimeoutError("timed out")


class TestClassify:
    def test_no_rules_returns_fallback(self):
        category, retryable, handled = _classify(ValueError("test"), ErrorMap())
        assert category == frozenset({"unclassified"})
        assert retryable is False
        assert handled is False

    def test_error_map_match(self):
        em = ErrorMap().map(ValueError, category="validation")
        category, _, handled = _classify(ValueError("test"), em)
        assert category == frozenset({"validation"})
        assert handled is True

    def test_error_rules_priority(self):
        def my_rule(exc):
            return ("custom", True)

        category, retryable, handled = _classify(
            ValueError("test"), ErrorMap(), error_rules=(my_rule,)
        )
        assert category == frozenset({"custom"})
        assert retryable is True
        assert handled is True

    def test_error_rules_no_match_falls_through(self):
        def my_rule(exc):
            return None

        em = ErrorMap().map(ValueError, category="from_map")
        category, _, handled = _classify(ValueError("test"), em, error_rules=(my_rule,))
        assert category == frozenset({"from_map"})


class TestMakeSafeCaller:
    @pytest.mark.anyio
    async def test_sync_func_success(self):
        caller = make_safe_caller(sync_func)
        result = await caller(x=2, y=3)
        assert isinstance(result, ToolResponse)
        assert result.ok is True
        assert result.content == 5

    @pytest.mark.anyio
    async def test_async_func_success(self):
        caller = make_safe_caller(async_func)
        result = await caller(x=2, y=3)
        assert result.ok is True
        assert result.content == 5

    @pytest.mark.anyio
    async def test_sync_func_error_with_map(self):
        em = ErrorMap().map(ValueError, category="validation", retryable=True)
        caller = make_safe_caller(failing_func, error_map=em)
        result = await caller()
        assert result.ok is False
        assert result.error.category == frozenset({"validation"})
        assert result.error.retryable is True

    @pytest.mark.anyio
    async def test_async_func_error_with_map(self):
        em = ErrorMap().map(FileNotFoundError, category="not_found")
        caller = make_safe_caller(async_failing_func, error_map=em)
        result = await caller()
        assert result.ok is False
        assert result.error.category == frozenset({"not_found"})

    @pytest.mark.anyio
    async def test_unhandled_error_sanitized(self):
        caller = make_safe_caller(failing_func)
        result = await caller()
        assert result.ok is False
        assert "bad input" not in result.error.message
        assert result.error.handled is False

    @pytest.mark.anyio
    async def test_unhandled_error_always_sanitized(self):
        caller = make_safe_caller(failing_func, sanitize_system_errors=False)
        result = await caller()
        assert result.ok is False
        assert "bad input" not in result.error.message
        assert result.error.handled is False

    @pytest.mark.anyio
    async def test_error_rules(self):
        def rule(exc):
            if isinstance(exc, ValueError):
                return ("from_rule", False)
            return None

        caller = make_safe_caller(failing_func, error_rules=(rule,))
        result = await caller()
        assert result.ok is False
        assert result.error.category == frozenset({"from_rule"})

    @pytest.mark.anyio
    async def test_timeout_error(self):
        em = ErrorMap().map(TimeoutError, category="timeout", retryable=True)
        caller = make_safe_caller(timeout_func, error_map=em)
        result = await caller()
        assert result.ok is False
        assert result.error.category == frozenset({"timeout"})
        assert result.error.retryable is True
