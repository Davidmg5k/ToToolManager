"""
Ejemplo de integración con skills agnósticas.

Este archivo demuestra cómo las skills influyen en el comportamiento
del agente sin interponerse en la lógica de negocio.

Muestra dos patrones:
  - **Service** → herramienta individual, el agente llama métodos directamente.
  - **Module** → agrupa servicios relacionados bajo un solo tool de lote,
                  el agente envía operaciones en un solo call.
"""
from typing import Any, Callable

from classes import (
    Order,
    OrderAlreadyExistsError,
    OrderNotFoundError,
    Product,
    User,
    UserAlreadyExistsError,
    UserNotFoundError,
    ProductNotFoundError,
    InvalidQuantityError,
    InsufficientStockError,
)
from dotenv import load_dotenv

from to_tool_manager.security.middleware import ToolMiddleware
from to_tool_manager.core.types import ToolResponse, ToolError

load_dotenv()

from to_tool_manager import Module, Service, ToToolManager, Middleware
from to_tool_manager.adapters.pydantic_ai import build_agent
from to_tool_manager.core.types import ErrorMap
from pydantic_ai_harness.planning import Planning

class AuthenticationError(Exception):...


# =============================================================================
# Middleware
# =============================================================================
class SecurityMiddleware(Middleware):

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        print("Into SecurityMiddleware")
        response = await func(*args, **kw)
        print("after the tool executed")
        return response

class AuthenticationMiddleware(ToolMiddleware):

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        print("entro a autenticar")
        auth = False
        if auth is False:
            return ToolResponse(
                error=ToolError(
                    category=frozenset({"authentication_error"}),
                    message="No puedes realizar esta acción porque no estás autenticado. Por favor, inicia sesión primero.",
                    exception_type="AuthenticationError",
                    retryable=False,
                )
            )
        return await func(*args, **kw)

# =============================================================================
# 1. Configurar servicios (framework-agnostic)
# =============================================================================

# -- Services individuales ---------------------------------------------------
# Cada Service se convierte en UNA herramienta independiente.

product_service = Service(
    name="Product",
    service=Product,
    description=(
        "Product catalog management: list products, check stock, "
        "get product details by category."
    ),
    error_map=(
        ErrorMap()
        .map(ProductNotFoundError, category="not_found")
    ),
    args=("cars",),
)

# -- Module: agrupación de servicios relacionados ----------------------------
# Un Module agrupa múltiples Services en un ÚNICO tool de batch.
# El agente envía un JSON con la lista de operaciones a ejecutar y el
# Module las despacha internamente a cada servicio.

order_module = Module(
    name="OrderManagement",
    description=(
        "Gestión integral de órdenes y usuarios del sistema. "
        "Permite crear, eliminar y consultar órdenes y usuarios "
        "en operaciones batch."
    ),
    services=[
        Service(
            name="Order",
            service=Order,
            description=(
                "Handles everything related to customer orders: creating, "
                "deleting and listing them. Supports batch operations."
            ),
            error_map=(
                ErrorMap()
                .map(OrderAlreadyExistsError, category="already_exists")
                .map(OrderNotFoundError, category="not_found")
                .map(InvalidQuantityError, category="validation_error")
                .map(InsufficientStockError, category="out_of_stock")
            ),
            disable_middlewares=["SecurityMiddleware"],
            middlewares=[AuthenticationMiddleware(include=["get_orders"])]
        ),
        Service(
            name="User",
            service=User,
            description=(
                "Handles everything related to application users: "
                "creation, deletion, lookup and existence checks."
            ),
            error_map=(
                ErrorMap()
                .map(UserAlreadyExistsError, category="already_exists")
                .map(UserNotFoundError, category="not_found")
                # .map(AuthenticationError, category="bad_credentials")
            ),
            disable_middlewares=["SecurityMiddleware"],
            middlewares=[AuthenticationMiddleware(include=["create_user"])]
        ),
    ],
)

# -- Manager -----------------------------------------------------------------
# Se pueden mezclar Services y Modules en el mismo manager.
# Services → tools individuales.
# Module   → un solo tool que encapsula sus servicios internos.

manager = ToToolManager([
        order_module,     # 1 tool: OrderManagement (batch)
        product_service,  # 1 tool: Product (directo)
    ],
    middlewares=[SecurityMiddleware()]
)


# =============================================================================

# =============================================================================
# 3. Construir agente con skills
# =============================================================================

def print_messages(result):
    for msg in result.new_messages():
        kind = msg.kind
        print(f"\n--- {kind.upper()} ---")
        for part in msg.parts:
            part_type = type(part).__name__
            if part_type == "ToolCallPart":
                print(f"  [Tool Call] {part.tool_name}({part.args})")
            elif part_type == "ToolReturnPart":
                print(f"  [Tool Result] {str(part.content)}")
            elif part_type == "TextPart":
                print(f"  {str(part.content)}")
            else:
                print(f"  [{part_type}] {str(getattr(part, 'content', str(part)))}")


# `capabilities=[Planning()]` -- pydantic-ai-harness task planning.
# `OrderManagement` agrupa varias operaciones batch (crear/eliminar
# usuarios y órdenes); Planning le da al modelo un checklist propio
# (write_plan/add_task/update_task_status) para trackear una secuencia
# de pasos del usuario a través de varios turnos, sin invalidar el
# prompt cache -- complementario al Module de arriba, no un reemplazo:
# el Module sigue siendo quien ejecuta las operaciones reales.
agent = build_agent(
    "groq:openai/gpt-oss-120b",
    manager,
    capabilities=[Planning()],
)


# =============================================================================
# 4. Web app
# =============================================================================

app = agent.to_web()