"""
System Tests - Requirements Level (V Model)
============================================

Requirements↔Test Traceability Matrix (RTM):
- REQ-001: Service creates tools from public methods
- REQ-002: Module groups services as sub-agent
- REQ-003: ToToolManager orchestrates services and modules
- REQ-004: TTMBuilder provides fluent API to build agents
- REQ-005: Middleware is applied in correct chain
- REQ-006: ToolMiddleware filters methods by include/exclude
- REQ-007: disable_middlewares excludes specific middlewares
- REQ-008: to_mcp_tool() converts to MCP server

Validation order by blast radius (axioma-auditoria):
1. DinamicDepend (leaf - blast radius=0)
2. Service.build_as_capability (boundary)
3. Module.build_as_agent (boundary)
4. ToToolManager.build_agent (package level)
5. TTMBuilder.build + Agent.run (requirements level - WITH LLM)

Test model: groq:openai/gpt-oss-120b
"""

import pytest
from dotenv import load_dotenv
from pydantic_ai import Agent

from to_tool_manager.core.builder.ttm_builder import TTMBuilder
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware


load_dotenv()

# ============================================================
# GLOBAL MODEL FOR SYSTEM TESTS
# ============================================================
TEST_MODEL = "groq:openai/gpt-oss-120b"


# ============================================================
# EXAMPLE SERVICES
# ============================================================

class FakeOrderDB:
    """Fake database for orders."""

    def __init__(self):
        self.orders = {
            "ORD-001": {"status": "shipped", "tracking": "TRK-123", "dest": "Bogota"},
            "ORD-002": {"status": "processing", "tracking": None, "dest": "Medellin"},
            "ORD-003": {"status": "delivered", "tracking": "TRK-456", "dest": "Cali"},
        }

    def get(self, order_id: str) -> dict | None:
        return self.orders.get(order_id)


class OrderService:
    """Order service for testing."""

    def __init__(self, db: FakeOrderDB):
        self.db = db

    def get_status(self, order_id: str) -> str:
        """Gets the status of an order."""
        order = self.db.get(order_id)
        if not order:
            return f"Order {order_id} not found"
        return f"Order {order_id}: status={order['status']}, dest={order['dest']}"

    def get_tracking(self, order_id: str) -> str:
        """Gets the tracking of an order."""
        order = self.db.get(order_id)
        if not order:
            return f"Order {order_id} not found"
        if not order["tracking"]:
            return f"Order {order_id}: no tracking available"
        return f"Order {order_id}: tracking={order['tracking']}"


class RefundService:
    """Refund service for testing."""

    def status(self, order_id: str) -> str:
        """Refund status."""
        return f"Refund for {order_id}: pending review"

    def issue(self, order_id: str, reason: str) -> str:
        """Issue refund."""
        return f"Refund issued for {order_id}. Reason: {reason}"


class UserService:
    """User service for testing."""

    def create(self, name: str) -> str:
        """Creates a user."""
        return f"User {name} created"

    def get(self, user_id: int) -> dict:
        """Gets a user."""
        return {"id": user_id, "name": f"User_{user_id}"}


# ============================================================
# EXAMPLE MIDDLEWARES
# ============================================================

class AuthMiddleware(ToolMiddleware):
    """Authentication middleware."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class LogMiddleware(Middleware):
    """Logging middleware."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class ValidationMiddleware(ToolMiddleware):
    """Validation middleware."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


# ============================================================
# LEVEL 1: UNIT TESTS (boundary - low blast radius)
# REQ-001, REQ-006, REQ-007
# ============================================================

class TestServiceBuildCapability:
    """Unit tests for Service.build_as_capability()."""

    def test_service_creates_capability(self):
        """REQ-001: Service returns Capability with tools."""
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Order management"
        )
        capability = service.build_as_capability()
        assert capability is not None
        assert capability.id == "Order"

    def test_service_discovers_methods(self):
        """REQ-001: Service discovers public methods."""
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Order management"
        )
        capability = service.build_as_capability()
        tool_names = [t.name for t in capability.tools]
        assert "get_status" in tool_names
        assert "get_tracking" in tool_names

    def test_service_with_middleware(self):
        """REQ-006: Service applies ToolMiddleware."""
        mw = AuthMiddleware(include=["get_status"])
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Order management",
            middleware=[mw]
        )
        capability = service.build_as_capability()
        assert len(capability.tools) == 2

    def test_service_with_constructor_args(self):
        """REQ-001: Service accepts args for constructor."""
        db = FakeOrderDB()
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Order management",
            args=(db,)
        )
        capability = service.build_as_capability()
        assert capability is not None


# ============================================================
# LEVEL 2: INTEGRATION TESTS (package level)
# REQ-002, REQ-003, REQ-005
# ============================================================

class TestModuleIntegration:
    """Integration tests for Module."""

    def test_module_builds_subagent(self):
        """REQ-002: Module builds SubAgent."""
        db = FakeOrderDB()
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Order management",
            args=(db,)
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module"
        )
        subagent = module.build_as_agent()
        assert subagent is not None

    def test_module_applies_middlewares(self):
        """REQ-005: Module applies middlewares to services."""
        db = FakeOrderDB()
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Order management",
            args=(db,)
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            middleware=[LogMiddleware()]
        )
        module.build_as_agent()
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)

    def test_module_disable_middlewares(self):
        """REQ-007: Module respects Service's disable_middlewares."""
        db = FakeOrderDB()
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Order management",
            args=(db,),
            disable_middlewares=("AuthMiddleware",)
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module",
            middleware=[AuthMiddleware(), LogMiddleware()],
        )
        module.build_as_agent()
        assert not any(isinstance(mw, AuthMiddleware) for mw in service.middleware)
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)


class TestToToolManagerIntegration:
    """Integration tests for ToToolManager."""

    def test_manager_builds_agent(self):
        """REQ-003: ToToolManager builds Agent."""
        db = FakeOrderDB()
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Order management",
            args=(db,)
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service]
        )
        agent = manager.build_agent()
        assert agent is not None
        assert agent.name == "TestManager"

    def test_manager_with_module(self):
        """REQ-003: ToToolManager works with modules."""
        db = FakeOrderDB()
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Order management",
            args=(db,)
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module"
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[module]
        )
        agent = manager.build_agent()
        assert agent is not None

    def test_manager_resolve_middlewares(self):
        """REQ-005: ToToolManager resolves middlewares correctly."""
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Order management"
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service],
            middlewares=[AuthMiddleware(), LogMiddleware()]
        )
        resolved = manager._resolve_middlewares(service)
        assert len(resolved) == 2

    def test_manager_disable_middlewares(self):
        """REQ-007: ToToolManager excludes disabled middlewares."""
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Order management",
            disable_middlewares=("AuthMiddleware",)
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service],
            middlewares=[AuthMiddleware(), LogMiddleware()]
        )
        resolved = manager._resolve_middlewares(service)
        assert not any(m.name == "AuthMiddleware" for m in resolved)
        assert any(m.name == "LogMiddleware" for m in resolved)


# ============================================================
# LEVEL 3: SYSTEM TESTS (requirements level - WITH LLM)
# REQ-004, REQ-008
# ============================================================

class TestTTMBuilderWithLLM:
    """System tests for TTMBuilder with groq:openai/gpt-oss-120b."""

    def test_builder_creates_agent_with_model(self):
        """REQ-004: TTMBuilder creates Agent with specified model."""
        builder = TTMBuilder(name="TestAgent")
        builder.add_service(
            name="orders",
            service=OrderService,
            instructions="Order management. Use get_status to check status.",
            args=(FakeOrderDB(),)
        )
        builder.build(TEST_MODEL)
        assert builder.agent is not None
        assert builder.agent.name == "TestAgent"

    def test_builder_fluent_api_with_model(self):
        """REQ-004: TTMBuilder fluent API works with model."""
        builder = (
            TTMBuilder(name="FluentAgent")
            .add_service(
                name="orders",
                service=OrderService,
                instructions="Order management",
                args=(FakeOrderDB(),)
            )
            .add_service(
                name="refunds",
                service=RefundService,
                instructions="Refund management"
            )
        )
        builder.build(TEST_MODEL)
        assert builder.agent is not None

    def test_builder_with_module_and_model(self):
        """REQ-004: TTMBuilder works with modules and model."""
        service = Service(
            name="orders",
            service=OrderService,
            instructions="Order management",
            args=(FakeOrderDB(),)
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Commerce module"
        )
        builder = TTMBuilder(name="ModuleAgent")
        builder.add_module(
            name="Commerce",
            services=[service],
            description="Commerce module"
        )
        builder.build(TEST_MODEL)
        assert builder.agent is not None

    def test_builder_context_manager_with_model(self):
        """REQ-004: Context manager works with model."""
        with TTMBuilder(name="ContextAgent") as builder:
            builder.add_service(
                name="orders",
                service=OrderService,
                instructions="Order management",
                args=(FakeOrderDB(),)
            )
        # build() is called automatically in __exit__
        assert builder.agent is not None

    def test_to_mcp_tool(self):
        """REQ-008: to_mcp_tool() creates MCP server."""
        from fastmcp import FastMCP

        builder = TTMBuilder(name="MCPAgent")
        builder.add_service(
            name="orders",
            service=OrderService,
            instructions="Order management",
            args=(FakeOrderDB(),)
        )
        builder.build(TEST_MODEL)

        mcp_app = builder.to_mcp_tool(
            name="OrderMCP",
            instructions="Order MCP server"
        )
        assert isinstance(mcp_app, FastMCP)
        assert mcp_app.name == "OrderMCP"


class TestAgentExecutionWithLLM:
    """Real agent execution tests with groq:openai/gpt-oss-120b."""

    @pytest.mark.asyncio
    async def test_agent_runs_with_tool_call(self):
        """REQ-003+REQ-004: Agent executes real tool with LLM."""
        db = FakeOrderDB()
        builder = TTMBuilder(name="ExecAgent")
        builder.add_service(
            name="orders",
            service=OrderService,
            instructions="Use get_status to check the status of an order. If the user asks about order ORD-001, use get_status with order_id='ORD-001'.",
            args=(db,)
        )
        builder.build(TEST_MODEL)

        result = await builder.agent.run(
            "¿Cuál es el estado de la orden ORD-001?",
            deps=builder.deps,
        )
        assert result is not None
        # The agent should have used the tool and return information
        assert "ORD-001" in str(result) or "shipped" in str(result).lower() or "bogota" in str(result).lower()

    @pytest.mark.asyncio
    async def test_agent_with_multiple_services(self):
        """REQ-003: Agent uses multiple services."""
        db = FakeOrderDB()
        builder = TTMBuilder(name="MultiServiceAgent")
        builder.add_service(
            name="orders",
            service=OrderService,
            instructions="Order management. Use get_status for status.",
            args=(db,)
        )
        builder.add_service(
            name="refunds",
            service=RefundService,
            instructions="Refund management. Use status to check."
        )
        builder.build(TEST_MODEL)

        result = await builder.agent.run(
            "¿Cuál es el estado de la orden ORD-002?",
            deps=builder.deps,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_agent_with_middlewares(self):
        """REQ-005: Agent works with active middlewares."""
        db = FakeOrderDB()
        builder = TTMBuilder(name="MiddlewareAgent")
        builder.add_service(
            name="orders",
            service=OrderService,
            instructions="Order management. Use get_status.",
            args=(db,),
            middleware=[AuthMiddleware(include=frozenset({"get_status"}))]
        )
        builder.add_middleware(LogMiddleware())
        builder.build(TEST_MODEL)

        result = await builder.agent.run(
            "Consulta el estado de ORD-003",
            deps=builder.deps,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_agent_module_with_llm(self):
        """REQ-002+REQ-004: Agent with module works with LLM."""
        db = FakeOrderDB()
        builder = TTMBuilder(name="ModuleLLMAgent")
        builder.add_module(
            name="Commerce",
            services=[
                Service(
                    name="orders",
                    service=OrderService,
                    instructions="Order management. Use get_status.",
                    args=(db,)
                )
            ],
            description="Commerce module"
        )
        builder.build(TEST_MODEL)

        result = await builder.agent.run(
            "¿Qué órdenes hay? Consulta la ORD-001",
            deps=builder.deps,
        )
        assert result is not None


# ============================================================
# LEVEL 4: ACCEPTANCE TESTS (stakeholder need level)
# REQ-001 through REQ-008
# ============================================================

class TestAcceptanceFullFlow:
    """Acceptance tests: full usage flow."""

    @pytest.mark.asyncio
    async def test_full_flow_builder_service_middleware_llm(self):
        """Full flow: Builder + Service + Middleware + LLM."""
        db = FakeOrderDB()

        # Arrange
        builder = TTMBuilder(name="CustomerSupport")
        builder.add_service(
            name="orders",
            service=OrderService,
            instructions=(
                "Order service. "
                " Use get_status to check order status. "
                " Use get_tracking to check tracking."
            ),
            args=(db,),
            middleware=[AuthMiddleware(include=frozenset({"get_status"}))]
        )
        builder.add_service(
            name="refunds",
            service=RefundService,
            instructions="Refund service. Use status to check.",
        )
        builder.add_middleware(LogMiddleware())

        # Act
        builder.build(TEST_MODEL)

        # Assert - Agent created
        assert builder.agent is not None
        assert builder.agent.name == "CustomerSupport"

        # Act - Execute with LLM
        result = await builder.agent.run(
            "Necesito saber el estado de la orden ORD-001 y si tiene tracking",
            deps=builder.deps,
        )

        # Assert - Valid result
        assert result is not None
        result_str = str(result).lower()
        # Must contain order information
        assert any(keyword in result_str for keyword in [
            "ord-001", "shipped", "bogota", "trk-123", "tracking"
        ])

    @pytest.mark.asyncio
    async def test_full_flow_module_builder_llm(self):
        """Full flow: Module + Builder + LLM."""
        db = FakeOrderDB()

        # Arrange
        builder = TTMBuilder(name="CommerceAgent")
        builder.add_module(
            name="Orders",
            services=[
                Service(
                    name="orders",
                    service=OrderService,
                    instructions="Order management. Use get_status.",
                    args=(db,)
                )
            ],
            description="Order management module"
        )
        builder.add_service(
            name="refunds",
            service=RefundService,
            instructions="Refund service."
        )

        # Act
        builder.build(TEST_MODEL)

        # Assert
        assert builder.agent is not None

        # Act - Execute
        result = await builder.agent.run(
            "¿Cuál es el estado de la ORD-003?",
            deps=builder.deps,
        )

        # Assert
        assert result is not None

    @pytest.mark.asyncio
    async def test_error_handling_invalid_order(self):
        """Error handling: non-existent order."""
        db = FakeOrderDB()

        builder = TTMBuilder(name="ErrorAgent")
        builder.add_service(
            name="orders",
            service=OrderService,
            instructions="Order management. Use get_status.",
            args=(db,)
        )
        builder.build(TEST_MODEL)

        result = await builder.agent.run(
            "¿Cuál es el estado de la orden ORD-999?",
            deps=builder.deps,
        )
        assert result is not None
        # Must handle the error gracefully
        result_str = str(result).lower()
        assert any(keyword in result_str for keyword in [
            "not found", "no encontr", "error", " ord", "999"
        ])
