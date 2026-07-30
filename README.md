# to_tool_manager

Convierte clases Python normales (tu capa de servicios) en **tools**
para agentes, sin atarte a ningún framework de agentes.

## La idea central: un SERVICIO = una TOOL

**Cada `Service` que registrás produce exactamente UNA tool** — nunca
una tool por método. Esa tool acepta una lista de *operaciones*
(`{"method": ..., "args": {...}}`) y las ejecuta todas en una sola
llamada. Así, con dos servicios (`Order`, `User`) el LLM ve **dos
tools**, y puede hacer algo como:

> "Creá al usuario David y de paso listá todos los usuarios"

en **una sola tool call** al tool `User`, en vez de dos round-trips
separados:

```json
{
  "operations": [
    {"method": "create_user", "args": {"user_name": "David"}},
    {"method": "get_users", "args": {}}
  ]
}
```

```
tu clase de servicio  →  Service(...)  →  ToToolManager  →  tool_specs (1 por servicio, agnóstico)
                                                                   │
                                        ┌──────────────────────────┼──────────────────────┐
                                        ▼                          ▼                       ▼
                            adapters.pydantic_ai        adapters.fastmcp           adapters.raw
                            (Agent / FunctionToolset)    (servidor MCP)            (OpenAI/Anthropic
                                                                                     tools JSON a mano)
```

El paquete base (`to_tool_manager`) **no tiene ninguna dependencia dura**
de frameworks de agentes. Cada adapter importa su framework solo cuando
vos importás ese adapter.

---

## Instalación

```bash
pip install to_tool_manager

pip install pydantic-ai      # para adapters.pydantic_ai
pip install fastmcp          # para adapters.fastmcp
pip install ag-ui-core       # para adapters.ag_ui
# adapters.raw no necesita nada extra
```

---



## Indice

| Seccion | Descripcion |
|---------|-------------|
| [Instalacion](#instalacion) | Dependencias por adapter |
| [Uso rapido](#uso-rapido) | 3 pasos: clase -> registrar -> agente |
| [Referencia de la API](#referencia-de-la-api) | Service, Module, ToToolManager, ErrorMap, ToolSpec, ToolResponse |
| [Nivel 1 - Lo minimo](#nivel-1--lo-minimo-un-servicio-con-una-operacion) | Un servicio, una operacion |
| [Nivel 2 - Multiples operaciones](#nivel-2--servicio-con-multiples-operaciones-y-excepciones-propias) | Batch de ops, error handling |
| [Nivel 3 - Dos servicios](#nivel-3--dos-servicios-dos-tools-el-patron-tipico) | Patron tipico multi-tool |
| [Nivel 4 - Raw (sin framework)](#nivel-4--ejecutar-operaciones-directamente-sin-framework) | to_openai_tool_schemas, dispatch |
| [Nivel 5 - pydantic-ai](#nivel-5--integracion-con-pydantic-ai-agent) | build_agent, run_streaming, iter_agent |
| [Nivel 6 - FastMCP](#nivel-6--integracion-con-fastmcp-servidor-mcp) | build_mcp_server, build_mcp_agent |
| [Nivel 7 - Visibilidad](#nivel-7--opciones-de-visibilidad-y-filtrado-de-metodos) | public, protected, include, exclude |
| [Nivel 8 - Properties](#nivel-8--exponer-propiedades-como-operaciones) | @property como ops de 0 args |
| [Nivel 9 - ErrorMap](#nivel-9--sistema-de-errores-avanzado-con-errormap) | map, map_callable, when |
| [Nivel 10 - Prompts](#nivel-10--prompts-personalizados) | build_system_prompt, build_instructions |
| [Nivel 11 - Modulos](#nivel-11--modulos-sub-agentes-aislados) | Module con sub-agentes |
| [Nivel 12 - Planner](#nivel-12--planner-planificacion-cross-service) | Step, StepOperation, ServiceDependencyGraph |
| [Nivel 13 - ag_ui](#nivel-13--integracion-con-ag_ui-streaming-de-estado-a-uis) | AGUIPlanHandler |
| [Nivel 14 - Skills](#nivel-14--skills-patrones-de-comportamiento-para-agentes) | reasoning, validation, etc. |
| [Nivel 15 - build_agent completo](#nivel-15--build_agent-con-todas-las-opciones) | Todas las opciones de build_agent |
| [Nivel 16 - Condicionales when](#nivel-16--operaciones-condicionales-con-when) | when clauses en batches |
| [Nivel 17 - Singleton](#nivel-17--clase-como-singleton-vs-instancias-frescas) | singleton=True/False |
| [Nivel 18 - Middleware](#nivel-18--middleware) | Middleware vs ToolMiddleware, secuencias, por que van en capas |
| [Nivel 19 - Caso completo](#nivel-19--caso-completo-pydantic-ai--planner--streaming) | Planner + agent + streaming con diagrama |
| [Ejemplos completos](#ejemplos-completos) | example/ y example_ui_pydantic/ |

---

## Uso rápido

### 1. Definí tus clases de negocio

```python
class Order:
    """Gestiona órdenes de clientes."""

    def __init__(self) -> None:
        self.__orders: list[str] = ["gpu"]

    def create(self, product_name: str):
        """Crea una nueva orden.

        Args:
            product_name: Nombre del producto a ordenar.
        """
        if product_name in self.__orders:
            raise OrderAlreadyExistsError(f"Order '{product_name}' already exists")
        self.__orders.append(product_name)
        return f"Order '{product_name}' created successfully"

    def delete(self, product_name: str):
        """Elimina una orden por nombre de producto."""
        if product_name not in self.__orders:
            raise OrderNotFoundError(f"Order '{product_name}' not found")
        self.__orders.remove(product_name)
        return f"Order '{product_name}' deleted successfully"

    def get_orders(self):
        """Devuelve todas las órdenes actuales."""
        return self.__orders
```

### 2. Registralas como tools

```python
from to_tool_manager import Service, ToToolManager

manager = ToToolManager([
    Service(
        name="Order",
        service=Order,
        description="Manages customer orders.",
        error_map={
            OrderAlreadyExistsError: ("already_exists", False),
            OrderNotFoundError: ("not_found", False),
        },
    ),
])
```

### 3. Construí el agente

```python
from to_tool_manager.adapters.pydantic_ai import build_agent

agent = build_agent("groq:llama-3.1-8b-instant", manager)
result = await agent.run("Creá una orden para laptop")
print(result.output)
```

---

## Referencia de la API

### `Service`

Registra una clase Python como tool.

```python
Service(
    name="Order",                     # nombre de la tool (requerido)
    service=Order,                    # la clase a envolver (requerido)
    description="Manages orders.",    # descripción de la tool (default: auto)
    visibility={"public"},            # qué métodos exponer (default)
    include=frozenset({"create"}),    # whitelist (ignora visibility)
    exclude=frozenset({"_internal"}), # blacklist
    expose_properties=False,          # exponer @property como ops de 0 args
    error_map=ErrorMap(),             # clasificación de excepciones
    sanitize_system_errors=True,      # ocultar texto raw de errores no mapeados
    singleton=True,                   # reusar instancia vs. crear por llamada
    args=(),                          # args del constructor
    kwargs={},                        # kwargs del constructor
    middlewares=[],                   # middlewares de este servicio
    disable_middlewares=[],           # desactivar middlewares globales para este servicio
)
```

### `Module`

Agrupa varios servicios bajo un solo sub-agente con su propio system prompt.

```python
Module(
    name="Commerce",
    description="Sub-agente de comercio.",
    system_prompt="Sos un especialista en comercio. Respondé en español.",
    services=[service1, service2],
    middlewares=[],
    disable_middlewares=[],
)
```

### `ToToolManager`

Punto de entrada único. Crea una instancia por aplicación.

```python
manager = ToToolManager(
    services=[service_or_module, ...],    # Service o Module
    middlewares=[GlobalMiddleware()],      # middlewares globales
)

manager.tool_specs       # list[ToolSpec] — las tools generadas
manager.services         # dict[str, Service] — servicios registrados
manager.modules          # dict[str, Module] — módulos registrados
manager.get_service("Order")  # lookup por nombre
manager.refresh()             # invalidar cache de tool_specs
manager.register_middleware([mw])  # registrar middleware en runtime
```

### `ErrorMap`

Builder composable para clasificar excepciones.

```python
ErrorMap()
    .map(NotFoundError, category="not_found")
    .map(AlreadyExistsError, category="already_exists")
    .map(ValidationError, category="validation_error", retryable=True)
    .map_entry(SomeError, ErrorEntry(category="custom", retryable=False))
    .map_callable(HTTPError, lambda e: ("not_found", False) if e.status_code == 404 else ("server", False))
    .when(lambda e: hasattr(e, "timeout"), category="timeout", retryable=True)
```

También acepta el formato dict legacy: `error_map={ExcType: ("category", retryable)}`.

### `ToolSpec` (dato de salida)

Cada `Service`/`Module` produce un `ToolSpec` con:

- `name` — nombre de la tool
- `description` — descripción auto-generada
- `operations` — tupla de `OperationSpec` (una por método expuesto)
- `call(operations=[...])` — dispatch que **nunca lanza excepciones**, siempre retorna `ToolResponse`

### `ToolResponse`

```python
ToolResponse(content=resultado, error=None)   # éxito
ToolResponse(content=None, error=ToolError(...))  # error clasificado
response.ok  # True si no hay error
```

---

## Ejemplos de uso

### Nivel 1 — Lo mínimo: un servicio con una operación

```python
class Counter:
    """Un contador simple."""

    def __init__(self) -> None:
        self.__value = 0

    def increment(self, amount: int = 1):
        """Suma al contador.

        Args:
            amount: Cantidad a sumar.
        """
        self.__value += amount
        return self.__value

    def get_value(self):
        """Devuelve el valor actual."""
        return self.__value
```

```python
from to_tool_manager import Service, ToToolManager

manager = ToToolManager([
    Service(name="Counter", service=Counter, description="Simple counter."),
])

# Un solo ToolSpec, con una sola operación
print(len(manager.tool_specs))  # 1
print(manager.tool_specs[0].operations[0].name)  # "increment"
```

---

### Nivel 2 — Servicio con múltiples operaciones y excepciones propias

```python
class OrderAlreadyExistsError(Exception): ...
class OrderNotFoundError(Exception): ...

class Order:
    """Gestiona órdenes de clientes: creación, eliminación y listado."""

    def __init__(self) -> None:
        self.__orders: list[str] = ["gpu"]

    def create(self, product_name: str):
        """Crea una nueva orden.

        Args:
            product_name: Nombre del producto a ordenar.
        """
        if product_name in self.__orders:
            raise OrderAlreadyExistsError(f"Order '{product_name}' already exists")
        self.__orders.append(product_name)
        return f"Order '{product_name}' created successfully"

    def delete(self, product_name: str):
        """Elimina una orden por nombre de producto."""
        if product_name not in self.__orders:
            raise OrderNotFoundError(f"Order '{product_name}' not found")
        self.__orders.remove(product_name)
        return f"Order '{product_name}' deleted successfully"

    def get_orders(self):
        """Devuelve todas las órdenes actuales."""
        return self.__orders
```

```python
from to_tool_manager import Service, ToToolManager

manager = ToToolManager([
    Service(
        name="Order",
        service=Order,
        description="Gestiona todo lo relacionado con órdenes de clientes.",
        error_map={
            OrderAlreadyExistsError: ("already_exists", False),
            OrderNotFoundError: ("not_found", False),
        },
    ),
])
```

Cada `ToolSpec` trae: `name` (== nombre del servicio), `description`
(auto-generada, enumera cada operación con su firma y docstring), un
único parámetro `operations`, y `call(operations=[...])` que **nunca
tira excepción** — siempre devuelve un `ToolResponse` cuyo `content`
es una lista con el resultado de cada operación:

```json
[
  {"method": "create", "success": true, "result": "Order 'laptop' created successfully"},
  {"method": "get_orders", "success": true, "result": ["gpu", "laptop"]}
]
```

Una operación que falla **no aborta** el resto del batch:

```json
[
  {"method": "create", "success": false, "error": {"category": "already_exists", "message": "Order 'gpu' already exists"}},
  {"method": "get_orders", "success": true, "result": ["gpu"]}
]
```

---

### Nivel 3 — Dos servicios, dos tools (el patrón típico)

```python
class UserNotFoundError(Exception): ...
class UserAlreadyExistsError(Exception): ...

class User:
    """Gestiona usuarios del sistema."""

    def __init__(self) -> None:
        self.__users: list[str] = ["admin"]

    def create_user(self, user_name: str):
        """Crea un nuevo usuario."""
        if user_name in self.__users:
            raise UserAlreadyExistsError(f"User '{user_name}' already exists")
        self.__users.append(user_name)
        return f"User '{user_name}' created"

    def get_users(self):
        """Lista todos los usuarios."""
        return self.__users
```

```python
from to_tool_manager import Service, ToToolManager

manager = ToToolManager([
    Service(
        name="Order",
        service=Order,
        description="Manages customer orders.",
        error_map={
            OrderAlreadyExistsError: ("already_exists", False),
            OrderNotFoundError: ("not_found", False),
        },
    ),
    Service(
        name="User",
        service=User,
        description="Manages system users.",
        error_map={
            UserAlreadyExistsError: ("already_exists", False),
            UserNotFoundError: ("not_found", False),
        },
    ),
])

# Dos tools: Order y User
assert len(manager.tool_specs) == 2
assert [s.name for s in manager.tool_specs] == ["Order", "User"]
```

---

### Nivel 4 — Ejecutar operaciones directamente (sin framework)

```python
import asyncio
from to_tool_manager.adapters.raw import to_openai_tool_schemas, dispatch

# Genera schemas compatibles con OpenAI/Anthropic
tool_schemas = to_openai_tool_schemas(manager.tool_specs)

# Ejecuta una tool por nombre
async def main():
    response = await dispatch("Order", {
        "operations": [
            {"method": "create", "args": {"product_name": "laptop"}},
            {"method": "get_orders", "args": {}},
        ]
    }, manager.tool_specs)
    print(response.content)

asyncio.run(main())
```

---

### Nivel 5 — Integración con pydantic-ai (Agent)

```python
from to_tool_manager.adapters.pydantic_ai import build_agent

agent = build_agent("groq:llama-3.1-8b-instant", manager)

# El agent ya tiene acceso a las tools Order y User
result = await agent.run("Creá un usuario llamado David y listá todas las órdenes")
print(result.output)
```

**Salida tipada** para integrar a un frontend:

```python
from pydantic import BaseModel

class AgentReply(BaseModel):
    message: str
    success: bool
    data: dict | None = None

agent = build_agent("groq:llama-3.1-8b-instant", manager, output_type=AgentReply)
result = await agent.run("Creá al usuario David")
print(result.output.message)   # str, seguro de mostrar directo
print(result.output.success)   # bool
```

**Streaming** de la respuesta:

```python
from to_tool_manager.adapters.pydantic_ai import run_streaming

async with run_streaming(agent, "Listá todas las órdenes") as stream:
    async for text in stream.stream_text():
        print(text, end="", flush=True)
```

**Iteración de nodos** (para observabilidad):

```python
from to_tool_manager.adapters.pydantic_ai import iter_agent

async with iter_agent(agent, "Creá al usuario David") as run:
    async for node in run:
        print(type(node).__name__)  # ToolCallNode, ToolReturnNode, etc.
```

---

### Nivel 6 — Integración con FastMCP (servidor MCP)

```python
from to_tool_manager.adapters.fastmcp import build_mcp_server

mcp = build_mcp_server("order-user-service", manager.tool_specs)
mcp.run()
```

O registrando en un servidor existente:

```python
from fastmcp import FastMCP
from to_tool_manager.adapters.fastmcp import register_on_mcp

mcp = FastMCP("my-server")
register_on_mcp(mcp, manager.tool_specs)
mcp.run()
```

Si tenés `Module`, usá `build_mcp_agent` para montar sub-servidores aislados por namespace:

```python
from to_tool_manager.adapters.fastmcp import build_mcp_agent

mcp = build_mcp_agent("commerce", manager)
mcp.run()
```

---

### Nivel 7 — Opciones de visibilidad y filtrado de métodos

```python
class InternalService:
    """Servicio con métodos públicos, protegidos y privados."""

    def public_method(self):
        """Método público."""
        return "public"

    def _protected_method(self):
        """Método protegido."""
        return "protected"

    def __private_method(self):
        """Método privado (mangled)."""
        return "private"
```

```python
from to_tool_manager import Service, ToToolManager

# Solo públicos (default)
s1 = Service(name="A", service=InternalService, visibility={"public"})

# Públicos + protegidos
s2 = Service(name="B", service=InternalService, visibility={"public", "protected"})

# Solo métodos específicos (ignora visibility)
s3 = Service(name="C", service=InternalService, include=frozenset({"public_method"}))

# Excluir un método puntual
s4 = Service(name="D", service=InternalService, exclude=frozenset({"_protected_method"}))
```

---

### Nivel 8 — Exponer propiedades como operaciones

```python
class Config:
    """Servicio con propiedades de solo lectura."""

    @property
    def version(self):
        """Versión actual del sistema."""
        return "1.0.0"

    @property
    def max_retries(self):
        """Máximo de reintentos permitidos."""
        return 3

    def reload(self):
        """Recarga la configuración."""
        return "reloaded"
```

```python
service = Service(name="Config", service=Config, expose_properties=True)

manager = ToToolManager([service])
spec = manager.tool_specs[0]

# Tres operaciones: version, max_retries, reload
assert len(spec.operations) == 3
assert [op.name for op in spec.operations] == ["version", "max_retries", "reload"]
```

---

### Nivel 9 — Sistema de errores avanzado con ErrorMap

```python
from to_tool_manager import Service, ToToolManager
from to_tool_manager.core.types import ErrorMap

class HTTPError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)

class RateLimitError(Exception):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Rate limited, retry after {retry_after}s")

class ExternalAPI:
    """Servicio que depende de APIs externas."""

    def fetch_data(self, url: str):
        """Obtiene datos de una URL externa."""
        raise HTTPError(404, "Not found")

    def call_api(self, endpoint: str):
        """Llama a una API externa."""
        raise RateLimitError(retry_after=2.0)
```

```python
# ErrorMap composable con type-based y predicate-based rules
error_map = (
    ErrorMap()
    .map(HTTPError, category="not_found")
    .map(RateLimitError, category="rate_limited", retryable=True)
    .map_callable(
        HTTPError,
        lambda e: ("not_found", False) if e.status_code == 404 else ("server_error", False),
    )
    .when(
        lambda e: hasattr(e, "retry_after"),
        category="rate_limited",
        retryable=True,
    )
)

service = Service(
    name="ExternalAPI",
    service=ExternalAPI,
    error_map=error_map,
    sanitize_system_errors=True,  # errores no mapeados se sanitizan
)
```

**Reglas de error por defecto** (sin mapear):

| Excepción | Categoría | Reintentable |
|---|---|---|
| `ValueError` / `TypeError` | `validation_error` | Sí |
| `KeyError` / `LookupError` | `not_found` | No |
| Cualquier otra | `unclassified` (sanitizado) | No |

---

### Nivel 10 — Prompts personalizados

```python
from to_tool_manager import build_system_prompt, build_instructions

services = list(manager.services.values())

# Extender el prompt por defecto
prompt = build_system_prompt(
    services,
    custom="Responde siempre en español, tono formal.",
)

# Reemplazar el prompt por completo
prompt = build_system_prompt(
    services,
    custom="Sos un agente interno, solo para empleados.",
    mode="override",
)

# Instrucciones dinámicas (separadas del system prompt)
instructions = build_instructions(
    custom="Siempre confirmá con el usuario antes de borrar.",
)
```

---

### Nivel 11 — Módulos (sub-agentes aislados)

Un `Module` agrupa varios servicios bajo un solo sub-agente con su
propio system prompt. El agente principal llama al Module como una
única tool.

```python
from to_tool_manager import Service, Module, ToToolManager

module = Module(
    name="OrderManagement",
    description="Sub-agente que gestiona órdenes y usuarios.",
    system_prompt="Sos un especialista en gestión de pedidos. Siempre respondé en español.",
    services=[
        Service(name="Order", service=Order, description="Manages orders."),
        Service(name="User", service=User, description="Manages users."),
    ],
)

manager = ToToolManager([module])

# Un solo ToolSpec que engloba todo el módulo
assert len(manager.tool_specs) == 1
assert manager.tool_specs[0].name == "OrderManagement"

# Todas las operaciones de Order y User están disponibles
op_names = [op.name for op in manager.tool_specs[0].operations]
assert "create" in op_names       # de Order
assert "get_users" in op_names    # de User
```

Modules soportan middlewares propios y pueden desactivar middlewares globales:

```python
module = Module(
    name="SecureModule",
    services=[service1, service2],
    middlewares=[LocalMiddleware()],
    disable_middlewares=["GlobalSecurity"],
)
```

---

### Nivel 12 — Planner (planificación cross-service)

El planner agrega una capa de planificación sobre el manager, permitiendo
crear planes con pasos que referencian operaciones de múltiples servicios.

```python
from to_tool_manager import Service, ToToolManager
from to_tool_manager.core.planner import (
    Step, StepOperation, Planner, ServiceDependency, ServiceDependencyGraph,
)

manager = ToToolManager([
    Service(name="Order", service=Order, description="Manages orders.",
            error_map={OrderAlreadyExistsError: ("already_exists", False),
                       OrderNotFoundError: ("not_found", False)}),
    Service(name="User", service=User, description="Manages users.",
            error_map={UserAlreadyExistsError: ("already_exists", False),
                       UserNotFoundError: ("not_found", False)}),
])

# Definir dependencias entre servicios
graph = ServiceDependencyGraph(
    dependencies=[
        ServiceDependency(source="Order", target="User", reason="Orders reference users"),
    ]
)

planner = manager.with_planner(dependency_graph=graph)

# Crear un plan con pasos
plan = await planner.create_plan([
    Step(
        description="Crear usuario David",
        operations=[
            StepOperation(service="User", method="create_user", args={"user_name": "David"}),
        ],
    ),
    Step(
        description="Crear orden para David",
        depends_on=[],
        operations=[
            StepOperation(service="Order", method="create", args={"product_name": "laptop"}),
        ],
    ),
    Step(
        description="Listar todo",
        operations=[
            StepOperation(service="User", method="get_users", args={}),
            StepOperation(service="Order", method="get_orders", args={}),
        ],
    ),
])

# Ejecutar el plan (pasos independientes corren en paralelo)
completed_plan = await planner.execute_plan(plan.id)

for step in completed_plan.steps:
    print(f"{step.description}: {step.status.value}")
```

El planner también expone 4 tools para que el agente gestione planes programáticamente:

```python
tools = planner.build_tools()  # create_plan, execute_plan, update_plan_step, get_plan
```

**Planner con handler de eventos** (para UIs en tiempo real):

```python
class LogHandler:
    async def on_plan_event(self, event):
        print(f"[{event.type.value}] plan={event.plan_id[:8]}")

planner.add_handler(LogHandler())

# Ahora cada cambio de estado emite eventos
plan = await planner.create_plan([...])
await planner.execute_plan(plan.id)
```

---

### Nivel 13 — Integración con ag_ui (streaming de estado a UIs)

```python
from to_tool_manager.adapters.ag_ui import AGUIPlanHandler

planner = manager.with_planner()
planner.add_handler(AGUIPlanHandler())

# Los eventos del planner se convierten a StateSnapshotEvent / StateDeltaEvent
# para actualizaciones en tiempo real en clientes ag_ui
```

---

### Nivel 14 — Skills (patrones de comportamiento para agentes)

Los skills son patrones de comportamiento que influyen CÓMO el agente
piensa y ejecuta. Se incluyen automáticamente al usar `build_agent`:

```python
from to_tool_manager.skills import (
    reasoning_skill,
    validation_skill,
    error_handling_skill,
    composition_skill,
    planning_skill,
    build_skills_toolset,
)

# build_agent ya incluye todos los skills por defecto
agent = build_agent("groq:llama-3.1-8b-instant", manager)

# O construir un toolset personalizado
toolset = build_skills_toolset(skills=[reasoning_skill, validation_skill])
```

**Skills disponibles:**

| Skill | Qué influye |
|---|---|
| `reasoning` | Pre-análisis, estrategia de ejecución, manejo de incertidumbre |
| `validation` | Validación de inputs, estado, dependencias y seguridad |
| `error_handling` | Clasificación de errores, estrategia de retry, comunicación |
| `composition` | Agrupación de operaciones independientes vs dependientes |
| `planning` | Cuándo planificar, estructura de pasos, batching inteligente |

---

### Nivel 15 — build_agent con todas las opciones

```python
from pydantic import BaseModel
from to_tool_manager.adapters.pydantic_ai import build_agent

class AgentReply(BaseModel):
    message: str
    success: bool
    data: dict | None = None

agent = build_agent(
    model="groq:llama-3.1-8b-instant",
    manager=manager,
    output_type=AgentReply,                # salida tipada
    system_prompt="Sos un asistente de negocio.",  # override del prompt auto-generado
    instructions="Siempre confirmá antes de borrar.",  # instrucciones dinámicas
    name="business-assistant",             # nombre para tracing
    description="Agente de gestión de negocio",
    model_settings={"temperature": 0.7},  # configuración del modelo
    retries=3,                             # reintentos por categoría
    tool_timeout=30.0,                     # timeout por tool
    max_concurrency=5,                     # concurrencia máxima
    end_strategy="exhaustive",             # ejecutar todos los tools antes de responder
)
```

---

### Nivel 16 — Operaciones condicionales con `when`

Dentro de un batch, podés encadenar operaciones con cláusulas `when`
que dependen del resultado de una operación anterior en la misma llamada:

```python
# Solo listar usuarios si la creación falló porque ya existía
response = await dispatch("User", {
    "operations": [
        {"id": "create", "method": "create_user", "args": {"user_name": "David"}},
        {
            "method": "get_users",
            "args": {},
            "when": {"op": "create", "outcome": "error", "category": "already_exists"},
        },
    ]
}, manager.tool_specs)
```

Si la operación `create` falla con categoría `already_exists`, se
ejecuta `get_users`. Si `create` tiene éxito, `get_users` se skipea
(reportado pero no ejecutado).

---

### Nivel 17 — Clase como singleton vs instancias frescas

```python
# Singleton (default): una sola instancia para todas las llamadas
Service(name="Order", service=Order, singleton=True)

# Instancia fresca por llamada al manager (no por operación dentro del batch)
Service(name="Order", service=Order, singleton=False)

# Constructor con argumentos
Service(
    name="DB",
    service=DatabaseService,
    args=("postgresql://localhost/mydb",),
    kwargs={"pool_size": 10},
)
```

---

### Nivel 18 -- Middleware

Intercepta llamadas a tools para logging, validacion, sanitizacion o control de acceso.

#### Middleware vs ToolMiddleware

Hay **dos tipos** de middleware. No son intercambiables: cada uno vive en un nivel distinto.

| Tipo | Que hace | Donde se registra | Filtra por metodo? |
|------|----------|-------------------|--------------------|
| `Middleware` | Intercepta la llamada **completa** a la tool (el batch de operaciones) | `ToToolManager(middlewares=[...])` (global) | No, corre siempre |
| `ToolMiddleware` | Intercepta **metodos individuales** dentro de un servicio | `Service(middlewares=[...])` (local) | Si, via `include`/`exclude` |

**Por que estan en capas separadas?**

`ToolMiddleware` opera a nivel de metodo individual: envuelve cada metodo
en la dispatch table con `is_allowed()` (linea 301 de `manager.py`). Por eso
**solo puede vivir en `Service.middlewares`** -- necesita acceso a los nombres
de los metodos para filtrar. Si lo pusieras en el manager level, no tendria
sense porque no sabe que metodos tiene cada servicio.

`Middleware` opera a nivel de tool completa: envuelve el `dispatch_call` entero
(linea 247 de `manager.py`). Corre una vez por tool call, no por metodo.
Y explicitamente **salta** los `ToolMiddleware` (linea 248: `if isinstance(mw, ToolMiddleware): continue`).

En resumen:
- **Global** (`ToToolManager`) = solo `Middleware` (logging, metricas, rate limiting)
- **Local** (`Service`) = `Middleware` + `ToolMiddleware` (auth, sanitizacion por metodo)

#### Ejemplo: Middleware global (solo Middleware)

```python
from to_tool_manager import Middleware

class LoggingMiddleware(Middleware):
    async def dispatch(self, func, /, *args, **kw):
        print(f"[LOG] Ejecutando tool...")
        response = await func(*args, **kw)
        print(f"[LOG] Completado")
        return response

# Solo Middleware en el manager (ToolMiddleware no iria aca)
manager = ToToolManager([service], middlewares=[LoggingMiddleware()])
```

#### Ejemplo: ToolMiddleware local (solo en Service)

```python
from to_tool_manager import ToolMiddleware, ToolResponse, ToolError

class AuthMiddleware(ToolMiddleware):
    def __init__(self):
        # Solo corre para estos dos metodos del servicio
        super().__init__(include=["create_user", "delete_user"])

    async def dispatch(self, func, /, *args, **kw):
        if not self.is_authenticated():
            return ToolResponse(
                error=ToolError(
                    category=frozenset({"authentication_error"}),
                    message="No autorizado",
                    exception_type="AuthError",
                    retryable=False,
                )
            )
        return await func(*args, **kw)

# ToolMiddleware SOLO va en Service.middlewares
Service(
    name="User",
    service=User,
    middlewares=[AuthMiddleware(include=["create_user"])],
)
```

#### Ejemplo: Combinacion (global + local + desactivar)

```python
manager = ToToolManager(
    [order_service],
    middlewares=[LoggingMiddleware()],       # Middleware GLOBAL
)

order_service = Service(
    name="Order",
    service=Order,
    middlewares=[AuthMiddleware(include=["create"])],   # ToolMiddleware LOCAL
    disable_middlewares=["LoggingMiddleware"],            # desactiva el global
)
```

#### Diagrama de secuencia: cadena de middlewares

```
  LLM                  ToToolManager          LoggingMW(M)       AuthMW(TM)         Service
   |                        |                     |                |                   |
   |-- tool_call("Order") ->|                     |                |                   |
   |                        |                     |                |                   |
   |                        |-- _resolve_middlewares(service) ---->|                   |
   |                        |   1. globals: [LoggingMW]           |                   |
   |                        |   2. - disable_middlewares           |                   |
   |                        |   3. + locals: [AuthMW]             |                   |
   |                        |   resolved: [LoggingMW, AuthMW]     |                   |
   |                        |                     |                |                   |
   |                        |-- _apply_middlewares() ------------->|                   |
   |                        |   SKIPS AuthMW (isinstance check)   |                   |
   |                        |   solo envuelve con LoggingMW       |                   |
   |                        |                     |                |                   |
   |                        |                     |-- dispatch -->|                   |
   |                        |                     |                |-- is_allowed?     |
   |                        |                     |                |   create: SI      |
   |                        |                     |                |-- dispatch(func)->|
   |                        |                     |                |                   |-- func(args)
   |                        |                     |                |                   |< ToolResponse
   |                        |                     |                |< ToolResponse     |
   |                        |                     |< ToolResponse  |                   |
   |                        |< ToolResponse       |                |                   |
   |< ToolResponse          |                     |                |                   |
   |                        |                     |                |                   |

  Para "get_orders" (no esta en include de AuthMW):
   |                        |                     |                |                   |
   |                        |-- _apply_middlewares() ------------->|                   |
   |                        |                     |-- dispatch -->|                   |
   |                        |                     |                |-- is_allowed?     |
   |                        |                     |                |   get_orders: NO  |
   |                        |                     |                |   retorna         |
   |                        |                     |                |   ToolResponse    |
   |                        |                     |   sin wrappear |   directamente    |
   |                        |                     |< ToolResponse  |                   |
   |                        |< ToolResponse       |                |                   |
   |< ToolResponse          |                     |                |                   |
```

#### Para Modules

Los middlewares del modulo se apilan como "globales" del sub-manager interno:

```
  Module(name="Commerce", middlewares=[ModuleMW])
      |
      v
  sub-ToToolManager:
    global_middlewares = [ManagerMW] + [ModuleMW]
      |
      v
  Cada Service dentro del modulo resuelve:
    1. ManagerMW + ModuleMW  (como "globales" del sub-manager, solo Middleware)
    2. - disable_middlewares del service
    3. + middlewares locales del service (Middleware + ToolMiddleware)
```

**Orden de ejecucion:** globales (solo `Middleware`) -> eliminados por `disable_middlewares` -> locales del servicio (`Middleware` + `ToolMiddleware`).

---

### Nivel 19 -- Caso completo: pydantic-ai + planner + streaming

El planner se conecta al agent via `planner.build_tools()`, que devuelve
4 tools (`create_plan`, `execute_plan`, `update_plan_step`, `get_plan`).
Estas tools se pasan al agent como toolsets adicionales, y el LLM decide
cuando usarlas.

#### Ejemplo corregido

```python
import asyncio
from pydantic import BaseModel
from to_tool_manager import Service, ToToolManager
from to_tool_manager.adapters.pydantic_ai import build_agent, run_streaming
from to_tool_manager.core.planner import (
    Step, StepOperation, ServiceDependency, ServiceDependencyGraph,
)

# 1. Definir servicios
class Product:
    def __init__(self):
        self._catalog = {"gpu": 500.0, "cpu": 300.0}

    def add_product(self, name: str, price: float):
        self._catalog[name] = price
        return f"Product '{name}' added at ${price}"

    def get_products(self):
        return self._catalog

class ProductAlreadyExistsError(Exception): ...
class OrderAlreadyExistsError(Exception): ...
class OrderNotFoundError(Exception): ...

# 2. Configurar manager
manager = ToToolManager([
    Service(
        name="Order", service=Order, description="Manages customer orders.",
        error_map={OrderAlreadyExistsError: ("already_exists", False)},
    ),
    Service(name="User", service=User, description="Manages system users."),
    Service(
        name="Product", service=Product, description="Product catalog.",
        error_map={ProductAlreadyExistsError: ("already_exists", False)},
    ),
])

# 3. Configurar planner con dependencias
graph = ServiceDependencyGraph(dependencies=[
    ServiceDependency(source="Order", target="User", reason="Orders need users"),
    ServiceDependency(source="Order", target="Product", reason="Orders reference products"),
])
planner = manager.with_planner(dependency_graph=graph)

# 4. Crear agente con las tools del planner
class BusinessReply(BaseModel):
    summary: str
    details: dict

# planner.build_tools() devuelve 4 tools: create_plan, execute_plan,
# update_plan_step, get_plan. Se pasan como toolsets adicionales.
planner_tools = planner.build_tools()

agent = build_agent(
    "groq:llama-3.1-8b-instant",
    manager,
    output_type=BusinessReply,
    name="business-agent",
)

# Registrar las tools del planner en el agent
for pt in planner_tools:
    agent.tools.append(pt["func"])

# 5. Ejecutar
async def main():
    result = await agent.run(
        "Creá el usuario Ana, agregá el producto 'monitor' a $200, "
        "y creá una orden para ella. Usá el planner para coordinar."
    )
    print(result.output)

asyncio.run(main())
```

#### Diagrama de secuencia: planner via agent

```
  Usuario              Agent                 Planner             Service
    |                    |                     |                    |
    | "Creá usuario,     |                     |                    |
    |  producto y orden" |                     |                    |
    |------------------->|                     |                    |
    |                    |                     |                    |
    |                    |-- LLM decide:       |                    |
    |                    |   crear plan primero|                    |
    |                    |                     |                    |
    |                    |-- create_plan ----->|                    |
    |                    |   steps: [          |                    |
    |                    |     {create_user},  |                    |
    |                    |     {add_product},  |                    |
    |                    |     {create_order}  |                    |
    |                    |   ]                 |                    |
    |                    |                     |                    |
    |                    |                     |-- Valida deps:     |
    |                    |                     |   Order depende    |
    |                    |                     |   de User+Product  |
    |                    |                     |   OK: User y       |
    |                    |                     |   Product van      |
    |                    |                     |   primero          |
    |                    |<-- plan_id ---------|                    |
    |                    |                     |                    |
    |                    |-- LLM decide:       |                    |
    |                    |   ejecutar plan     |                    |
    |                    |                     |                    |
    |                    |-- execute_plan --->|                    |
    |                    |   plan_id: "abc"   |                    |
    |                    |                    |                    |
    |                    |                    |-- Step 1+2         |
    |                    |                    |   (independientes): |
    |                    |                    |                    |-- User.create("Ana")
    |                    |                    |                    |<-- "User 'Ana' created"
    |                    |                    |                    |-- Product.add("monitor",200)
    |                    |                    |                    |<-- "Product added"
    |                    |                    |                    |
    |                    |                    |-- Step 3           |
    |                    |                    |   (depende 1+2):   |
    |                    |                    |                    |-- Order.create("monitor")
    |                    |                    |                    |<-- "Order created"
    |                    |                    |                    |
    |                    |<-- plan completado -|                    |
    |                    |                     |                    |
    |                    |-- LLM genera        |                    |
    |                    |   respuesta final   |                    |
    |<-- BusinessReply --|                     |                    |
```

#### La diferencia clave

**Sin planner:** el LLM llama directamente a `User.create()`, `Product.add()`,
`Order.create()` como tools separadas. No hay validacion de dependencias,
no hay batching paralelo, no hay tracking de estado.

**Con planner:** el LLM usa `create_plan` para definir la secuencia de pasos,
y `execute_plan` para ejecutarlos. El planner:
- Valida que las dependencias se respeten (Order no puede ir antes de User)
- Ejecuta steps independientes en paralelo (User y Product simultaneamente)
- Trackea estado de cada step (pending/in_progress/completed/failed)
- Emite eventos para UIs en tiempo real

---

------------------->|                     |                    |
    |                    |                     |                    |
    |                    |-- LLM decide:       |                    |
    |                    |   crear plan primero|                    |
    |                    |                     |                    |
    |                    |-- create_plan ----->|                    |
    |                    |   steps: [          |                    |
    |                    |     {create_user},  |                    |
    |                    |     {add_product},  |                    |
    |                    |     {create_order}  |                    |
    |                    |   ]                 |                    |
    |                    |                     |                    |
    |                    |                     |-- Valida deps:     |
    |                    |                     |   Order depende    |
    |                    |                     |   de User+Product  |
    |                    |                     |   OK: User y       |
    |                    |                     |   Product van      |
    |                    |                     |   primero          |
    |                    |<-- plan_id ---------|                    |
    |                    |                     |                    |
    |                    |-- LLM decide:       |                    |
    |                    |   ejecutar plan     |                    |
    |                    |                     |                    |
    |                    |-- execute_plan --->|                    |
    |                    |   plan_id: "abc"   |                    |
    |                    |                    |                    |
    |                    |                    |-- Step 1+2         |
    |                    |                    |   (independientes): |
    |                    |                    |                    |-- User.create("Ana")
    |                    |                    |                    |<-- "User 'Ana' created"
    |                    |                    |                    |-- Product.add("monitor",200)
    |                    |                    |                    |<-- "Product added"
    |                    |                    |                    |
    |                    |                    |-- Step 3           |
    |                    |                    |   (depende 1+2):   |
    |                    |                    |                    |-- Order.create("monitor")
    |                    |                    |                    |<-- "Order created"
    |                    |                    |                    |
    |                    |<-- plan completado -|                    |
    |                    |                     |                    |
    |                    |-- LLM genera        |                    |
    |                    |   respuesta final   |                    |
    |<-- BusinessReply --|                     |                    |
```

#### La diferencia clave

**Sin planner:** el LLM llama directamente a `User.create()`, `Product.add()`,
`Order.create()` como tools separadas. No hay validacion de dependencias,
no hay batching paralelo, no hay tracking de estado.

**Con planner:** el LLM usa `create_plan` para definir la secuencia de pasos,
y `execute_plan` para ejecutarlos. El planner:
- Valida que las dependencias se respeten (Order no puede ir antes de User)
- Ejecuta steps independientes en paralelo (User y Product simultaneamente)
- Trackea estado de cada step (pending/in_progress/completed/failed)
- Emite eventos para UIs en tiempo real

---

---

## Ejemplos completos

### `example/` — App de comercio completa (FastAPI + HTMX)

Aplicación de comercio completa con:
- SQLModel + SQLite (WAL mode)
- Capas: Router → Controller → Service → Repository
- AI agent integrado con streaming via SSE
- UI admin con HTMX + Jinja2
- Suite completa de tests

```bash
cd example
python run.py                    # iniciar en localhost:8000
python util/seed_data.py         # sembrar datos de prueba
pytest test/                     # correr tests
```

### `example_ui_pydantic/` — Agente standalone con UI web

Ejemplo mínimo con pydantic-ai, sin base de datos:
- Clases plain con storage en memoria
- Módulos, middlewares personalizados
- Una línea para UI web: `agent.to_web()`

```bash
cd example_ui_pydantic
python ui_exe.py                 # iniciar en localhost:5000
```

### Patrón de uso típico

```python
# 1. Clases de negocio
class Order:
    def create(self, product_name: str): ...
    def get_orders(self): ...

# 2. Registrar
manager = ToToolManager([
    Service(name="Order", service=Order, error_map={...}),
    Service(name="User", service=User, error_map={...}),
])

# 3. Agente
agent = build_agent("groq:llama-3.1-8b-instant", manager)
result = await agent.run("message")

# 4. O web UI
app = agent.to_web()
```

---

## Manejo de errores

Nunca uses string-matching sobre mensajes. Definí tus propias
excepciones de dominio y mapealas explícitamente en `error_map`. Sin
mapear, los defaults son: `ValueError`/`TypeError` → `validation_error`
(reintentable); `KeyError`/`LookupError` → `not_found`; el resto →
`unclassified` sanitizado, no reintentable.

---

## Por qué es agnóstico

- `to_tool_manager` (core) solo usa `inspect`, `dataclasses`, `re` y
  `asyncio` de la stdlib. Nunca importa pydantic-ai, fastmcp, ni langchain.
- Todo lo específico de un framework vive en `to_tool_manager/adapters/`.
  Si aparece un framework nuevo, se agrega un adapter; el core no se toca.
- Probado end-to-end: el mismo `manager.tool_specs` corre sin cambios
  contra un `Agent` real de pydantic-ai y contra un servidor `FastMCP`
  real, con `pyright` en 0 errores sobre todo el paquete.