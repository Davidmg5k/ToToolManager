from typing import Any, List, Sequence

from pydantic_ai import Agent, models
from pydantic_ai.agent.abstract import AgentMetadata, AgentModelSettings, AgentRetries
from pydantic_ai._instructions import AgentInstructions
from pydantic_ai._agent_graph import EndStrategy
from pydantic_ai.concurrency import AnyConcurrencyLimit
from pydantic_ai.template import TemplateStr
from pydantic_ai_harness.subagents import SubAgent, SubAgents

from to_tool_manager.adapters.fastmcp import build_mcp_server
from to_tool_manager.orchestrator.shared.agent_interface import AgentInterface
from to_tool_manager.orchestrator.events import (
    OrchestratorEvent,
    OrchestratorEventHandler,
    OrchestratorEventType,
)


class AgentOrchestrator:
    """Main orchestrator that manages multiple agents and their sub-agents.

    Supports:
    - Multi-agent management (add, remove, lookup)
    - Lifecycle hooks (startup, shutdown)
    - Event system for observability
    - MCP server exposure

    Example::

        orchestrator = AgentOrchestrator([agent1, agent2])
        orchestrator.init_app(model="openai:gpt-4o")
        response = await orchestrator.run("Create a user named David")
    """

    def __init__(self, agents: List[AgentInterface] | None = None) -> None:
        self.__agents: List[AgentInterface] = agents or []
        self.__agent: Agent | None = None
        self.__event_handlers: List[OrchestratorEventHandler] = []

    @property
    def agent(self) -> Agent:
        """The built main agent.

        Raises:
            RuntimeError: If init_app() has not been called.
        """
        if self.__agent is None:
            raise RuntimeError(
                "Orchestrator not initialized. Call init_app() first."
            )
        return self.__agent

    @property
    def agents(self) -> List[AgentInterface]:
        """List of registered agents (read-only)."""
        return list(self.__agents)

    @property
    def event_handlers(self) -> List[OrchestratorEventHandler]:
        """Registered event handlers (read-only)."""
        return list(self.__event_handlers)

    # -------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------

    async def startup(self) -> None:
        """Executes startup hooks and emits ORCHESTRATOR_STARTED event."""
        await self._emit_event(OrchestratorEvent(
            type=OrchestratorEventType.ORCHESTRATOR_STARTED,
            data={"agents_count": len(self.__agents)},
        ))

    async def shutdown(self) -> None:
        """Executes shutdown hooks and emits ORCHESTRATOR_STOPPED event."""
        await self._emit_event(OrchestratorEvent(
            type=OrchestratorEventType.ORCHESTRATOR_STOPPED,
        ))

    # -------------------------------------------------------------------
    # Agent management
    # -------------------------------------------------------------------

    def init_app(
        self,
        model: models.Model | models.KnownModelName | str,
        *,
        output_type: Any = str,
        instructions: AgentInstructions = None,
        system_prompt: str | Sequence[str] = (),
        deps_type: type | None = None,
        name: str | None = None,
        description: TemplateStr | str | None = None,
        model_settings: AgentModelSettings | None = None,
        retries: int | AgentRetries | None = None,
        validation_context: Any = None,
        defer_model_check: bool = False,
        end_strategy: EndStrategy = "graceful",
        metadata: AgentMetadata | None = None,
        tool_timeout: float | None = None,
        max_concurrency: AnyConcurrencyLimit = None,
    ) -> None:
        """Initializes the orchestrator by building all registered agents.

        Args:
            model: LLM model (e.g. ``"openai:gpt-4o"`` or a
                ``pydantic_ai.models.Model`` instance).
            output_type: Pydantic BaseModel / dataclass / TypedDict /
                ``str`` for structured output.
            instructions: Dynamic instructions (str or callable).
            system_prompt: Static system prompt(s).
            deps_type: Dependency injection type for static typing.
            name: Agent name for logging and tracing.
            description: Human-readable description attached to OTel spans.
            model_settings: Static model settings (temperature, max_tokens,
                etc.).
            retries: Per-category retry budget. ``None`` uses Agent defaults.
            validation_context: Validation context.
            defer_model_check: Defer model evaluation until first run.
            end_strategy: How to handle tool calls alongside final result.
            metadata: Agent metadata.
            tool_timeout: Default timeout in seconds for tool execution.
            max_concurrency: Limit on concurrent agent runs.
        """
        sub_agents: List[SubAgent] = []

        for agent in self.__agents:
            agent.build_agent()
            sub_agents.append(SubAgent(agent.agent.agent))

        agent_kwargs: dict[str, Any] = {}
        if output_type is not str:
            agent_kwargs["output_type"] = output_type
        if instructions is not None:
            agent_kwargs["instructions"] = instructions
        if system_prompt != ():
            agent_kwargs["system_prompt"] = system_prompt
        if deps_type is not None:
            agent_kwargs["deps_type"] = deps_type
        if name is not None:
            agent_kwargs["name"] = name
        if description is not None:
            agent_kwargs["description"] = description
        if model_settings is not None:
            agent_kwargs["model_settings"] = model_settings
        if retries is not None:
            agent_kwargs["retries"] = retries
        if validation_context is not None:
            agent_kwargs["validation_context"] = validation_context
        if defer_model_check:
            agent_kwargs["defer_model_check"] = defer_model_check
        if end_strategy != "graceful":
            agent_kwargs["end_strategy"] = end_strategy
        if metadata is not None:
            agent_kwargs["metadata"] = metadata
        if tool_timeout is not None:
            agent_kwargs["tool_timeout"] = tool_timeout
        if max_concurrency is not None:
            agent_kwargs["max_concurrency"] = max_concurrency

        self.__agent = Agent(
            model=model,
            capabilities=[SubAgents(agents=sub_agents)],
            **agent_kwargs,
        )

    def add_agent(self, agent: AgentInterface) -> None:
        """Adds an agent to the orchestrator.

        Raises:
            ValueError: If the agent is already registered.
        """
        if agent in self.__agents:
            raise ValueError("Agent already registered.")
        self.__agents.append(agent)

    def add_agents(self, agents: List[AgentInterface]) -> None:
        """Adds multiple agents to the orchestrator.

        Raises:
            ValueError: If any of the agents is already registered.
        """
        existing = set(id(a) for a in self.__agents)
        for agent in agents:
            if id(agent) in existing:
                raise ValueError("Agent already registered.")
        self.__agents.extend(agents)

    def has_agent(self, name: str) -> bool:
        """Checks if an agent with the given name is registered."""
        for agent in self.__agents:
            agent_name = getattr(agent, 'name', None)
            if agent_name and agent_name == name:
                return True
        return False

    def get_agent(self, name: str) -> AgentInterface | None:
        """Retrieves an agent by name. Returns None if not found."""
        for agent in self.__agents:
            agent_name = getattr(agent, 'name', None)
            if agent_name and agent_name == name:
                return agent
        return None

    def remove_agent(self, agent: AgentInterface) -> None:
        """Removes an agent from the orchestrator.

        Raises:
            ValueError: If the agent is not found.
        """
        if agent not in self.__agents:
            raise ValueError("Agent not found.")
        self.__agents.remove(agent)
        self.__agent = None

    def clear_agents(self) -> None:
        """Removes all registered agents and invalidates the main agent."""
        self.__agents.clear()
        self.__agent = None

    # -------------------------------------------------------------------
    # Events
    # -------------------------------------------------------------------

    def add_event_handler(self, handler: OrchestratorEventHandler) -> None:
        """Registers an event handler for the orchestrator."""
        self.__event_handlers.append(handler)

    def remove_event_handler(self, handler: OrchestratorEventHandler) -> None:
        """Removes an event handler.

        Raises:
            ValueError: If the handler is not registered.
        """
        if handler not in self.__event_handlers:
            raise ValueError("Handler not registered.")
        self.__event_handlers.remove(handler)

    async def _emit_event(self, event: OrchestratorEvent) -> None:
        """Emits an event to all registered handlers."""
        for handler in self.__event_handlers:
            await handler.on_event(event)

    # -------------------------------------------------------------------
    # MCP
    # -------------------------------------------------------------------

    def expose_as_mcp_server(self, name: str):
        """Exposes the agents as an MCP server."""
        sub_agents = []
        for agent in self.__agents:
            agent.build_agent()
            sub_agents.extend(agent.agent._manager.tool_specs)
        return build_mcp_server(name, sub_agents)
