import pytest
from unittest.mock import patch, MagicMock
from to_tool_manager.core.types import ToolSpec, ToolResponse, ToolError

try:
    from fastmcp import FastMCP
    _has_fastmcp = True
except Exception:
    _has_fastmcp = False


async def dummy_tool(operations: list = None) -> ToolResponse:
    return ToolResponse(content={"result": "ok"})


async def failing_tool() -> ToolResponse:
    return ToolResponse(
        error=ToolError(
            category=frozenset({"validation"}),
            message="Invalid input",
            exception_type="ValueError",
            retryable=True,
            handled=True,
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


class TestFormatCategories:
    def test_empty(self):
        from to_tool_manager.adapters.fastmcp import _format_categories
        assert _format_categories(frozenset()) == ""

    def test_single(self):
        from to_tool_manager.adapters.fastmcp import _format_categories
        assert _format_categories(frozenset({"not_found"})) == "not_found"

    def test_multiple(self):
        from to_tool_manager.adapters.fastmcp import _format_categories
        result = _format_categories(frozenset({"a", "b"}))
        assert "a" in result
        assert "b" in result


class TestSerializeContent:
    def test_list_of_dicts(self):
        from to_tool_manager.adapters.fastmcp import _serialize_content
        content = [{"name": "Alice", "age": 30}]
        result = _serialize_content(content)
        assert "|" in result
        assert "Alice" in result

    def test_dict(self):
        from to_tool_manager.adapters.fastmcp import _serialize_content
        result = _serialize_content({"key": "value"})
        assert "key" in result

    def test_string(self):
        from to_tool_manager.adapters.fastmcp import _serialize_content
        result = _serialize_content("hello")
        assert result == "hello"


class TestBuildCallable:
    def test_builds_callable(self, sample_spec):
        from to_tool_manager.adapters.fastmcp import _build_callable
        func = _build_callable(sample_spec)
        assert callable(func)
        assert func.__name__ == "TestTool"

    @pytest.mark.anyio
    async def test_callable_success(self, sample_spec):
        from to_tool_manager.adapters.fastmcp import _build_callable
        func = _build_callable(sample_spec)
        result = await func()
        assert "ok" in result

    @pytest.mark.anyio
    async def test_callable_handled_error(self, failing_spec):
        from to_tool_manager.adapters.fastmcp import _build_callable
        func = _build_callable(failing_spec)
        result = await func()
        assert "Error" in result
        assert "validation" in result


class TestRegisterOnMcp:
    def test_registers_tools(self, sample_spec):
        from to_tool_manager.adapters.fastmcp import register_on_mcp
        mock_mcp = MagicMock()
        register_on_mcp(mock_mcp, [sample_spec])
        mock_mcp.tool.assert_called_once()

    def test_registers_multiple(self, sample_spec, failing_spec):
        from to_tool_manager.adapters.fastmcp import register_on_mcp
        mock_mcp = MagicMock()
        register_on_mcp(mock_mcp, [sample_spec, failing_spec])
        assert mock_mcp.tool.call_count == 2


@pytest.mark.skipif(not _has_fastmcp, reason="FastMCP server support not installed")
class TestBuildMcpServer:
    def test_builds_server(self, sample_spec):
        from to_tool_manager.adapters.fastmcp import build_mcp_server
        mock_mcp = MagicMock()
        with patch("fastmcp.FastMCP", return_value=mock_mcp):
            result = build_mcp_server("test_server", [sample_spec])
            mock_mcp.tool.assert_called_once()


@pytest.mark.skipif(not _has_fastmcp, reason="FastMCP server support not installed")
class TestBuildMcpAgent:
    def test_builds_agent_no_modules(self, sample_spec):
        from to_tool_manager.adapters.fastmcp import build_mcp_agent
        from to_tool_manager.core.manager import ToToolManager
        from to_tool_manager.core.service import Service

        class Dummy:
            pass

        svc = Service(name="Test", service=Dummy)
        manager = ToToolManager([svc])
        mock_mcp = MagicMock()
        with patch("fastmcp.FastMCP", return_value=mock_mcp):
            result = build_mcp_agent("test_agent", manager)
