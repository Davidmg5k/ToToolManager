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


class TestBuildAgent:
    """No prior test in this file actually called build_agent() -- these
    close that gap with real (no-mock) Agent construction against
    pydantic-ai's own TestModel. Doubles as regression coverage for:
    - the constructor bug (dynamic system_prompt callable crashing
      Agent.__init__, fixed in this same effort);
    - D5 (Fase 0.4): build_agent() must not build Module.build_tool_spec()
      for Modules it's about to discard from the flat tool list.
    """

    def _service_only_manager(self):
        from to_tool_manager.core.manager import ToToolManager
        from to_tool_manager.core.service import Service

        class Greeter:
            def hello(self, name: str) -> str:
                """Say hello."""
                return f"Hello {name}"

        return ToToolManager([Service(name="greeter", service=Greeter)])

    def test_builds_real_agent_with_service_only_manager(self):
        from pydantic_ai.models.test import TestModel
        from to_tool_manager.adapters.pydantic_ai import build_agent

        manager = self._service_only_manager()
        agent = build_agent(TestModel(), manager)
        assert agent is not None

    def test_built_agent_runs_end_to_end(self):
        from pydantic_ai.models.test import TestModel
        from to_tool_manager.adapters.pydantic_ai import build_agent

        manager = self._service_only_manager()
        agent = build_agent(TestModel(call_tools=[]), manager)

        result = asyncio.run(agent.run("say hi"))
        assert result.output is not None

    def test_build_agent_accepts_sequence_system_prompt_in_gated_branch(self, monkeypatch):
        """Regression guard (pyright reportArgumentType, hallazgo 1.2 #4):
        `system_prompt` is documented to accept `str | Sequence[str]`
        (matching Agent's own constructor), but `_make_gated_system_prompt`
        used to concatenate `base_prompt + "\\n\\n" + ...` directly, which
        raises `TypeError: can only concatenate list (not "str") to list`
        the moment the gated heuristic decides a turn "looks complex" and a
        caller passed a Sequence[str] system_prompt. Force the heuristic to
        fire and confirm no crash."""
        import to_tool_manager.adapters.pydantic_ai as pydantic_ai_adapter
        from pydantic_ai.models.test import TestModel

        monkeypatch.setattr(pydantic_ai_adapter, "request_looks_complex", lambda text, names: True)

        manager = self._service_only_manager()
        agent = pydantic_ai_adapter.build_agent(
            TestModel(call_tools=[]),
            manager,
            system_prompt=["You are helpful.", "Be concise."],
        )

        result = asyncio.run(agent.run("anything"))
        assert result.output is not None

    def test_build_agent_does_not_build_module_tool_spec(self, monkeypatch):
        """D5 regression guard: registering a Module must not trigger
        Module.build_tool_spec() from build_agent() -- Modules go through
        SubAgentCapability (manager.modules directly), never the flat
        tool list, so building their batched ToolSpec here is pure waste
        that gets thrown away."""
        from pydantic_ai.models.test import TestModel
        from to_tool_manager.adapters.pydantic_ai import build_agent
        from to_tool_manager.core.manager import ToToolManager
        from to_tool_manager.core.module import Module
        from to_tool_manager.core.service import Service

        class Greeter:
            def hello(self, name: str) -> str:
                """Say hello."""
                return f"Hello {name}"

        module_service = Service(name="greeter_in_module", service=Greeter)
        module = Module(name="GreeterModule", services=[module_service])
        manager = ToToolManager([module])

        calls = {"count": 0}
        original = Module.build_tool_spec

        def tracking_build_tool_spec(self, *args, **kwargs):
            calls["count"] += 1
            return original(self, *args, **kwargs)

        monkeypatch.setattr(Module, "build_tool_spec", tracking_build_tool_spec)

        build_agent(TestModel(), manager)

        assert calls["count"] == 0, (
            "build_agent() built a Module's batched ToolSpec even though "
            "Modules are handled via SubAgentCapability, not the flat "
            "tool list -- this is exactly the wasted work D5 flagged."
        )

    def test_build_agent_uses_service_specs_not_tool_specs_cache(self):
        """Confirms build_agent() populates manager.service_specs (the
        narrow, Module-free cache) without forcing manager.tool_specs
        (the full cache, which would have built Module specs too) to be
        populated as a side effect."""
        from pydantic_ai.models.test import TestModel
        from to_tool_manager.adapters.pydantic_ai import build_agent
        from to_tool_manager.core.manager import ToToolManager
        from to_tool_manager.core.module import Module
        from to_tool_manager.core.service import Service

        class Greeter:
            def hello(self, name: str) -> str:
                """Say hello."""
                return f"Hello {name}"

        module = Module(name="GreeterModule", services=[Service(name="g", service=Greeter)])
        manager = ToToolManager([module])

        build_agent(TestModel(), manager)

        assert manager._service_specs is not None
        assert manager._specs is None


from unittest.mock import MagicMock
