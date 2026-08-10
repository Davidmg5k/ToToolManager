import pytest
from to_tool_manager.orchestrator.config import OrchestratorConfig


class TestOrchestratorConfig:
    def test_creation_with_required_fields(self):
        config = OrchestratorConfig(model="openai:gpt-4o")
        assert config.model == "openai:gpt-4o"
        assert config.name == "orchestrator"

    def test_defaults(self):
        config = OrchestratorConfig(model="openai:gpt-4o")
        assert config.name == "orchestrator"
        assert config.description == ""
        assert config.on_startup is None
        assert config.on_shutdown is None
        assert config.enable_logging is True
        assert config.log_level == "INFO"
        assert config.mcp_server_name is None
        assert config.mcp_include_prompts is True
        assert config.metadata == {}

    def test_custom_fields(self):
        async def my_startup():
            pass

        async def my_shutdown():
            pass

        config = OrchestratorConfig(
            model="openai:gpt-4o",
            name="my-orchestrator",
            description="Test orchestrator",
            on_startup=my_startup,
            on_shutdown=my_shutdown,
            enable_logging=False,
            log_level="DEBUG",
            mcp_server_name="test-server",
            mcp_include_prompts=False,
            metadata={"version": "1.0"},
        )
        assert config.name == "my-orchestrator"
        assert config.description == "Test orchestrator"
        assert config.on_startup is my_startup
        assert config.on_shutdown is my_shutdown
        assert config.enable_logging is False
        assert config.log_level == "DEBUG"
        assert config.mcp_server_name == "test-server"
        assert config.mcp_include_prompts is False
        assert config.metadata == {"version": "1.0"}

    def test_model_is_required(self):
        with pytest.raises(TypeError):
            OrchestratorConfig()

    def test_metadata_mutable(self):
        config = OrchestratorConfig(model="openai:gpt-4o")
        config.metadata["key"] = "value"
        assert config.metadata["key"] == "value"