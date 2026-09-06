import pytest
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.builder.ttm_builder import TTMBuilder
from to_tool_manager.core.middleware.middleware import Middleware, ToolMiddleware


class UserService:
    """Servicio de usuarios para testing."""

    def create(self, name: str) -> str:
        return f"Created {name}"

    def get(self, id: int) -> dict:
        return {"id": id, "name": "Test"}

    def delete(self, id: int) -> bool:
        return True


class OrderService:
    """Servicio de órdenes para testing."""

    def create(self, product: str) -> str:
        return f"Order created for {product}"

    def get(self, id: int) -> dict:
        return {"id": id, "product": "Test"}


class AuthMiddleware(Middleware):
    """Middleware de autenticación de ejemplo."""

    async def dispatch(self, func, /, *args, **kw):
        return await func(*args, **kw)


class TestCrearAgenteBasico:
    """Caso de uso: Crear agente con 1 servicio."""

    def test_crear_agente_con_servicio(self):
        """Dado un servicio, cuando se crea agente, entonces está disponible"""
        # Arrange
        service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
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
    """Caso de uso: Crear agente con módulos."""

    def test_crear_agente_con_modulos(self):
        """Dado un módulo con servicios, cuando se crea agente, entonces funciona"""
        # Arrange
        user_service = Service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        order_service = Service(
            name="Order",
            service=OrderService,
            instructions="Gestión de órdenes"
        )
        module = Module(
            name="Commerce",
            services=[user_service, order_service],
            description="Módulo de comercio"
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
    """Caso de uso: ToolMiddleware filtra métodos."""

    def test_filtrado_por_include(self):
        """Dado un ToolMiddleware con include, cuando se ejecuta, solo métodos incluidos"""
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
    """Caso de uso: Deshabilitar middlewares heredados."""

    def test_servicio_publico_sin_auth(self):
        """Dado un servicio público, cuando se deshabilita auth, entonces no se aplica"""
        # Arrange
        public_service = Service(
            name="Public",
            service=UserService,
            instructions="API pública",
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
    """Caso de uso: API declarativa completa."""

    def test_fluent_api_crea_agente(self):
        """Dado un TTMBuilder, cuando se usa fluent API, entonces crea agente"""
        # Arrange & Act
        builder = TTMBuilder(name="TestBuilder")
        builder.add_service(
            name="User",
            service=UserService,
            instructions="Gestión de usuarios"
        )
        builder.build()

        # Assert
        assert builder.agent is not None
        assert builder.agent.name == "TestBuilder"
