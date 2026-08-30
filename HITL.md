# Human-in-the-Loop (HITL) Authorization

Framework-agnostic authorization layer for `to_tool_manager` that pauses tool execution and waits for human TOTP code confirmation.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Core API](#core-api)
- [Middleware](#middleware)
- [Framework Integration](#framework-integration)
  - [FastAPI + Jinja2](#fastapi--jinja2)
  - [Custom Framework](#custom-framework)
- [TOTP Validator](#totp-validator)
- [Use Cases](#use-cases)
- [When to Use HITL](#when-to-use-hitl)

---

## Overview

The HITL module solves one problem: **some tool operations require human confirmation before executing**.

Instead of hardcoding UI logic into the middleware, the core provides:

1. **Token generation** with configurable TTL (default: 2 minutes)
2. **Async wait mechanism** via `asyncio.Future`
3. **AuthorizationRequired exception** that frameworks catch and handle however they want

The framework (FastAPI, Flask, Django, etc.) decides how to present the authorization UI. The core doesn't know about HTTP, templates, or browsers.

### Key Components

| Component | Purpose |
|-----------|---------|
| `HumanInTheLoop` | Core class: token management, async wait, resolve |
| `AuthorizationRequired` | Exception raised by middleware - framework catches it |
| `AuthorizationRequest` | Data about a pending request (token, method, args, TTL) |
| `AuthorizationValidator` | Protocol for plugging in your TOTP provider |
| `AuthorizationRequiredMiddleware` | `ToolMiddleware` subclass that triggers HITL |

---

## Architecture

```
Agent calls tool
       |
       v
AuthorizationRequiredMiddleware.dispatch()
       |
       v
hitl.request_authorization(method, args)
       |
       +-- Creates token (hex, 12 chars)
       +-- Stores pending request with TTL
       +-- raise AuthorizationRequired(token, request)
              |
              v
       Framework catches exception
              |
              +-- GET /authorize/{token} -> render template
              |                         -> user enters TOTP code
              |                         -> POST /authorize/{token}
              |
              +-- hitl.resolve(token, code)
                     |
                     +-- Validates with AuthorizationValidator (optional)
                     +-- Sets Future result
                     +-- Returns True/False
                            |
                            v
       Middleware receives code from wait_for_resolution()
              |
              +-- code is valid -> continue with func(*args, **kw)
              +-- code is invalid/expired -> return ToolResponse(error=...)
```

---

## Quick Start

```python
from to_tool_manager import Service, ToToolManager
from to_tool_manager.security.hitl import (
    HumanInTheLoop,
    AuthorizationRequired,
)
from to_tool_manager.security.middleware import AuthorizationRequiredMiddleware

# 1. Create HITL instance
hitl = HumanInTheLoop(ttl_seconds=120)

# 2. Create middleware
auth_mw = AuthorizationRequiredMiddleware(hitl, include=["delete_order"])

# 3. Register service with middleware
service = Service(
    name="Order",
    service=Order,
    middlewares=[auth_mw],
)
manager = ToToolManager([service])

# 4. In your framework, catch AuthorizationRequired
# (see Framework Integration section below)
```

---

## Core API

### `HumanInTheLoop`

```python
from to_tool_manager.security.hitl import HumanInTheLoop

hitl = HumanInTheLoop(
    validator=my_validator,  # Optional[AuthorizationValidator]
    ttl_seconds=120.0,       # Token TTL in seconds
)
```

#### `request_authorization(method, args, message)`

Creates a token and **always raises** `AuthorizationRequired`. This method never returns.

```python
try:
    await hitl.request_authorization(
        method="delete_order",
        args={"order_id": "123"},
        message="Confirm deletion of order #123",
    )
except AuthorizationRequired as exc:
    # exc.token -> "a1b2c3d4e5f6"
    # exc.request -> AuthorizationRequest
    print(f"Token: {exc.token}")
    print(f"Expires: {exc.request.expires_at}")
```

#### `resolve(token, code)`

Validates the code and resolves the pending authorization. Returns `True` if successful.

```python
success = hitl.resolve(token="a1b2c3d4e5f6", code="123456")
# True -> code accepted, middleware will continue
# False -> token expired, invalid, or already resolved
```

#### `wait_for_resolution(token, timeout)`

Async method that waits for a code to be submitted. Returns the code or `None` on timeout.

```python
code = await hitl.wait_for_resolution(token="a1b2c3d4e5f6", timeout=120)
if code is None:
    print("Authorization timed out")
```

#### `pending`

Read-only dict of pending authorization requests. Useful for admin/debugging.

```python
for token, request in hitl.pending.items():
    print(f"{token}: {request.method} (expires {request.expires_at})")
```

### `AuthorizationRequest`

```python
@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    token: str
    method: str
    args: dict[str, Any]
    message: str
    created_at: datetime
    expires_at: datetime

    @property
    def is_expired(self) -> bool: ...

    def to_dict(self) -> dict[str, Any]: ...
```

### `AuthorizationRequired`

```python
class AuthorizationRequired(Exception):
    token: str              # The authorization token
    request: AuthorizationRequest  # Full request data
```

---

## Middleware

### `AuthorizationRequiredMiddleware`

Extends `ToolMiddleware` with `include`/`exclude` filtering.

```python
from to_tool_manager.security.middleware import AuthorizationRequiredMiddleware

middleware = AuthorizationRequiredMiddleware(
    human=hitl,
    include=["delete_order", "transfer_funds"],  # Only these methods
    exclude=None,                                  # Or exclude specific ones
    message="Sensitive operation - TOTP required", # Custom message
)
```

The middleware **always raises** `AuthorizationRequired`. It never returns normally - the framework must catch the exception.

---

## Framework Integration

### FastAPI + Jinja2

**1. Create TOTP validator:**

```python
# app/security/totp.py
from to_tool_manager.security.hitl import AuthorizationValidator

class TOTPValidator:
    def __init__(self, secret: str):
        self._secret = secret

    async def validate(self, token: str, code: str, request) -> bool:
        import pyotp
        totp = pyotp.TOTP(self._secret)
        return totp.verify(code, valid_window=1)
```

**2. Create HITL instance:**

```python
# app/security/hitl.py
from to_tool_manager.security.hitl import HumanInTheLoop
from app.security.totp import TOTPValidator

validator = TOTPValidator(secret="JBSWY3DPEHPK3PXP")
human = HumanInTheLoop(validator=validator, ttl_seconds=120)
```

**3. Create authorization endpoints:**

```python
# app/router/web/authorize.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from app.security.hitl import human
from app.templates import templates

authorize_router = APIRouter(tags=["web"])

@authorize_router.get("/authorize/{token}")
async def show_authorize_form(token: str, request: Request):
    pending = human.pending.get(token)
    if not pending or pending.is_expired:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "page/authorize.html", {
        "token": token,
        "method": pending.method,
        "message": pending.message,
    })

@authorize_router.post("/authorize/{token}")
async def submit_authorization(token: str, code: str = Form(...)):
    success = human.resolve(token, code)
    if success:
        return RedirectResponse(f"/authorize/{token}/success", status_code=303)
    return RedirectResponse(f"/authorize/{token}?error=invalid", status_code=303)
```

**4. Register exception handler:**

```python
# app/exception.py
from fastapi import Request
from fastapi.responses import RedirectResponse
from to_tool_manager.security.hitl import AuthorizationRequired

async def authorization_required_handler(request: Request, exc: AuthorizationRequired):
    return RedirectResponse(f"/authorize/{exc.token}", status_code=303)
```

```python
# main.py
from fastapi import FastAPI
from to_tool_manager.security.hitl import AuthorizationRequired
from app.exception import authorization_required_handler

app = FastAPI()
app.exception_handler(AuthorizationRequired)(authorization_required_handler)
```

**5. Create Jinja2 template:**

```html
<!-- frontend/src/page/authorize.html -->
{% extends 'layout/layout.html' %}

{% block title %}Autorizacion Requerida{% endblock %}

{% block content %}
<div class="min-h-[70vh] flex items-center justify-center">
  <div class="w-full max-w-md">
    <div class="text-center mb-8">
      <h1 class="text-2xl font-display font-bold text-ink-900">{{ message }}</h1>
      <p class="text-sm text-ink-600 mt-2">Metodo: <code>{{ method }}</code></p>
      <p class="text-xs text-ink-500 mt-1">Expira en 2 minutos</p>
    </div>

    <div class="hud-corners bg-paper-100 rounded-xl shadow-panel border border-paper-300 p-8">
      <form method="POST" action="/authorize/{{ token }}">
        <div class="space-y-5">
          <div>
            <label class="block text-xs font-mono uppercase tracking-wide text-ink-600 mb-1.5">
              Codigo TOTP
            </label>
            <input type="text"
                   name="code"
                   required
                   autofocus
                   pattern="[0-9]{6}"
                   maxlength="6"
                   class="w-full px-4 py-2.5 bg-paper-100 border border-paper-400 rounded-lg
                          text-ink-900 text-center text-2xl tracking-[0.5em] font-mono"
                   placeholder="000000">
          </div>
          <button type="submit"
                  class="w-full py-2.5 px-4 bg-brand-400 text-ink-950 font-semibold rounded-lg
                         hover:bg-brand-300 shadow-brand transition-colors">
            Autorizar
          </button>
        </div>
      </form>
    </div>
  </div>
</div>
{% endblock %}
```

**6. Register router:**

```python
# app/router/web/__init__.py
from app.router.web.authorize import authorize_router

web_routers = [
    # ... other routers
    authorize_router,
]
```

### Custom Framework

For any other framework (Flask, Django, etc.), implement the same pattern:

1. Catch `AuthorizationRequired` in your error handler
2. Render your template with `exc.token` and `exc.request`
3. Create a POST endpoint that calls `hitl.resolve(token, code)`
4. The middleware (running async in the background) picks up the resolved code

The core is pure Python - no framework dependencies.

---

## TOTP Validator

Implement the `AuthorizationValidator` protocol to plug in your TOTP provider:

```python
from to_tool_manager.security.hitl import AuthorizationValidator, AuthorizationRequest

class MyTOTPValidator:
    async def validate(self, token: str, code: str, request: AuthorizationRequest) -> bool:
        # Example with pyotp:
        import pyotp
        secret = get_secret_for_method(request.method)
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)

        # Example with custom logic:
        # return code == get_expected_code(request.method)

hitl = HumanInTheLoop(validator=MyTOTPValidator())
```

If no validator is set, `resolve()` accepts any 6-digit code.

---

## Use Cases

| Scenario | Why HITL |
|----------|----------|
| Delete production data | Prevent accidental deletion |
| Financial transactions | Regulatory compliance |
| API key rotation | Prevent unauthorized changes |
| Destructive operations | Human verification required |
| Multi-tenant admin actions | Cross-tenant safety |

---

## When to Use HITL

**Use HITL when:**
- Operations are destructive or irreversible
- Regulatory/compliance requires human approval
- Financial transactions need confirmation
- Multi-tenant isolation must be verified

**Don't use HITL when:**
- Operations are read-only
- The agent has full autonomy
- Speed is critical and operations are safe
- You're building a fully automated pipeline