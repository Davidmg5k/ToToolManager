import pytest
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.builder.ttm_builder import TTMBuilder
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware


class UserService:
    """User service for testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}

    def delete(self, id: int) -> bool:
        return True


class OrderService:
    """Order service for testing."""

    def create(self, product: str) -> str:
        return f"Order created for {product}"

    def get(self, id: int) -> dict:
        return {"id": id, "product": "Test"}


class AuthMiddleware(Middleware):
    """Example authentication middleware."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestCrearAgenteBasico:
    """Use case: Create agent with 1 service."""

    def test_crear_agente_con_servicio(self):
        """Given a service, when agent is created, then it is available"""
        # Arrange
        service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )

        # Act
        manager = ToToolManager(
            name="TestManager",
            resources=[service]
        )
        agent = manager.build_agent()

        # Assert
        assert agent is not None
        assert agent.name == "TestManager"


class TestAgenteConModulos:
    """Use case: Create agent with modules."""

    def test_crear_agente_con_modulos(self):
        """Given a module with services, when agent is created, then it works"""
        # Arrange
        user_service = Service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        order_service = Service(
            name="Order",
            service=OrderService,
            instructions="Order management"
        )
        module = Module(
            name="Commerce",
            services=[user_service, order_service],
            description="Commerce module"
        )

        # Act
        manager = ToToolManager(
            name="TestManager",
            resources=[module]
        )
        agent = manager.build_agent()

        # Assert
        assert agent is not None
        assert "Commerce" in manager.modules


class TestToolMiddlewareFiltrado:
    """Use case: ToolMiddleware filters methods."""

    def test_filtrado_por_include(self):
        """Given a ToolMiddleware with include, when executed, only included methods"""
        # Arrange
        class AuthMiddleware(ToolMiddleware):
            async def dispatch(self, func, /, *args, **kw):
                return await func(*args, **kw)

        middleware = AuthMiddleware(include=["create"])

        # Act
        is_create_allowed = middleware.is_allowed("create")
        is_get_allowed = middleware.is_allowed("get")

        # Assert
        assert is_create_allowed == True
        assert is_get_allowed == False


class TestDisableMiddlewares:
    """Use case: Disable inherited middlewares."""

    def test_servicio_publico_sin_auth(self):
        """Given a public service, when auth is disabled, then it is not applied"""
        # Arrange
        public_service = Service(
            name="Public",
            service=UserService,
            instructions="Public API",
            disable_middlewares=("AuthMiddleware",)
        )

        # Act
        manager = ToToolManager(
            name="TestManager",
            resources=[public_service],
            middlewares=[AuthMiddleware()]
        )
        resolved = manager._resolve_middlewares(public_service)

        # Assert
        assert not any(m.name == "AuthMiddleware" for m in resolved)


class TestFluentBuilder:
    """Use case: Full declarative API."""

    def test_fluent_api_crea_agente(self):
        """Given a TTMBuilder, when fluent API is used, then agent is created"""
        # Arrange & Act
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="User management"
        )
        builder.build()

        # Assert
        assert builder.agent is not None
        assert builder.agent.name == "TestBuilder"
