# ToToolManager Example

A full-featured demo showing how `to_tool_manager` turns plain Python services into AI-agent-callable tools. The example covers a **multi-domain platform** -- users, orders, inventory, payments, notifications, authentication, and a chat interface -- all wired together as tools an LLM can invoke autonomously.

---

## Table of Contents

- [Why to_tool_manager](#why-to_tool_manager)
- [What This Example Demonstrates](#what-this-example-demonstrates)
- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Running the App](#running-the-app)
- [Step-by-Step Walkthrough](#step-by-step-walkthrough)
  - [1. Define Your Business Services](#1-define-your-business-services)
  - [2. Define Typed Input/Output Models](#2-define-typed-inputoutput-models)
  - [3. Map Exceptions to Error Categories](#3-map-exceptions-to-error-categories)
  - [4. Wrap Services with Service](#4-wrap-services-with-service)
  - [5. Group Services with Module](#5-group-services-with-module)
  - [6. Assemble the ToToolManager](#6-assemble-the-tooloolmanager)
  - [7. Build the AI Agent](#7-build-the-ai-agent)
  - [8. Add Middlewares (optional)](#8-add-middlewares-optional)
- [Complexity Assessment](#complexity-assessment)
- [Available Services](#available-services)
- [Available Modules](#available-modules)
- [Request Flow](#request-flow)
- [Testing](#testing)

---

## Why to_tool_manager

Exposing Python services to an AI agent typically requires:

1. Writing tool schemas manually (JSON Schema per function).
2. Wiring each tool into a framework-specific agent API.
3. Handling errors, sanitizing responses, and keeping everything in sync.

**to_tool_manager eliminates all of this.** You write standard Python service classes with typed Pydantic models, and the library handles:

- **Automatic tool generation** -- service methods become LLM-callable tools with zero schema boilerplate.
- **Error mapping** -- Python exceptions become categorized, retryable error strings the AI understands.
- **Response sanitization** -- middlewares strip sensitive fields (passwords, UUIDs) before they reach the model.
- **Module grouping** -- related services are bundled into sub-agents with their own system prompts.
- **Adapter support** -- works with `pydantic-ai` (and other frameworks) out of the box.

The result: you write business logic, and `to_tool_manager` bridges the gap between your code and the AI.

---

## What This Example Demonstrates

| Domain | Services | What the AI Can Do |
|---|---|---|
| **Users** | `user_service` | Create, retrieve, update, delete users |
| **Orders** | `order_service` | Place orders, update status, cancel orders |
| **Inventory** | `inventory_service` | Manage products, check/adjust stock levels |
| **Payments** | `payment_service` | Process payments, issue refunds, query records |
| **Notifications** | `notification_service` | Send email, SMS, or push notifications |
| **Authentication** | `auth_service` | Login, refresh tokens, validate access |
| **Chat** | `chat_service` | Manage chat sessions and message history |

The AI can **combine** these services freely -- for example, placing an order triggers stock validation, payment processing, and a notification, all orchestrated by the model without any glue code.

---

## Architecture Overview

```
+-----------------------------------------------------------+
|                    Frontend (HTMX)                         |
|              POST /api/chat/...                            |
+----------------------------+------------------------------+
                             |
+----------------------------v------------------------------+
|                   FastAPI Router                           |
|            Chat endpoint receives message                  |
+----------------------------+------------------------------+
                             |
+----------------------------v------------------------------+
|              ToToolManager                                 |
|  +-----------+ +-----------+ +------------+ +----------+  |
|  |  Users    | | Commerce  | |   Comm     | |   Chat   |  |
|  |  Service  | |  Module   | |   Module   | | Service  |  |
|  |           | | (inv +    | | (notif +   | |          |  |
|  |           | |  orders   | |   auth)    | |          |  |
|  |           | |+payment)  | |            | |          |  |
|  +-----------+ +-----------+ +------------+ +----------+  |
+----------------------------+------------------------------+
                             |
+----------------------------v------------------------------+
|           pydantic-ai Agent (LLM + Tools)                 |
|         agent.run_stream(message) -> SSE tokens            |
+-----------------------------------------------------------+
```

---

## Prerequisites

- **Python 3.10+**
- **An LLM provider API key** (Groq, OpenAI, Anthropic, etc. -- anything supported by `pydantic-ai`)
- Create a `.env` file in this directory:

```env
GROQ_API_KEY=your_groq_api_key_here
```

---

## Running the App

```bash
# From the example directory
pip install -r requirements.txt

# Start the server
python run.py
```

The app starts at `http://localhost:8000`. On first launch it creates an SQLite database and seeds it with sample data (users, products, orders, payments, notifications).

---

## Step-by-Step Walkthrough

### 1. Define Your Business Services

Write standard Python classes with async methods. Each method accepts a typed Pydantic model as input and returns a model or dict.

```python
# app/service/user.py
class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.__repo = repo

    async def get_user(self, data: GetUser):
        user = self.__repo.get(data.user_id)
        if user is None:
            raise NotFoundException("User", data.user_id)
        return user

    async def create_user(self, data: CreateUser):
        existing = self.__repo.find_by_email(data.email)
        if existing:
            raise AlreadyExistsException("User", "email", data.email)
        return self.__repo.create(data)

    async def list_users(self):
        return self.__repo.list_all()
```

**Key points:**
- Methods are `async` -- `to_tool_manager` awaits them automatically.
- Input types are Pydantic models -- the library extracts parameter schemas from them.
- Errors are raised as exceptions -- the `ErrorMap` (step 3) translates them.

### 2. Define Typed Input/Output Models

Pydantic models serve as both the AI's parameter schema and runtime validation:

```python
# app/types/user.py
from pydantic import BaseModel
from uuid import UUID

class CreateUser(BaseModel):
    name: str
    email: str
    password: str

class GetUser(BaseModel):
    user_id: UUID

class UpdateUser(BaseModel):
    name: str | None = None
    email: str | None = None
```

The LLM sees these fields as tool parameters with types and descriptions -- no manual JSON Schema needed.

### 3. Map Exceptions to Error Categories

Define how Python exceptions translate to AI-friendly error categories:

```python
from to_tool_manager import ErrorMap
from app.exception import NotFoundException, AlreadyExistsException, ValidationException

ErrorMap()
    .map(NotFoundException, category="not_found")
    .map(AlreadyExistsException, category="already_exists")
    .map(ValidationException, category="validation_error", retryable=True)
```

**How it works:**
- `category` -- a string the AI receives, helping it understand *what went wrong*.
- `retryable=True` -- hints the AI can attempt the operation again (e.g., with corrected input).

When the service raises `ValidationException`, the AI receives `"validation_error"` and knows to retry. When it raises `NotFoundException`, the AI gets `"not_found"` and understands the resource doesn't exist.

### 4. Wrap Services with Service

Each service is wrapped in a `Service` instance that tells the AI what the service does:

```python
from to_tool_manager import Service, ErrorMap

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

| Parameter | Purpose |
|---|---|
| `name` | Unique identifier the AI uses to reference the service |
| `service` | The actual Python class to instantiate |
| `description` | Natural-language description -- the AI uses this to decide when to call the service |
| `error_map` | Maps exceptions to categorized error strings |
| `args` | Positional arguments passed to the service constructor |
| `singleton` | If `True`, a single instance is reused across calls |
| `middlewares` | List of middleware classes that intercept tool responses before they reach the AI |

### 5. Group Services with Module

Modules cluster related services into a sub-agent with its own system prompt:

```python
from to_tool_manager import Module

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

- `description` -- helps the top-level AI decide which module to delegate to.
- `system_prompt` -- instructs the sub-agent on domain-specific behavior.
- `services` -- the tools available inside this module.

### 6. Assemble the ToToolManager

Collect all services and modules into a single manager:

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

Global middlewares (like `SensitiveFieldMiddlewareAI`) apply to **every** tool call. Service-level middlewares apply only to that specific service.

### 7. Build the AI Agent

The `pydantic-ai` adapter converts the manager into an agent:

```python
from to_tool_manager.adapters.pydantic_ai import build_agent

agent = build_agent(
    model="groq:openai/gpt-oss-120b",
    manager=manager,
    system_prompt=SYSTEM_PROMPT,
)

# One-shot
response = await agent.run("Create a new user named Alice")

# Streaming
async for token in agent.run_stream("List all users"):
    print(token, end="", flush=True)
```

### 8. Add Middlewares (optional)

Middlewares intercept tool responses before they reach the AI. Two types exist:

**Global middleware** (`Middleware`) -- applied to every tool call:

```python
from to_tool_manager.security.middleware import Middleware
from to_tool_manager.core.types import ToolResponse

class SensitiveFieldMiddlewareAI(Middleware):
    async def dispatch(self, func, /, *args, **kw):
        response: ToolResponse = await func(*args, **kw)
        if response.error is not None:
            return response
        return self._sanitize(response)
```

**Service middleware** (`ToolMiddleware`) -- applied to a single service:

```python
from to_tool_manager.security.middleware import ToolMiddleware

class RemoverPasswordsMiddlewareAI(ToolMiddleware):
    async def dispatch(self, func, /, *args, **kw):
        response = await func(*args, **kw)
        if response.error is not None:
            return response
        return self._sanitize(response)
```

Common use cases: strip passwords, remove internal UUIDs, redact PII, log tool calls.

---

## Complexity Assessment

| Aspect | Rating | Notes |
|---|---|---|
| **Setup** | Low | Create models, wrap services, done |
| **Boilerplate** | Minimal | No manual JSON schemas, no framework glue |
| **Learning curve** | Low | If you know Python + Pydantic, you already know 80% of it |
| **Integration** | Single call | `build_agent()` connects everything to the LLM |
| **Maintenance** | Low | Add a new service = add one `build_*` function and register it |

**Compared to writing tools manually:**

| Task | Without to_tool_manager | With to_tool_manager |
|---|---|---|
| Define tool schema | Write JSON Schema per parameter | Use Pydantic models (auto-extracted) |
| Wire into agent | Framework-specific code per tool | `build_agent(manager=...)` |
| Error handling | Custom error strings per tool | `ErrorMap().map(Exception, category="...")` |
| Sanitize responses | Manual post-processing per endpoint | Middleware pipeline |
| Group related tools | Manual sub-agent orchestration | `Module(system_prompt=..., services=[...])` |

**When to use it:**
- You have Python services and want an AI agent to call them.
- You need error handling that the AI can reason about.
- You want response sanitization without modifying service code.
- You are building multi-domain agents that delegate to specialized sub-agents.

**When it may not fit:**
- Single, trivial functions with no domain logic (just use the LLM's native tools).
- Non-Python stacks (the library is Python-only).

---

## Available Services

| Service | Description | Key Methods |
|---|---|---|
| `user_service` | User account CRUD | `create_user`, `get_user`, `update_user`, `delete_user`, `list_users` |
| `order_service` | Customer order management | `create_order`, `get_order`, `update_order_status`, `cancel_order`, `list_orders` |
| `inventory_service` | Product catalog and stock | `create_product`, `get_product`, `adjust_stock`, `list_products` |
| `payment_service` | Payment processing and refunds | `process_payment`, `refund_payment`, `get_payment`, `list_payments` |
| `notification_service` | Notifications via email, SMS, push | `send_notification`, `get_notification`, `list_notifications` |
| `auth_service` | Login, token refresh, validation | `login`, `refresh_token`, `validate_token` |
| `chat_service` | Chat sessions and messages | `create_session`, `get_session`, `add_message`, `get_messages` |

---

## Available Modules

| Module | Contains | System Prompt Focus |
|---|---|---|
| `commerce` | inventory + order + payment | Stock validation, order-payment consistency |
| `communication` | notification + auth | Correct recipient, appropriate channel, token management |

---

## Request Flow

```
User sends message (e.g., "Order 3 units of Widget X for user Alice")
  |
  v
POST /api/chat/sessions/{chat_id}/send
  |
  +-- Assembles ToToolManager with all services + modules
  +-- build_agent() creates AI agent with LLM + tools
  |
  v
agent.run_stream(message)
  |
  +-- AI decides: "I need to call commerce module"
  |    +-- inventory_service.get_product(...)     -> checks stock
  |    +-- order_service.create_order(...)        -> places order
  |    +-- payment_service.process_payment(...)   -> charges user
  |
  +-- Each tool call goes through:
  |    +-- Service method execution
  |    +-- ErrorMap exception translation
  |    +-- Middleware response sanitization
  |    +-- ToolResponse returned to AI
  |
  +-- AI formulates natural-language reply
  |
  v
Tokens stream to frontend via SSE (Server-Sent Events)
```

---

## Testing

```bash
# From the example directory
pytest test/ -v
```

Tests cover all API endpoints (REST and chat) and use an isolated SQLite test database.

---

## Summary

`to_tool_manager` reduces the gap between **writing Python services** and **exposing them to AI agents** to a single abstraction layer. You focus on business logic; the library handles schema generation, error mapping, response sanitization, and agent integration.

The total integration code for 7 services + 2 modules in this example is ~100 lines in `agent.py`. Without `to_tool_manager`, that would easily be 500+ lines of manual tool definitions, error handling, and framework wiring.
