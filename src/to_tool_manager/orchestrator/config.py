from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from pydantic_ai import models


@dataclass
class OrchestratorConfig:
    """Centralized configuration for the orchestrator.

    Allows configuring the model, lifecycle hooks, logging,
    and MCP options in a single place.

    Example::

        config = OrchestratorConfig(
            model="openai:gpt-4o",
            name="my_orchestrator",
            on_startup=my_startup_hook,
            on_shutdown=my_shutdown_hook,
        )
    """
    model: models.KnownModelName
    name: str = "orchestrator"
    description: str = ""

    on_startup: Callable[[], Awaitable[None]] | None = None
    """Async hook executed when the orchestrator starts."""

    on_shutdown: Callable[[], Awaitable[None]] | None = None
    """Async hook executed when the orchestrator stops."""

    enable_logging: bool = True
    log_level: str = "INFO"

    mcp_server_name: str | None = None
    mcp_include_prompts: bool = True

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata for the orchestrator."""