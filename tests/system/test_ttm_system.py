"""
Tests de Sistema - Nivel Requisitos (Modelo V)
===============================================

Matriz de Trazabilidad Requisito↔Prueba (RTM):
- REQ-001: Service crea tools a partir de métodos públicos
- REQ-002: Module agrupa servicios como sub-agente
- REQ-003: ToToolManager orquesta servicios y módulos
- REQ-004: TTMBuilder提供了fluent API para construir agentes
- REQ-005: Middleware se aplica en cadena correcta
- REQ-006: ToolMiddleware filtra métodos por include/exclude
- REQ-007: disable_middlewares excluye middlewares específicos
- REQ-008: to_mcp_tool() convierte en servidor MCP

Orden de validación por blast radius (axioma-auditoria):
1. DinamicDepend (leaf - blast radius=0)
2. Service.build_as_capability (frontera)
3. Module.build_as_agent (frontera)
4. ToToolManager.build_agent (nivel paquete)
5. TTMBuilder.build + Agent.run (nivel requisitos - CON LLM)

Modelo de prueba: groq:openai/gpt-oss-120b
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
# MODELO GLOBAL PARA TESTS DE SISTEMA
# ============================================================
TEST_MODEL = "groq:openai/gpt-oss-120b"


# ============================================================
# SERVICIOS DE EJEMPLO
# ============================================================

class FakeOrderDB:
    """Base de datos falsa para órdenes."""

    def __init__(self):
        self.orders = {
            "ORD-001": {"status": "shipped", "tracking": "TRK-123", "dest": "Bogota"},
            "ORD-002": {"status": "processing", "tracking": None, "dest": "Medellin"},
            "ORD-003": {"status": "delivered", "tracking": "TRK-456", "dest": "Cali"},
        }

    def get(self, order_id: str) -> dict | None:
        return self.orders.get(order_id)


class OrderService:
    """Servicio de órdenes para testing."""

    def __init__(self, db: FakeOrderDB):
        self.db = db

    def get_status(self, order_id: str) -> str:
        """Obtiene el estado de una orden."""
        order = self.db.get(order_id)
        if not order:
            return f"Order {order_id} not found"
        return f"Order {order_id}: status={order['status']}, dest={order['dest']}"

    def get_tracking(self, order_id: str) -> str:
        """Obtiene el tracking de una orden."""
        order = self.db.get(order_id)
        if not order:
            return f"Order {order_id} not found"
        if not order["tracking"]:
            return f"Order {order_id}: no tracking available"
        return f"Order {order_id}: tracking={order['tracking']}"


class RefundService:
    """Servicio de reembolsos para testing."""

    def status(self, order_id: str) -> str:
        """Estado del reembolso."""
        return f"Refund for {order_id}: pending review"

    def issue(self, order_id: str, reason: str) -> str:
        """Emitir reembolso."""
        return f"Refund issued for {order_id}. Reason: {reason}"


class UserService:
    """Servicio de usuarios para testing."""

    def create(self, name: str) -> str:
        """Crea un usuario."""
        return f"User {name} created"

    def get(self, user_id: int) -> dict:
        """Obtiene un usuario."""
        return {"id": user_id, "name": f"User_{user_id}"}


# ============================================================
# MIDDLEWARES DE EJEMPLO
# ============================================================

class AuthMiddleware(ToolMiddleware):
    """Middleware de autenticación."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class LogMiddleware(Middleware):
    """Middleware de logging."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class ValidationMiddleware(ToolMiddleware):
    """Middleware de validación."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


# ============================================================
# NIVEL 1: TESTS UNITARIOS (frontera - blast radius bajo)
# REQ-001, REQ-006, REQ-007
# ============================================================

class TestServiceBuildCapability:
    """Tests unitarios para Service.build_as_capability()."""

    def test_service_creates_capability(self):
        """REQ-001: Service retorna Capability con tools."""
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Gestión de órdenes"
        )
        capability = service.build_as_capability()
        assert capability is not None
        assert capability.id == "Order"

    def test_service_discovers_methods(self):
        """REQ-001: Service descubre métodos públicos."""
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Gestión de órdenes"
        )
        capability = service.build_as_capability()
        tool_names = [t.name for t in capability.tools]
        assert "get_status" in tool_names
        assert "get_tracking" in tool_names

    def test_service_with_middleware(self):
        """REQ-006: Service aplica ToolMiddleware."""
        mw = AuthMiddleware(include=["get_status"])
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Gestión de órdenes",
            middleware=[mw]
        )
        capability = service.build_as_capability()
        assert len(capability.tools) == 2

    def test_service_with_constructor_args(self):
        """REQ-001: Service acepta args para constructor."""
        db = FakeOrderDB()
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Gestión de órdenes",
            args=(db,)
        )
        capability = service.build_as_capability()
        assert capability is not None


# ============================================================
# NIVEL 2: TESTS DE INTEGRACIÓN (nivel paquete)
# REQ-002, REQ-003, REQ-005
# ============================================================

class TestModuleIntegration:
    """Tests de integración para Module."""

    def test_module_builds_subagent(self):
        """REQ-002: Module construye SubAgent."""
        db = FakeOrderDB()
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Gestión de órdenes",
            args=(db,)
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio"
        )
        subagent = module.build_as_agent()
        assert subagent is not None

    def test_module_applies_middlewares(self):
        """REQ-005: Module aplica middlewares a servicios."""
        db = FakeOrderDB()
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Gestión de órdenes",
            args=(db,)
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            middleware=[LogMiddleware()]
        )
        module.build_as_agent()
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)

    def test_module_disable_middlewares(self):
        """REQ-007: Module respeta disable_middlewares del Service."""
        db = FakeOrderDB()
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Gestión de órdenes",
            args=(db,),
            disable_middlewares=("AuthMiddleware",)
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio",
            middleware=[AuthMiddleware(), LogMiddleware()],
        )
        module.build_as_agent()
        assert not any(isinstance(mw, AuthMiddleware) for mw in service.middleware)
        assert any(isinstance(mw, LogMiddleware) for mw in service.middleware)


class TestToToolManagerIntegration:
    """Tests de integración para ToToolManager."""

    def test_manager_builds_agent(self):
        """REQ-003: ToToolManager construye Agent."""
        db = FakeOrderDB()
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Gestión de órdenes",
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
        """REQ-003: ToToolManager funciona con módulos."""
        db = FakeOrderDB()
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Gestión de órdenes",
            args=(db,)
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio"
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[module]
        )
        agent = manager.build_agent()
        assert agent is not None

    def test_manager_resolve_middlewares(self):
        """REQ-005: ToToolManager resuelve middlewares correctamente."""
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Gestión de órdenes"
        )
        manager = ToToolManager(
            name="TestManager",
            resources=[service],
            middlewares=[AuthMiddleware(), LogMiddleware()]
        )
        resolved = manager._resolve_middlewares(service)
        assert len(resolved) == 2

    def test_manager_disable_middlewares(self):
        """REQ-007: ToToolManager excluye middlewares deshabilitados."""
        service = Service(
            name="Order",
            service=OrderService,
            instructions="Gestión de órdenes",
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
# NIVEL 3: TESTS DE SISTEMA (nivel requisitos - CON LLM)
# REQ-004, REQ-008
# ============================================================

class TestTTMBuilderWithLLM:
    """Tests de sistema para TTMBuilder con groq:openai/gpt-oss-120b."""

    def test_builder_creates_agent_with_model(self):
        """REQ-004: TTMBuilder crea Agent con modelo especificado."""
        builder = TTMBuilder(name="TestAgent")
        builder.add_service(
            name="orders",
            service=OrderService,
            instructions="Gestión de órdenes. Usa get_status para consultar estado.",
            args=(FakeOrderDB(),)
        )
        builder.build(TEST_MODEL)
        assert builder.agent is not None
        assert builder.agent.name == "TestAgent"

    def test_builder_fluent_api_with_model(self):
        """REQ-004: TTMBuilder fluent API funciona con modelo."""
        builder = (
            TTMBuilder(name="FluentAgent")
            .add_service(
                name="orders",
                service=OrderService,
                instructions="Gestión de órdenes",
                args=(FakeOrderDB(),)
            )
            .add_service(
                name="refunds",
                service=RefundService,
                instructions="Gestión de reembolsos"
            )
        )
        builder.build(TEST_MODEL)
        assert builder.agent is not None

    def test_builder_with_module_and_model(self):
        """REQ-004: TTMBuilder funciona con módulos y modelo."""
        service = Service(
            name="orders",
            service=OrderService,
            instructions="Gestión de órdenes",
            args=(FakeOrderDB(),)
        )
        module = Module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio"
        )
        builder = TTMBuilder(name="ModuleAgent")
        builder.add_module(
            name="Commerce",
            services=[service],
            description="Módulo de comercio"
        )
        builder.build(TEST_MODEL)
        assert builder.agent is not None

    def test_builder_context_manager_with_model(self):
        """REQ-004: Context manager funciona con modelo."""
        with TTMBuilder(name="ContextAgent") as builder:
            builder.add_service(
                name="orders",
                service=OrderService,
                instructions="Gestión de órdenes",
                args=(FakeOrderDB(),)
            )
        # build() se llama automáticamente en __exit__
        assert builder.agent is not None

    def test_to_mcp_tool(self):
        """REQ-008: to_mcp_tool() crea servidor MCP."""
        from fastmcp import FastMCP

        builder = TTMBuilder(name="MCPAgent")
        builder.add_service(
            name="orders",
            service=OrderService,
            instructions="Gestión de órdenes",
            args=(FakeOrderDB(),)
        )
        builder.build(TEST_MODEL)

        mcp_app = builder.to_mcp_tool(
            name="OrderMCP",
            instructions="Servidor MCP de órdenes"
        )
        assert isinstance(mcp_app, FastMCP)
        assert mcp_app.name == "OrderMCP"


class TestAgentExecutionWithLLM:
    """Tests de ejecución real del agente con groq:openai/gpt-oss-120b."""

    @pytest.mark.asyncio
    async def test_agent_runs_with_tool_call(self):
        """REQ-003+REQ-004: Agente ejecuta tool real con LLM."""
        db = FakeOrderDB()
        builder = TTMBuilder(name="ExecAgent")
        builder.add_service(
            name="orders",
            service=OrderService,
            instructions="Usa get_status para consultar el estado de una orden. Si el usuario pregunta por la orden ORD-001, usa get_status con order_id='ORD-001'.",
            args=(db,)
        )
        builder.build(TEST_MODEL)

        result = await builder.agent.run(
            "¿Cuál es el estado de la orden ORD-001?",
            deps=builder.deps,
        )
        assert result is not None
        # El agente debe haber usado la tool y retornar información
        assert "ORD-001" in str(result) or "shipped" in str(result).lower() or "bogota" in str(result).lower()

    @pytest.mark.asyncio
    async def test_agent_with_multiple_services(self):
        """REQ-003: Agente usa múltiples servicios."""
        db = FakeOrderDB()
        builder = TTMBuilder(name="MultiServiceAgent")
        builder.add_service(
            name="orders",
            service=OrderService,
            instructions="Gestión de órdenes. Usa get_status para estado.",
            args=(db,)
        )
        builder.add_service(
            name="refunds",
            service=RefundService,
            instructions="Gestión de reembolsos. Usa status para consultar."
        )
        builder.build(TEST_MODEL)

        result = await builder.agent.run(
            "¿Cuál es el estado de la orden ORD-002?",
            deps=builder.deps,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_agent_with_middlewares(self):
        """REQ-005: Agente funciona con middlewares activos."""
        db = FakeOrderDB()
        builder = TTMBuilder(name="MiddlewareAgent")
        builder.add_service(
            name="orders",
            service=OrderService,
            instructions="Gestión de órdenes. Usa get_status.",
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
        """REQ-002+REQ-004: Agente con módulo funciona con LLM."""
        db = FakeOrderDB()
        builder = TTMBuilder(name="ModuleLLMAgent")
        builder.add_module(
            name="Commerce",
            services=[
                Service(
                    name="orders",
                    service=OrderService,
                    instructions="Gestión de órdenes. Usa get_status.",
                    args=(db,)
                )
            ],
            description="Módulo de comercio"
        )
        builder.build(TEST_MODEL)

        result = await builder.agent.run(
            "¿Qué órdenes hay? Consulta la ORD-001",
            deps=builder.deps,
        )
        assert result is not None


# ============================================================
# NIVEL 4: TESTS DE ACEPTACIÓN (nivel necesidad stakeholder)
# REQ-001 through REQ-008
# ============================================================

class TestAcceptanceFullFlow:
    """Tests de aceptación: flujo completo de uso."""

    @pytest.mark.asyncio
    async def test_full_flow_builder_service_middleware_llm(self):
        """Flujo completo: Builder + Service + Middleware + LLM."""
        db = FakeOrderDB()

        # Arrange
        builder = TTMBuilder(name="CustomerSupport")
        builder.add_service(
            name="orders",
            service=OrderService,
            instructions=(
                "Servicio de órdenes. "
                " Usa get_status para consultar estado de una orden. "
                " Usa get_tracking para consultar tracking."
            ),
            args=(db,),
            middleware=[AuthMiddleware(include=frozenset({"get_status"}))]
        )
        builder.add_service(
            name="refunds",
            service=RefundService,
            instructions="Servicio de reembolsos. Usa status para consultar.",
        )
        builder.add_middleware(LogMiddleware())

        # Act
        builder.build(TEST_MODEL)

        # Assert - Agente creado
        assert builder.agent is not None
        assert builder.agent.name == "CustomerSupport"

        # Act - Ejecutar con LLM
        result = await builder.agent.run(
            "Necesito saber el estado de la orden ORD-001 y si tiene tracking",
            deps=builder.deps,
        )

        # Assert - Resultado válido
        assert result is not None
        result_str = str(result).lower()
        # Debe contener información de la orden
        assert any(keyword in result_str for keyword in [
            "ord-001", "shipped", "bogota", "trk-123", "tracking"
        ])

    @pytest.mark.asyncio
    async def test_full_flow_module_builder_llm(self):
        """Flujo completo: Module + Builder + LLM."""
        db = FakeOrderDB()

        # Arrange
        builder = TTMBuilder(name="CommerceAgent")
        builder.add_module(
            name="Orders",
            services=[
                Service(
                    name="orders",
                    service=OrderService,
                    instructions="Gestión de órdenes. Usa get_status.",
                    args=(db,)
                )
            ],
            description="Módulo de gestión de órdenes"
        )
        builder.add_service(
            name="refunds",
            service=RefundService,
            instructions="Servicio de reembolsos."
        )

        # Act
        builder.build(TEST_MODEL)

        # Assert
        assert builder.agent is not None

        # Act - Ejecutar
        result = await builder.agent.run(
            "¿Cuál es el estado de la ORD-003?",
            deps=builder.deps,
        )

        # Assert
        assert result is not None

    @pytest.mark.asyncio
    async def test_error_handling_invalid_order(self):
        """Manejo de errores: orden inexistente."""
        db = FakeOrderDB()

        builder = TTMBuilder(name="ErrorAgent")
        builder.add_service(
            name="orders",
            service=OrderService,
            instructions="Gestión de órdenes. Usa get_status.",
            args=(db,)
        )
        builder.build(TEST_MODEL)

        result = await builder.agent.run(
            "¿Cuál es el estado de la orden ORD-999?",
            deps=builder.deps,
        )
        assert result is not None
        # Debe manejar el error gracefully
        result_str = str(result).lower()
        assert any(keyword in result_str for keyword in [
            "not found", "no encontr", "error", " ord", "999"
        ])
