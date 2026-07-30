import pytest
import asyncio
from to_tool_manager.core.types import ToolSpec, ToolResponse, ToolError


async def dummy_tool(operations: list = None) -> ToolResponse:
    return ToolResponse(content={"result": "ok"})


async def failing_tool() -> ToolResponse:
    return ToolResponse(
        error=ToolError(
            category=frozenset({"validation"}),
            message="Invalid input",
            exception_type="ValueError",
            retryable=True,
        )
    )


async def unhandled_failing_tool() -> ToolResponse:
    return ToolResponse(
        error=ToolError(
            category=frozenset({"unclassified"}),
            message="An unexpected error occurred.",
            exception_type="RuntimeError",
            retryable=False,
            handled=False,
        )
    )


@pytest.fixture
def sample_spec():
    return ToolSpec(
        name="TestTool",
        description="A test tool",
        parameters=[],
        call=dummy_tool,
    )


@pytest.fixture
def failing_spec():
    return ToolSpec(
        name="FailingTool",
        description="A failing tool",
        parameters=[],
        call=failing_tool,
    )


@pytest.fixture
def unhandled_spec():
    return ToolSpec(
        name="UnhandledTool",
        description="An unhandled failing tool",
        parameters=[],
        call=unhandled_failing_tool,
    )


class TestFormatCategories:
    def test_empty(self):
        from to_tool_manager.adapters.pydantic_ai import _format_categories
        assert _format_categories(frozenset()) == ""

    def test_single(self):
        from to_tool_manager.adapters.pydantic_ai import _format_categories
        assert _format_categories(frozenset({"not_found"})) == "not_found"

    def test_multiple(self):
        from to_tool_manager.adapters.pydantic_ai import _format_categories
        result = _format_categories(frozenset({"a", "b"}))
        assert "a" in result
        assert "b" in result


class TestFormatError:
    def test_handled_error(self):
        from to_tool_manager.adapters.pydantic_ai import _format_error
        spec = MagicMock()
        error = ToolError(
            category=frozenset({"validation"}),
            message="Bad input",
            exception_type="ValueError",
            retryable=True,
        )
        result = _format_error(spec, error)
        assert "validation" in result
        assert "Bad input" in result

    def test_unhandled_error(self):
        from to_tool_manager.adapters.pydantic_ai import _format_error
        spec = MagicMock()
        error = ToolError(
            category=frozenset(),
            message="Something broke",
            exception_type="RuntimeError",
            handled=False,
        )
        result = _format_error(spec, error)
        assert "Something broke" in result


class TestSerializeContent:
    def test_list_of_dicts(self):
        from to_tool_manager.adapters.pydantic_ai import _serialize_content
        content = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        result = _serialize_content(content)
        assert "|" in result
        assert "Alice" in result

    def test_dict(self):
        from to_tool_manager.adapters.pydantic_ai import _serialize_content
        content = {"key": "value"}
        result = _serialize_content(content)
        assert "key" in result

    def test_string(self):
        from to_tool_manager.adapters.pydantic_ai import _serialize_content
        result = _serialize_content("hello")
        assert result == "hello"

    def test_number(self):
        from to_tool_manager.adapters.pydantic_ai import _serialize_content
        result = _serialize_content(42)
        assert result == "42"


class TestBuildCallable:
    def test_builds_callable(self, sample_spec):
        from to_tool_manager.adapters.pydantic_ai import _build_callable
        func = _build_callable(sample_spec)
        assert callable(func)
        assert func.__name__ == "TestTool"
        assert func.__doc__ == "A test tool"

    @pytest.mark.anyio
    async def test_callable_success(self, sample_spec):
        from to_tool_manager.adapters.pydantic_ai import _build_callable
        func = _build_callable(sample_spec)
        result = await func()
        assert "ok" in result

    @pytest.mark.anyio
    async def test_callable_retryable_error(self, failing_spec):
        from to_tool_manager.adapters.pydantic_ai import _build_callable
        from pydantic_ai import ModelRetry
        func = _build_callable(failing_spec)
        with pytest.raises(ModelRetry):
            await func()

    @pytest.mark.anyio
    async def test_callable_unhandled_error(self, unhandled_spec):
        from to_tool_manager.adapters.pydantic_ai import _build_callable
        func = _build_callable(unhandled_spec)
        result = await func()
        assert "unexpected" in result.lower()


class TestToPydanticAiTools:
    def test_empty(self):
        from to_tool_manager.adapters.pydantic_ai import to_pydantic_ai_tools
        result = to_pydantic_ai_tools([])
        assert result == []

    def test_single_spec(self, sample_spec):
        from to_tool_manager.adapters.pydantic_ai import to_pydantic_ai_tools
        result = to_pydantic_ai_tools([sample_spec])
        assert len(result) == 1
        assert callable(result[0])


class TestToFunctionToolset:
    def test_creates_toolset(self, sample_spec):
        from to_tool_manager.adapters.pydantic_ai import to_function_toolset
        toolset = to_function_toolset([sample_spec])
        assert toolset is not None

    def test_with_instructions(self, sample_spec):
        from to_tool_manager.adapters.pydantic_ai import to_function_toolset
        toolset = to_function_toolset([sample_spec], instructions="Custom instructions")
        assert toolset is not None


from unittest.mock import MagicMock
