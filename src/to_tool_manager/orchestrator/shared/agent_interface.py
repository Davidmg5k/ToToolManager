from abc import ABC, abstractmethod
from typing import Sequence

from pydantic_ai import models

from to_tool_manager import Middleware
from to_tool_manager.orchestrator.shared.agent_support import AgentSupport


class AgentInterface(ABC):
    """Abstract interface for agents that can be orchestrated.

    Concrete agents must implement _create_plan(), _create_services(),
    and _create_modules() to define their services, modules, and planning.
    """

    def __init__(self, 
        model: models.KnownModelName, 
        middleware: Sequence[Middleware] | None = None,
        *,
        capabilities: list | None = None,
    ):
        """Initializes the agent with the given model and middlewares.

        Args:
            model: Model name to use (e.g., 'openai:gpt-4o').
            middleware: Optional sequence of middlewares to intercept calls.
            capabilities: Optional list of pydantic-ai capabilities (e.g.
                `Planning(...)` from `pydantic_ai_harness.planning` for
                task planning) passed through to the underlying
                `build_agent()` call. `None` (the default) preserves the
                exact behavior this class had before this parameter
                existed. Capabilities can also be added later, before
                `build_agent()` is called, via `self.agent.add_capability(...)`.
        """
        self.__agent_support = AgentSupport(model, middleware, capabilities=capabilities)

    @property
    def agent(self) -> AgentSupport:
        """Access the agent support for advanced configuration."""
        return self.__agent_support

    def build_agent(self) -> None:
        """Builds the agent with its services, modules, and planning.

        This method:
        1. Builds the base agent with the manager
        2. Calls _create_plan() to configure planning
        3. Calls _create_services() to register services
        4. Calls _create_modules() to register modules
        """
        self.__agent_support.build_agent()
        self._create_plan()
        self._create_services()
        self._create_modules()

    @abstractmethod
    def _create_services(self) -> None:
        """Creates and registers the agent's services.

        Implement this method to add services using:
            self.agent.add_service(name, service_class)
        """
        ...

    @abstractmethod
    def _create_modules(self) -> None:
        """Creates and registers the agent's modules.

        Implement this method to add modules using:
            self.agent.add_module(name, services)
        """
        ...

    @abstractmethod
    def _create_plan(self) -> None:
        """Configures the agent's planning.

        Implement this method to configure the execution plan.
        """
        ...