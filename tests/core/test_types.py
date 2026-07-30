import pytest
from to_tool_manager.core.types import (
    ErrorClassification,
    ErrorEntry,
    ErrorMap,
    ParamSpec,
    ToolError,
    ToolResponse,
    OperationSpec,
    ToolSpec,
    _normalize_category,
)


# ---------------------------------------------------------------------------
# _normalize_category
# ---------------------------------------------------------------------------

class TestNormalizeCategory:
    def test_none_returns_empty_frozenset(self):
        assert _normalize_category(None) == frozenset()

    def test_single_string(self):
        assert _normalize_category("not_found") == frozenset({"not_found"})

    def test_list_of_strings(self):
        result = _normalize_category(["a", "b", "c"])
        assert result == frozenset({"a", "b", "c"})

    def test_tuple_of_strings(self):
        result = _normalize_category(("x", "y"))
        assert result == frozenset({"x", "y"})

    def test_frozenset_passthrough(self):
        fs = frozenset({"a"})
        assert _normalize_category(fs) == fs


# ---------------------------------------------------------------------------
# ErrorClassification
# ---------------------------------------------------------------------------

class TestErrorClassification:
    def test_defaults(self):
        ec = ErrorClassification()
        assert ec.category is None
        assert ec.retryable is False
        assert ec.message is None

    def test_with_values(self):
        ec = ErrorClassification(category="not_found", retryable=True, message="Custom msg")
        assert ec.category == "not_found"
        assert ec.retryable is True
        assert ec.message == "Custom msg"

    def test_frozen(self):
        ec = ErrorClassification(category="test")
        with pytest.raises(AttributeError):
            ec.category = "other"


# ---------------------------------------------------------------------------
# ErrorEntry
# ---------------------------------------------------------------------------

class TestErrorEntry:
    def test_normalizes_string_category(self):
        entry = ErrorEntry(category="not_found")
        assert entry.category == frozenset({"not_found"})

    def test_normalizes_list_category(self):
        entry = ErrorEntry(category=["a", "b"])
        assert entry.category == frozenset({"a", "b"})

    def test_frozenset_passthrough(self):
        fs = frozenset({"x"})
        entry = ErrorEntry(category=fs)
        assert entry.category == fs

    def test_retryable_and_message(self):
        entry = ErrorEntry(category="timeout", retryable=True, message="Too slow")
        assert entry.retryable is True
        assert entry.message == "Too slow"


# ---------------------------------------------------------------------------
# ErrorMap
# ---------------------------------------------------------------------------

class TestErrorMap:
    def test_empty_is_falsy(self):
        em = ErrorMap()
        assert not em

    def test_map_adds_entry(self):
        em = ErrorMap().map(ValueError, category="validation")
        assert em
        result = em.classify(ValueError("bad"))
        assert result is not None
        category, retryable, handled = result
        assert category == frozenset({"validation"})
        assert retryable is False
        assert handled is True

    def test_map_with_retryable(self):
        em = ErrorMap().map(TimeoutError, category="timeout", retryable=True)
        category, retryable, handled = em.classify(TimeoutError("timed out"))
        assert retryable is True

    def test_map_entry(self):
        entry = ErrorEntry(category="custom", retryable=True, message="Custom error")
        em = ErrorMap().map_entry(ValueError, entry)
        category, retryable, handled = em.classify(ValueError("bad"))
        assert category == frozenset({"custom"})
        assert retryable is True

    def test_map_callable(self):
        def classifier(exc):
            if "not found" in str(exc):
                return ("not_found", False)
            return None

        em = ErrorMap().map_callable(FileNotFoundError, classifier)
        result = em.classify(FileNotFoundError("file not found"))
        assert result is not None
        assert result[0] == frozenset({"not_found"})

    def test_map_callable_returns_none(self):
        def classifier(exc):
            return None

        em = ErrorMap().map_callable(ValueError, classifier)
        result = em.classify(ValueError("test"))
        assert result is None

    def test_when_predicate(self):
        em = ErrorMap().when(
            lambda e: "timeout" in str(e).lower(),
            category="timeout",
            retryable=True,
        )
        category, retryable, handled = em.classify(TimeoutError("Connection timeout"))
        assert category == frozenset({"timeout"})
        assert retryable is True

    def test_when_predicate_no_match(self):
        em = ErrorMap().when(
            lambda e: "timeout" in str(e).lower(),
            category="timeout",
        )
        result = em.classify(ValueError("other error"))
        assert result is None

    def test_mro_walk(self):
        class CustomError(ValueError):
            pass

        em = ErrorMap().map(ValueError, category="validation")
        category, _, handled = em.classify(CustomError("custom"))
        assert category == frozenset({"validation"})
        assert handled is True

    def test_from_dict_with_string(self):
        em = ErrorMap.from_dict({ValueError: "validation"})
        category, _, handled = em.classify(ValueError("bad"))
        assert category == frozenset({"validation"})
        assert handled is True

    def test_from_dict_with_tuple(self):
        em = ErrorMap.from_dict({ValueError: ("validation", True)})
        category, retryable, _ = em.classify(ValueError("bad"))
        assert retryable is True

    def test_from_dict_with_callable(self):
        em = ErrorMap.from_dict({ValueError: lambda e: ("custom", False)})
        category, _, _ = em.classify(ValueError("bad"))
        assert category == frozenset({"custom"})

    def test_from_dict_with_error_entry(self):
        entry = ErrorEntry(category="from_entry", retryable=True)
        em = ErrorMap.from_dict({ValueError: entry})
        category, retryable, _ = em.classify(ValueError("bad"))
        assert category == frozenset({"from_entry"})
        assert retryable is True

    def test_from_dict_with_error_classification(self):
        ec = ErrorClassification(category="from_class", retryable=False)
        em = ErrorMap.from_dict({ValueError: ec})
        category, _, _ = em.classify(ValueError("bad"))
        assert category == frozenset({"from_class"})

    def test_no_match_returns_none(self):
        em = ErrorMap().map(ValueError, category="test")
        result = em.classify(KeyError("missing"))
        assert result is None


# ---------------------------------------------------------------------------
# ParamSpec
# ---------------------------------------------------------------------------

class TestParamSpec:
    def test_required_param(self):
        p = ParamSpec(name="x", annotation=int, required=True)
        assert p.required is True
        assert p.has_default is False

    def test_optional_param_with_default(self):
        p = ParamSpec(name="x", annotation=int, required=False, default=42)
        assert p.has_default is True
        assert p.default == 42

    def test_description(self):
        p = ParamSpec(name="x", annotation=str, required=True, description="A string")
        assert p.description == "A string"


# ---------------------------------------------------------------------------
# ToolError
# ---------------------------------------------------------------------------

class TestToolError:
    def test_from_exception_handled(self):
        exc = ValueError("bad input")
        err = ToolError.from_exception(exc, category="validation", retryable=True, handled=True)
        assert err.category == frozenset({"validation"})
        assert err.message == "bad input"
        assert err.exception_type == "ValueError"
        assert err.retryable is True
        assert err.handled is True

    def test_from_exception_unhandled_sanitizes_message(self):
        exc = ValueError("secret internal detail")
        err = ToolError.from_exception(exc, handled=False)
        assert "secret internal detail" not in err.message
        assert "ValueError" in err.message
        assert err.handled is False

    def test_from_exception_unhandled_with_custom_message(self):
        exc = ValueError("secret")
        err = ToolError.from_exception(exc, handled=False, message="Safe message")
        assert err.message == "Safe message"

    def test_category_normalization(self):
        err = ToolError(category="test", message="m", exception_type="E")
        assert err.category == frozenset({"test"})


# ---------------------------------------------------------------------------
# ToolResponse
# ---------------------------------------------------------------------------

class TestToolResponse:
    def test_ok_response(self):
        resp = ToolResponse(content={"result": 42})
        assert resp.ok is True
        assert resp.error is None
        assert resp.content == {"result": 42}

    def test_error_response(self):
        err = ToolError(category="test", message="failed", exception_type="E")
        resp = ToolResponse(error=err)
        assert resp.ok is False
        assert resp.error is err


# ---------------------------------------------------------------------------
# OperationSpec
# ---------------------------------------------------------------------------

class TestOperationSpec:
    def test_creation(self):
        op = OperationSpec(
            name="create",
            description="Create an item",
            parameters=(ParamSpec(name="name", annotation=str, required=True),),
        )
        assert op.name == "create"
        assert len(op.parameters) == 1


# ---------------------------------------------------------------------------
# ToolSpec
# ---------------------------------------------------------------------------

class TestToolSpec:
    def test_creation(self):
        async def dummy(**kwargs):
            return ToolResponse(content="ok")

        spec = ToolSpec(
            name="TestTool",
            description="A test tool",
            parameters=(),
            call=dummy,
        )
        assert spec.name == "TestTool"
        assert spec.service_name == ""
        assert spec.metadata == {}
