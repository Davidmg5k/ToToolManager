import pytest
from to_tool_manager.adapters.raw import to_openai_tool_schemas, dispatch
from to_tool_manager.core.types import ToolSpec, ToolResponse, ToolError


async def dummy_tool(operations: list = None) -> ToolResponse:
    return ToolResponse(content={"result": "ok"})


@pytest.fixture
def sample_specs():
    return [
        ToolSpec(
            name="TestTool",
            description="A test tool",
            parameters=[],
            call=dummy_tool,
        )
    ]


class TestToOpenaiToolSchemas:
    def test_empty_specs(self):
        result = to_openai_tool_schemas([])
        assert result == []

    def test_basic_tool(self, sample_specs):
        result = to_openai_tool_schemas(sample_specs)
        assert len(result) == 1
        tool = result[0]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "TestTool"
        assert tool["function"]["description"] == "A test tool"

    def test_parameters(self):
        from to_tool_manager.core.types import ParamSpec

        spec = ToolSpec(
            name="WithParams",
            description="Tool with params",
            parameters=[
                ParamSpec(name="name", annotation=str, required=True, description="A name"),
                ParamSpec(name="count", annotation=int, required=False, default=10),
            ],
            call=dummy_tool,
        )
        result = to_openai_tool_schemas([spec])
        params = result[0]["function"]["parameters"]
        assert "name" in params["properties"]
        assert "count" in params["properties"]
        assert "name" in params["required"]
        assert "count" not in params["required"]

    def test_json_type_mapping(self):
        from to_tool_manager.core.types import ParamSpec

        spec = ToolSpec(
            name="TypedTool",
            description="Tool with typed params",
            parameters=[
                ParamSpec(name="items", annotation=list[str], required=True),
                ParamSpec(name="flag", annotation=bool, required=True),
            ],
            call=dummy_tool,
        )
        result = to_openai_tool_schemas([spec])
        props = result[0]["function"]["parameters"]["properties"]
        assert props["items"]["type"] == "array"
        assert props["items"]["items"]["type"] == "string"
        assert props["flag"]["type"] == "boolean"


class TestDispatch:
    @pytest.mark.anyio
    async def test_dispatch_success(self, sample_specs):
        result = await dispatch("TestTool", {}, sample_specs)
        assert result.ok is True
        assert result.content == {"result": "ok"}

    @pytest.mark.anyio
    async def test_dispatch_not_found(self, sample_specs):
        result = await dispatch("Nonexistent", {}, sample_specs)
        assert result.ok is False
        assert result.error is not None

    @pytest.mark.anyio
    async def test_dispatch_multiple_specs(self):
        async def tool_a() -> ToolResponse:
            return ToolResponse(content="a")

        async def tool_b() -> ToolResponse:
            return ToolResponse(content="b")

        specs = [
            ToolSpec(name="ToolA", description="A", parameters=[], call=tool_a),
            ToolSpec(name="ToolB", description="B", parameters=[], call=tool_b),
        ]
        result = await dispatch("ToolB", {}, specs)
        assert result.ok is True
        assert result.content == "b"
