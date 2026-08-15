from typing import List, Sequence

from pydantic_ai import Agent, ModelSettings, models
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
    ) -> None:
        """Initializes the orchestrator by building all registered agents."""
        sub_agents: List[SubAgent] = []

        for agent in self.__agents:
            agent.build_agent()
            sub_agents.append(SubAgent(agent.agent.agent))

        self.__agent = Agent(
            model=model,
            capabilities=[SubAgents(agents=sub_agents)]
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

    # -------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------

    async def run(self, message: str):
        """Runs the main agent with the given message."""
        response = await self.agent.run(message)
        return response