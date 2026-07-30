# ToToolManager - Usage Demo

This is a **demonstration application** that shows how to use the `to_tool_manager` library to expose Python services as AI-agent-callable tools. It is not a production template -- it focuses on illustrating the library's core features through a practical, runnable example.

## Prerequisites

- Python 3.10+
- A Groq API key (or any LLM provider supported by `pydantic-ai`)
- Create a `.env` file in this directory:

```env
GROQ_API_KEY=your_groq_api_key_here
```

## Running the App

```bash
# Install dependencies (from the project root)
pip install -r requirements.txt

# Start the server
python run.py
```

The app will be available at `http://localhost:8000`. On first launch it creates an SQLite database and seeds it with sample data (users, products, orders, payments, notifications).

## How ToToolManager Is Used

### 1. Wrapping Services with `Service`

Each business service is wrapped in a `Service` instance that tells the AI agent what the service does, what constructor arguments it needs, and how to translate errors into meaningful categories.

From `app/controller/agent.py`:

```python
from to_tool_manager import Service, Module, ErrorMap

def build_user_service(session) -> Service:
    repo = UserRepository(session)
    return Service(
        name="user_service",
        service=UserService,
        description="Manages user accounts: create, retrieve, update, and delete users.",
        error_map=(
            ErrorMap()
            .map(NotFoundException, category="not_found")
            .map(AlreadyExistsException, category="already_exists")
            .map(ValidationException, category="validation_error", retryable=True)
        ),
        args=(repo,),
        singleton=True,
        middlewares=[RemoverPasswordsMiddlewareAI(include=["get_user"])]
    )
```

**Key points:**

| Parameter | Purpose |
|---|---|
| `name` | Unique identifier the AI uses to reference the service. |
| `service` | The actual Python class to instantiate. |
| `description` | Natural-language description the AI uses to decide when to call this service. |
| `error_map` | Maps Python exceptions to categorized error strings. Marking an error as `retryable=True` hints to the AI that it can attempt the operation again. |
| `args` | Positional arguments passed to the service constructor. |
| `singleton` | If `True`, a single instance is reused across calls. |
| `middlewares` | List of middleware classes that intercept tool responses before they reach the AI. |

### 2. Grouping Services with `Module`

Modules let you cluster related services into a sub-agent with its own system prompt:

```python
def build_commerce_module(session) -> Module:
    return Module(
        name="commerce",
        description=(
            "Commerce sub-agent: manages products, orders, and payments. "
            "Use this module when the user's request involves creating or "
            "modifying products, placing orders, processing payments, or "
            "querying commerce-related data."
        ),
        system_prompt=(
            "You are a commerce specialist. You can manage products, "
            "process orders, and handle payments. Always ensure stock "
            "availability before confirming orders and validate payment "
            "amounts match order totals."
        ),
        services=[
            build_inventory_service(session),
            build_order_service(session),
            build_payment_service(session),
        ],
    )
```

The `description` helps the top-level AI decide which module to delegate to. The `system_prompt` instructs the sub-agent on how to behave.

### 3. Assembling the `ToToolManager`

All services and modules are collected into a `ToToolManager` instance:

```python
from to_tool_manager import ToToolManager

manager = ToToolManager([
    build_user_service(session),
    build_order_service(session),
    build_auth_service(session),
    build_inventory_service(session),
    build_payment_service(session),
    build_notification_service(session),
    build_commerce_module(session),
    build_communication_module(session),
],
    middlewares=[SensitiveFieldMiddlewareAI()]
)
```

Global middlewares (like `SensitiveFieldMiddlewareAI`) apply to **all** tools. Service-level middlewares apply only to that specific service.

### 4. Creating the AI Agent

The `pydantic-ai` adapter builds an agent from the manager:

```python
from to_tool_manager.adapters.pydantic_ai import build_agent

agent = build_agent(
    model="groq:openai/gpt-oss-120b",
    manager=manager,
    system_prompt=SYSTEM_PROMPT,
)
```

You can then call `agent.run(message)` for a one-shot response or use `agent.run_stream(message)` for streaming tokens.

### 5. Writing Custom Middlewares

Middlewares intercept tool responses before they reach the AI. Two examples are provided in `app/security/middleware_ai/sanitize.py`:

```python
from to_tool_manager.core.types import ToolResponse
from to_tool_manager.security.middleware import Middleware, ToolMiddleware


class SensitiveFieldMiddlewareAI(Middleware):
    async def dispatch(self, func, /, *args, **kw):
        response: ToolResponse = await func(*args, **kw)
        if response.error is not None:
            return response
        return self._sanitize(response)


class RemoverPasswordsMiddlewareAI(ToolMiddleware):
    async def dispatch(self, func, /, *args, **kw):
        response = await func(*args, **kw)
        if response.error is not None:
            return response
        return self._sanitize(response)
```

- **`Middleware`**: Applied globally to the `ToToolManager`. Intercepts every tool call.
- **`ToolMiddleware`**: Applied to a specific `Service`. Only intercepts calls to that service.

### 6. Error Mapping

The `ErrorMap` translates Python exceptions into categorized, AI-friendly error messages. This lets the AI understand *why* an operation failed and decide whether to retry or inform the user:

```python
ErrorMap()
    .map(NotFoundException, category="not_found")
    .map(AlreadyExistsException, category="already_exists")
    .map(ValidationException, category="validation_error", retryable=True)
```

When the service raises `ValidationException`, the AI receives a `validation_error` category and knows it can retry with corrected input. When it raises `NotFoundException`, the AI gets `not_found` and understands the resource doesn't exist.

## Request Flow Summary

```
User sends chat message
  -> POST /api/chat/sessions/{chat_id}/send
     -> Assembles ToToolManager with all services + modules
     -> build_agent() creates an AI agent with LLM + tools
     -> Background task starts agent.run_stream(message)
        -> AI decides which tools to call based on the user request
        -> ToolManager executes the service method
        -> Middlewares sanitize the response (strip UUIDs, passwords)
        -> AI formulates a natural-language reply
     -> Tokens stream to the frontend via SSE (Server-Sent Events)
```

## Available Services

| Service | Description |
|---|---|
| `user_service` | User account CRUD |
| `order_service` | Customer order management |
| `inventory_service` | Product catalog and stock |
| `payment_service` | Payment processing and refunds |
| `notification_service` | Notifications via email, SMS, push |
| `auth_service` | Login, token refresh, token validation |
| `chat_service` | Chat session and message management |

## Available Modules

| Module | Contains |
|---|---|
| `commerce` | inventory + order + payment |
| `communication` | notification + auth |

## Testing

```bash
# From the example directory
pytest test/ -v
```

Tests cover all API endpoints (REST and chat) and use an isolated SQLite test database.
