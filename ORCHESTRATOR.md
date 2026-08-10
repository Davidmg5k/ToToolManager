# Orchestrator Module

The orchestrator module provides a high-level abstraction for managing multiple agents, their lifecycle, and inter-agent coordination in `to_tool_manager`.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Use Cases](#use-cases)
- [When to Use the Orchestrator](#when-to-use-the-orchestrator)
- [When NOT to Use the Orchestrator](#when-not-to-use-the-orchestrator)
- [Migration Guide](#migration-guide)

---

## Overview

The orchestrator solves three main problems:

1. **Multi-agent coordination**: Managing multiple agents that need to work together under a single entry point.
2. **Lifecycle management**: Providing startup/shutdown hooks and event-driven observability.
3. **Simplified deployment**: Exposing multiple agents as a single MCP server or web endpoint.

### Key Components

| Component | Purpose |
|-----------|---------|
| `AgentOrchestrator` | Main class that coordinates multiple agents |
| `AgentInterface` | Abstract base class for agents that can be orchestrated |
| `AgentSupport` | Helper class for building agents with services and modules |
| `OrchestratorConfig` | Centralized configuration for the orchestrator |
| `OrchestratorBuilder` | Fluent builder pattern for complex configurations |
| `OrchestratorEvent` / `OrchestratorEventHandler` | Event system for observability |

---

## Architecture

```
+-----------------------------------------------------------------------+
|                          AgentOrchestrator                             |
|                                                                       |
|  agents:                                                              |
|    +-- AgentInterface_1  --> AgentSupport --> [Service A, Service B]  |
|    +-- AgentInterface_2  --> AgentSupport --> [Service C]             |
|    +-- AgentInterface_3  --> AgentSupport --> [Module D]              |
|                                                                       |
|  event_handlers:                                                      |
|    +-- LoggingHandler                                                |
|    +-- MetricsHandler                                                 |
|                                                                       |
|  init_app(model) --> Agent (pydantic-ai)                              |
|    +-- SubAgents([agent1.agent, agent2.agent, agent3.agent])          |
+-----------------------------------------------------------------------+
```

---

## Quick Start

### Basic Usage

```python
from to_tool_manager import Service, ToToolManager
from to_tool_manager.orchestrator import AgentOrchestrator, AgentInterface

# 1. Define your service classes
class OrderService:
    def create(self, product: str) -> str:
        return f"Order for {product} created"

class UserService:
    def create_user(self, name: str) -> str:
        return f"User {name} created"

# 2. Create agents implementing AgentInterface
class OrderAgent(AgentInterface):
    def __init__(self):
        super().__init__(model="openai:gpt-4o")

    def _create_services(self):
        self.agent.add_service("Order", OrderService)

    def _create_modules(self):
        pass

    def _create_plan(self):
        pass

class UserAgent(AgentInterface):
    def __init__(self):
        super().__init__(model="openai:gpt-4o")

    def _create_services(self):
        self.agent.add_service("User", UserService)

    def _create_modules(self):
        pass

    def _create_plan(self):
        pass

# 3. Create and initialize the orchestrator
orchestrator = AgentOrchestrator([OrderAgent(), UserAgent()])
orchestrator.init_app(model="openai:gpt-4o")

# 4. Run
response = await orchestrator.run("Create an order for laptop")
```

### Using the Builder

```python
from to_tool_manager.orchestrator import OrchestratorBuilder

orchestrator = (
    OrchestratorBuilder()
    .model("openai:gpt-4o")
    .agent(OrderAgent())
    .agent(UserAgent())
    .build()
)
orchestrator.init_app("openai:gpt-4o")
```

### Using Configuration

```python
from to_tool_manager.orchestrator import OrchestratorConfig, AgentOrchestrator

async def on_startup():
    print("Orchestrator starting...")

async def on_shutdown():
    print("Orchestrator stopping...")

config = OrchestratorConfig(
    model="openai:gpt-4o",
    name="my-orchestrator",
    on_startup=on_startup,
    on_shutdown=on_shutdown,
    enable_logging=True,
)

# Use config with builder or directly
orchestrator = AgentOrchestrator([OrderAgent(), UserAgent()])
await orchestrator.startup()
orchestrator.init_app(config.model)
# ... run ...
await orchestrator.shutdown()
```

---

## API Reference

### AgentOrchestrator

The main orchestrator class.

```python
class AgentOrchestrator:
    def __init__(self, agents: List[AgentInterface] | None = None):
        """Initialize with a list of agents."""

    @property
    def agent(self) -> Agent:
        """The built main agent. Raises RuntimeError if not initialized."""

    @property
    def agents(self) -> List[AgentInterface]:
        """List of registered agents (read-only)."""

    def init_app(self, model: models.KnownModelName) -> None:
        """Initialize the orchestrator by building all registered agents."""

    # Agent management
    def add_agent(self, agent: AgentInterface) -> None:
        """Add an agent. Raises ValueError if already registered."""

    def add_agents(self, agents: List[AgentInterface]) -> None:
        """Add multiple agents."""

    def has_agent(self, name: str) -> bool:
        """Check if an agent with the given name is registered."""

    def get_agent(self, name: str) -> AgentInterface | None:
        """Get an agent by name. Returns None if not found."""

    def remove_agent(self, agent: AgentInterface) -> None:
        """Remove an agent. Raises ValueError if not found."""

    def clear_agents(self) -> None:
        """Remove all agents and invalidate the main agent."""

    # Lifecycle
    async def startup(self) -> None:
        """Execute startup hooks and emit ORCHESTRATOR_STARTED event."""

    async def shutdown(self) -> None:
        """Execute shutdown hooks and emit ORCHESTRATOR_STOPPED event."""

    # Events
    def add_event_handler(self, handler: OrchestratorEventHandler) -> None:
        """Register an event handler."""

    def remove_event_handler(self, handler: OrchestratorEventHandler) -> None:
        """Remove an event handler."""

    # MCP
    def expose_as_mcp_server(self, name: str):
        """Expose agents as an MCP server."""

    # Execution
    async def run(self, message: str):
        """Run the main agent with the given message."""
```

### AgentInterface

Abstract base class for agents that can be orchestrated.

```python
class AgentInterface(ABC):
    def __init__(self, model: models.KnownModelName, middleware: Sequence[Middleware] | None = None):
        """Initialize with model and optional middlewares."""

    @property
    def agent(self) -> AgentSupport:
        """Access the agent support for advanced configuration."""

    def build_agent(self) -> None:
        """Build the agent with services, modules, and planning."""

    @abstractmethod
    def _create_services(self) -> None:
        """Create and register the agent's services."""

    @abstractmethod
    def _create_modules(self) -> None:
        """Create and register the agent's modules."""

    @abstractmethod
    def _create_plan(self) -> None:
        """Configure the agent's planning."""
```

### OrchestratorEvent

```python
class OrchestratorEventType(str, Enum):
    AGENT_ADDED = "agent_added"
    AGENT_REMOVED = "agent_removed"
    AGENT_INITIALIZED = "agent_initialized"
    ORCHESTRATOR_STARTED = "orchestrator_started"
    ORCHESTRATOR_STOPPED = "orchestrator_stopped"

@dataclass(frozen=True, slots=True)
class OrchestratorEvent:
    type: OrchestratorEventType
    timestamp: datetime
    data: dict[str, Any]
```

---

## Use Cases

### Use Case 1: Multi-Tenant Agent System

**Scenario**: You need to serve multiple tenants, each with its own isolated agent configuration, but expose them through a single endpoint.

```python
class TenantAgent(AgentInterface):
    def __init__(self, tenant_id: str, model: str):
        super().__init__(model=model)
        self.tenant_id = tenant_id

    def _create_services(self):
        # Each tenant gets its own service instances
        self.agent.add_service("Order", OrderService(tenant=self.tenant_id))
        self.agent.add_service("User", UserService(tenant=self.tenant_id))

    def _create_modules(self):
        pass

    def _create_plan(self):
        pass

# Create orchestrator with tenant agents
orchestrator = AgentOrchestrator([
    TenantAgent(tenant_id="tenant-a", model="openai:gpt-4o"),
    TenantAgent(tenant_id="tenant-b", model="openai:gpt-4o-mini"),
])

# Expose as MCP server
mcp_server = orchestrator.expose_as_mcp_server("multi-tenant-service")
mcp_server.run()
```

**Benefits**:
- Single deployment for all tenants
- Per-tenant model selection
- Easy to add/remove tenants dynamically

---

### Use Case 2: Specialized Agent Team with Event Logging

**Scenario**: You have specialized agents for different domains (commerce, analytics, notifications) and need to track all agent activity for auditing.

```python
import logging

logger = logging.getLogger("orchestrator")

class AuditEventHandler:
    async def on_event(self, event: OrchestratorEvent) -> None:
        logger.info(f"[AUDIT] {event.type.value} at {event.timestamp}")
        if event.data:
            logger.info(f"[AUDIT] Data: {event.data}")

class CommerceAgent(AgentInterface):
    def __init__(self):
        super().__init__(model="openai:gpt-4o")

    def _create_services(self):
        self.agent.add_service("Order", OrderService)
        self.agent.add_service("Product", ProductService)

    def _create_modules(self):
        pass

    def _create_plan(self):
        pass

class AnalyticsAgent(AgentInterface):
    def __init__(self):
        super().__init__(model="openai:gpt-4o")

    def _create_services(self):
        self.agent.add_service("Analytics", AnalyticsService)

    def _create_modules(self):
        pass

    def _create_plan(self):
        pass

class NotificationAgent(AgentInterface):
    def __init__(self):
        super().__init__(model="openai:gpt-4o-mini")

    def _create_services(self):
        self.agent.add_service("Email", EmailService)
        self.agent.add_service("SMS", SMSService)

    def _create_modules(self):
        pass

    def _create_plan(self):
        pass

# Create orchestrator with event logging
orchestrator = AgentOrchestrator([
    CommerceAgent(),
    AnalyticsAgent(),
    NotificationAgent(),
])
orchestrator.add_event_handler(AuditEventHandler())

await orchestrator.startup()
orchestrator.init_app("openai:gpt-4o")

# All activity is now logged
response = await orchestrator.run("Create an order and send confirmation email")

await orchestrator.shutdown()
```

**Benefits**:
- Complete audit trail of orchestrator lifecycle
- Easy to add monitoring, metrics, or alerting
- Decoupled logging from business logic

---

### Use Case 3: Dynamic Agent Management

**Scenario**: You need to add and remove agents at runtime based on user subscription or feature flags.

```python
from to_tool_manager.orchestrator import AgentOrchestrator, AgentInterface

class BaseAgent(AgentInterface):
    def __init__(self, model: str = "openai:gpt-4o-mini"):
        super().__init__(model=model)

    def _create_services(self):
        self.agent.add_service("Core", CoreService)

    def _create_modules(self):
        pass

    def _create_plan(self):
        pass

class PremiumAgent(AgentInterface):
    def __init__(self):
        super().__init__(model="openai:gpt-4o")

    def _create_services(self):
        self.agent.add_service("Premium", PremiumService)
        self.agent.add_service("AdvancedAnalytics", AnalyticsService)

    def _create_modules(self):
        pass

    def _create_plan(self):
        pass

class EnterpriseAgent(AgentInterface):
    def __init__(self):
        super().__init__(model="openai:gpt-4o")

    def _create_services(self):
        self.agent.add_service("Enterprise", EnterpriseService)
        self.agent.add_service("CustomIntegrations", IntegrationService)

    def _create_modules(self):
        pass

    def _create_plan(self):
        pass

# Start with base agent only
orchestrator = AgentOrchestrator([BaseAgent()])
orchestrator.init_app("openai:gpt-4o-mini")

# User upgrades to premium
premium_agent = PremiumAgent()
orchestrator.add_agent(premium_agent)
orchestrator.init_app("openai:gpt-4o")  # Reinitialize with better model

# User downgrades
orchestrator.remove_agent(premium_agent)
orchestrator.init_app("openai:gpt-4o-mini")  # Reinitialize with cheaper model

# Check what's available
if orchestrator.has_agent("Premium"):
    print("Premium features available")
```

**Benefits**:
- Runtime flexibility without restarts
- Pay-per-use model selection
- Easy A/B testing of agent configurations

---

### Use Case 4: Agent Pipeline with Lifecycle Hooks

**Scenario**: You need to perform setup/teardown operations when the orchestrator starts/stops (e.g., connect to databases, warm caches).

```python
import asyncio
from to_tool_manager.orchestrator import AgentOrchestrator, AgentInterface

class DatabaseAgent(AgentInterface):
    def __init__(self):
        super().__init__(model="openai:gpt-4o")
        self.db_pool = None

    async def connect(self):
        """Connect to database on startup."""
        self.db_pool = await create_db_pool()
        self.agent.add_service("DB", DatabaseService(self.db_pool))

    async def disconnect(self):
        """Disconnect from database on shutdown."""
        if self.db_pool:
            await self.db_pool.close()

    def _create_services(self):
        pass  # Services added in connect()

    def _create_modules(self):
        pass

    def _create_plan(self):
        pass

class CacheAgent(AgentInterface):
    def __init__(self):
        super().__init__(model="openai:gpt-4o")
        self.cache = None

    async def connect(self):
        """Warm up cache on startup."""
        self.cache = await create_cache_client()
        await self.cache.warm_up()
        self.agent.add_service("Cache", CacheService(self.cache))

    async def disconnect(self):
        """Flush and close cache on shutdown."""
        if self.cache:
            await self.cache.flush()
            await self.cache.close()

    def _create_services(self):
        pass

    def _create_modules(self):
        pass

    def _create_plan(self):
        pass

# Create agents
db_agent = DatabaseAgent()
cache_agent = CacheAgent()

# Create orchestrator
orchestrator = AgentOrchestrator([db_agent, cache_agent])

# Startup: connect to services
await db_agent.connect()
await cache_agent.connect()
orchestrator.init_app("openai:gpt-4o")

# Run
response = await orchestrator.run("Query user data")

# Shutdown: disconnect cleanly
await db_agent.disconnect()
await cache_agent.disconnect()
```

**Benefits**:
- Clean resource management
- Proper initialization order
- Graceful shutdown

---

## When to Use the Orchestrator

### Use the Orchestrator When:

| Scenario | Why the Orchestrator Helps |
|----------|---------------------------|
| **Multiple agents need a single entry point** | The orchestrator provides a unified API and can expose all agents as one MCP server |
| **You need lifecycle management** | Startup/shutdown hooks ensure proper resource initialization and cleanup |
| **You need observability across agents** | The event system tracks all agent activity in one place |
| **Agents have different models** | Each agent can use a different model (e.g., GPT-4 for complex tasks, GPT-4o-mini for simple ones) |
| **Dynamic agent registration** | Add/remove agents at runtime without restarting |
| **Multi-tenant systems** | Each tenant gets its own agent configuration through a shared orchestrator |
| **Complex agent teams** | Coordinate specialized agents (commerce, analytics, notifications) under one roof |
| **A/B testing agent configurations** | Easily swap agents and compare performance |

### Specific Patterns:

1. **Microservices with AI**: Each microservice gets its own agent, orchestrator provides the gateway.
2. **Feature-flagged agents**: Enable/disable premium features by adding/removing agents.
3. **Cost optimization**: Use cheaper models for simple tasks, expensive models for complex ones.
4. **Audit and compliance**: Track all AI interactions through the event system.

---

## When NOT to Use the Orchestrator

### Do NOT Use the Orchestrator When:

| Scenario | Why It's Not Needed | Alternative |
|----------|---------------------|-------------|
| **Single agent, single service** | Overhead without benefit | Use `ToToolManager` + `build_agent()` directly |
| **Simple tool registration** | No need for agent coordination | Use `ToToolManager` directly |
| **Framework-specific features only** | Orchestrator adds abstraction layer | Use the adapter directly (e.g., `adapters.pydantic_ai`) |
| **Performance-critical paths** | Extra indirection adds latency | Use `ToToolManager` + raw dispatch |
| **One-off scripts** | No lifecycle management needed | Use `build_agent()` directly |
| **Pure function calling** | No agent coordination needed | Use `ToToolManager` + raw adapters |

### Specific Anti-Patterns:

1. **Single service, single agent**: Just use `ToToolManager` + `build_agent()`.
2. **No need for multi-agent coordination**: The orchestrator adds unnecessary complexity.
3. **Simple MCP server**: Use `build_mcp_server()` directly without the orchestrator.
4. **Performance-critical paths**: The orchestrator adds a layer of indirection.

### Decision Matrix:

```
Do you have multiple agents?
  NO  -> Don't use orchestrator
  YES -> Do you need lifecycle management?
    NO  -> Consider if you really need the orchestrator
    YES -> Do you need event handling/observability?
      NO  -> Maybe just use agent composition
      YES -> Use the orchestrator
```

---

## Migration Guide

### From Direct Agent Usage

**Before:**

```python
from to_tool_manager import Service, ToToolManager
from to_tool_manager.adapters.pydantic_ai import build_agent

manager = ToToolManager([
    Service(name="Order", service=OrderService),
    Service(name="User", service=UserService),
])
agent = build_agent("openai:gpt-4o", manager)
result = await agent.run("Create an order")
```

**After:**

```python
from to_tool_manager import Service, ToToolManager
from to_tool_manager.orchestrator import AgentOrchestrator, AgentInterface

class BusinessAgent(AgentInterface):
    def __init__(self):
        super().__init__(model="openai:gpt-4o")

    def _create_services(self):
        self.agent.add_service("Order", OrderService)
        self.agent.add_service("User", UserService)

    def _create_modules(self):
        pass

    def _create_plan(self):
        pass

orchestrator = AgentOrchestrator([BusinessAgent()])
orchestrator.init_app("openai:gpt-4o")
result = await orchestrator.run("Create an order")
```

### From Multiple Agents

**Before:**

```python
agent1 = build_agent("openai:gpt-4o", manager1)
agent2 = build_agent("openai:gpt-4o-mini", manager2)

# Manual coordination
result1 = await agent1.run("task1")
result2 = await agent2.run("task2")
```

**After:**

```python
from to_tool_manager.orchestrator import AgentOrchestrator, AgentInterface

class Agent1(AgentInterface):
    def __init__(self):
        super().__init__(model="openai:gpt-4o")
    def _create_services(self):
        self.agent.add_service("Service1", Service1)
    def _create_modules(self):
        pass
    def _create_plan(self):
        pass

class Agent2(AgentInterface):
    def __init__(self):
        super().__init__(model="openai:gpt-4o-mini")
    def _create_services(self):
        self.agent.add_service("Service2", Service2)
    def _create_modules(self):
        pass
    def _create_plan(self):
        pass

orchestrator = AgentOrchestrator([Agent1(), Agent2()])
orchestrator.init_app("openai:gpt-4o")

# Single entry point for all agents
result = await orchestrator.run("task1")
```

---

## Additional Resources

- [Main README](README.md) - Full documentation of `to_tool_manager`
- [Examples](example/) - Complete example applications