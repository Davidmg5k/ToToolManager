# to-tool-manager

> Turn plain Python classes into LLM-callable tools, with middleware, sub-agents and human-in-the-loop — without writing a single tool schema.

**Version:** 0.9.5 | **Python:** >=3.12 | **License:** MIT

---

## Table of Contents

- [What it is](#what-it-is)
- [Why it exists](#why-it-exists)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [How it works](#how-it-works)
  - [Method discovery rules](#method-discovery-rules)
  - [From class to tool](#from-class-to-tool)
  - [Tool naming](#tool-naming)
  - [Error handling](#error-handling)
  - [Middleware resolution and ordering](#middleware-resolution-and-ordering)
- [Core API](#core-api)
  - [`Service`](#service)
  - [`Module`](#module)
  - [`ToToolManager`](#totoolmanager)
  - [`TTMBuilder`](#ttmbuilder)
  - [`DinamicDepend`](#dinamicdepend)
  - [`Include` / `Exclude` / `MethodsType`](#include--exclude--methodstype)
- [Middleware](#middleware)
  - [`Middleware`](#middleware)
  - [`ToolMiddleware`](#toolmiddleware)
  - [`NodeMiddleware`](#nodemiddleware)
  - [`NodeWrapper`](#nodewrapper)
  - [`GraphMiddlewareRunner`](#graphmiddlewarerunner)
- [Human-in-the-Loop](#human-in-the-loop)
  - [`EventEmitter`](#eventemitter)
  - [`HumanInTheLoop`](#humanintheloop)
  - [`HumanInputRetry`](#humaninputretry)
  - [`HumanInTheLoopMiddleware`](#humanintheloopmiddleware)
  - [`HumanInTheLoopToolMiddleware`](#humaninthelooptoolmiddleware)
- [Exceptions](#exceptions)
- [Configuration](#configuration)
- [Examples and use cases](#examples-and-use-cases)
  - [Dependency injection into services](#dependency-injection-into-services)
  - [Async services and DI](#async-services-and-di)
  - [Error mapping and PII scrubbing](#error-mapping-and-pii-scrubbing)
  - [Sub-agents with Module](#sub-agents-with-module)
  - [Disabling inherited middleware](#disabling-inherited-middleware)
  - [Exporting tools to an MCP server](#exporting-tools-to-an-mcp-server)
  - [Gateways and approvals with HITL](#gateways-and-approvals-with-hitl)
  - [Guarding graph transitions](#guarding-graph-transitions)
- [Gotchas and troubleshooting](#gotchas-and-troubleshooting)
- [Development](#development)
- [License](#license)
- [Links](#links)

---

## What it is

`to-tool-manager` is a thin, explicit layer over [pydantic-ai](https://github.com/pydantic/pydantic-ai). You keep your business logic in ordinary Python classes; the library discovers their public methods, derives the JSON schemas from their type hints and docstrings, and assembles a ready-to-use `Agent`.

Four objects cover the whole surface:

| Object | Role |
|---|---|
| `Service` | Wraps one class and exposes its public methods as tools. |
| `Module` | Groups services into a **sub-agent** with its own model, prompt and middleware layer. |
| `ToToolManager` | Orchestrates services and modules into a single `Agent`. |
| `TTMBuilder` | Fluent alternative to `ToToolManager` for declarative assembly. |

Cross-cutting concerns (auth, logging, rate limiting, redaction, human approval) are expressed as **middleware** and attached at the service, module or builder level — never inside your business code.

```
Python class ──> Service ──> Module (optional) ──> ToToolManager / TTMBuilder ──> Agent
                    │
                    └── ToolMiddleware (per method, outermost first)
```

---

## Why it exists

Building an LLM application normally forces you to repeat this loop for every capability:

1. Write the business logic as a plain class.
2. Hand-write a JSON schema for each method the model may call.
3. Register each tool on the agent, wiring dependencies by hand.
4. Repeat auth, logging, rate limiting and audit on every tool.
5. Add human approval for dangerous operations — and re-implement the pause/resume plumbing.

`to-tool-manager` collapses steps 2–5. You declare a class; the library generates the schemas, instantiates your object with the dependencies you provide, wraps each call in the middleware chain you declare, and hands you an `Agent`. Your service class stays free of framework imports and of concern-specific code.

---

## Requirements

| Item | Value |
|---|---|
| Python | `>=3.12` (tested on 3.12 and 3.13) |
| Build backend | `uv_build>=0.8.15,<0.9.0` |
| Runtime deps | `pydantic-ai-slim[cli,openai]`, `pydantic-ai-harness`, `pydantic-ai-skills`, `pydantic-graph`, `subagents-pydantic-ai`, `fastmcp` |
| Model access | Whatever provider your pydantic-ai model needs (OpenAI by default via the `openai` extra) |

**Direct dependencies** (from `pyproject.toml`):

| Package | Constraint |
|---|---|
| `pydantic-ai-slim[cli,openai]` | `>=2.37.0` |
| `pydantic-ai-harness` | `>=0.28.0` |
| `pydantic-ai-skills` | `>=1.4.0` |
| `pydantic-graph` | `>=2.37.0` |
| `subagents-pydantic-ai` | `>=0.2.21` |
| `fastmcp` | `>=4.0.2` |

`cryptography>=50.0.0` is pinned as a transitive override to pick up the PYSEC-2026-3552 fix regardless of what the auth stack resolves to.

---

## Installation

```bash
pip install to-tool-manager
```

Or with `uv`:

```bash
uv add to-tool-manager
```

From source:

```bash
git clone https://github.com/Davidmg5k/ToToolManager.git
cd ToToolManager
uv sync --extra pydantic-ai
```

---

## Quickstart

```python
from to_tool_manager import Service, ToToolManager


class UserManager:
    """In-memory user store."""

    def __init__(self) -> None:
        self._users: dict[str, str] = {}

    def create(self, id: str, name: str) -> str:
        """Create a user.

        Args:
            id: Unique user identifier.
            name: Display name.
        """
        self._users[id] = name
        return f"User {id} created: {name}"

    def get(self, id: str) -> str:
        """Return a user by id."""
        return f"User {id}: {self._users.get(id, 'not found')}"


manager = ToToolManager(
    name="App",
    resources=[
        Service(
            name="users",
            service=UserManager,
            instructions="Use for user creation and lookup.",
        )
    ],
    model="openai:gpt-4o",
)

agent = manager.build_agent()   # ready to use
```

Run it with the pydantic-ai CLI:

```bash
pydantic-ai to_tool_manager.quickstart:agent
```

> Building the agent validates the model, so it needs provider credentials to be present. While developing offline, swap the model for pydantic-ai's built-in test model: `model="test"`. It needs no API key and still exercises discovery, middleware and tool wrapping.

---

## How it works

### Method discovery rules

`Service` inspects the wrapped class with `inspect.getmembers` and keeps only what satisfies **all** of these rules:

| Rule | Behaviour | Source |
|---|---|---|
| Public only | Names starting with `_` are skipped. | `core/main/shared/discover.py:35` |
| No dunders | `__init__`, `__str__`, … are skipped. | `core/main/shared/discover.py:35` |
| **Declared in the class itself** | Methods inherited from a base class are **not** exposed. | `core/main/shared/discover.py:39` |
| Functions only | Class attributes, properties and nested classes are ignored. | `core/main/shared/discover.py:34` |
| `self` stripped | The first parameter is removed from the generated schema. | `core/main/shared/discover.py:43` |

> **Inheritance is the most common surprise.** If `class AdminUser(UserManager)` adds nothing of its own, the agent sees *zero* tools. Re-declare, or wrap a dedicated flat class.

Both `async def` and plain `def` methods are supported, and the generated tool keeps the same flavour.

### From class to tool

For every discovered method the library builds a wrapper:

1. Wrap the method with each allowed `ToolMiddleware` (innermost first).
2. Copy `__name__`, `__qualname__`, `__doc__` and the type annotations from the original method.
3. Rebuild an explicit `inspect.Signature` — `ctx` plus the original parameters as keyword-only — so pydantic-ai emits a real JSON schema instead of a bare `**kwargs`.
4. Register it as `Capability(id=<service name>, instructions=…, defer_loading=True)`.

At call time the wrapper resolves the service instance from `ctx.deps.<service name>`, binds the method to it, and invokes it with keyword arguments.

Because `defer_loading=True`, the tool schemas are only materialised into the model request when the capability is actually used.

### Tool naming

The tool name is the **bare method name**; the service name lives only in the wrapper's `__qualname__` (`users.create`).

| Service | Method | Tool name | Wrapper `__qualname__` |
|---|---|---|---|
| `users` | `create` | `create` | `users.create` |
| `orders` | `create` | `create` | `orders.create` |

> Two services exposing a method with the same name produce two tools with the same name. Give methods distinct names, or split them into separate `Module` sub-agents so only one is loaded at a time.

### Error handling

Exceptions raised inside a service method are **caught and converted into a string** — they never propagate to the agent runtime:

```text
Error in <service>.<method>: <ExceptionType>: <message>
```

```python
class Boom:
    def explode(self) -> str:
        raise ValueError("kaboom")

# Calling the generated tool returns the string:
# 'Error in b.explode: ValueError: kaboom'
```

If you need typed failures, validate inside the method and return a structured result, or translate domain exceptions with a `ToolMiddleware`.

### Middleware resolution and ordering

Two rules govern the chain, and both are easy to get backwards:

**1. Only `ToolMiddleware` wraps service methods.** `Service.build_as_capability` checks `isinstance(mw, ToolMiddleware)` before wrapping (`core/main/service.py:71`). A plain `Middleware` subclass placed in a service, module or builder middleware list is stored but never invoked. To intercept tool calls, always subclass `ToolMiddleware`.

**2. The last middleware in the list is the outermost.** Each middleware wraps the result of the previous one, so the tail of the list runs first:

```python
Service(
    ...,
    middleware=[ToolMW(tag="A"), ToolMW(tag="B")],
)
# Execution order: B-before → A-before → method → A-after → B-after
```

Layers are appended, so **outer layers run first**:

| Layer | Appended when | Relative position |
|---|---|---|
| `Service(middleware=[...])` | Service declaration | Innermost |
| `Module(middleware=[...])` | `build_as_agent()` | Outer |
| `TTMBuilder.add_middleware(...)` | `build()` | Outermost |

---

## Core API

### `Service`

A `@dataclass(slots=True)` describing one class whose public methods become tools. Not a pydantic-ai type — it is converted into a `Capability` on demand.

**Description**: Wraps a class, holds its construction arguments, its middleware and its instructions. Precondition: `service` is a class with at least one public method declared in its own body. Postcondition: `build_as_capability()` returns a `Capability` holding one `Tool` per discovered method.

**Return**: `None` — it is a declaration object; call `build_as_capability()` or let `Module`/`ToToolManager`/`TTMBuilder` do it for you.

**Args** (all keyword arguments, as a dataclass):

- `name`: `str` — *(required)* unique service identifier. Used as the `Capability` id, as the dependency attribute name and as the namespace in wrapper `__qualname__`s. Must be unique within a manager or builder.
- `service`: `type` — *(required)* the class to wrap. Instantiated as `service(*args, **kwargs)`.
- `instructions`: `str` — *(required)* guidance for the LLM about when to reach for this service. Passed verbatim to `Capability.instructions`.
- `middleware`: `List[ToolMiddleware | Middleware] | None` = `[]` — middleware instances for this service. Only `ToolMiddleware` instances are actually applied.
- `disable_middlewares`: `Tuple[str, ...]` = `()` — middleware names to skip when inherited from an outer layer. Matched against `Middleware.name`, which defaults to the class name.
- `include`: `MethodsType | Include | None` = `None` — **currently not applied.** Accepted and stored, but the package never reads it. Use `ToolMiddleware(include=…)` — see [Gotchas](#gotchas-and-troubleshooting).
- `exclude`: `MethodsType | Exclude | None` = `None` — **currently not applied**, same caveat as `include`.
- `args`: `Tuple[Any, ...]` = `()` — positional arguments for `service.__init__`.
- `kwargs`: `Dict[str, Any]` = `{}` — keyword arguments for `service.__init__`.

**Methods**:

#### `Service.add_middleware(middleware)` — method

**Description**: Appends a middleware to this service's list. Precondition: none. Postcondition: `middleware` is the last element of `self.middleware`, creating the list if it was `None`.

**Return**: `None`.

**Args**:

- `middleware`: `ToolMiddleware` — instance to append. Any `Middleware` subclass is accepted by the signature, but only `ToolMiddleware` instances are applied at build time.

**Kwargs**: None.

#### `Service.build_as_capability()` — method

**Description**: Discovers public methods, wraps each with the allowed `ToolMiddleware` instances, and registers the results as a pydantic-ai `Capability`. Precondition: `self.service` is a class. Postcondition: returns a `Capability` with `id=self.name`, `instructions=self.instructions`, `defer_loading=True` and one `Tool` per discovered method.

**Return**: `Capability` — the pydantic-ai capability to attach to an `Agent`. Does not raise for a class with no public methods; you simply get an empty capability.

**Args**: None.

**Kwargs**: None.

#### `Service.service_to_dependency(dinamic_depend)` — method

**Description**: Instantiates the service class and registers the instance on the dependency container. Precondition: `args`/`kwargs` satisfy the class constructor. Postcondition: `dinamic_depend.<name>` is the live service instance. Called for you during `build_agent()`, `build_as_agent()` and `TTMBuilder.add_service()`.

**Return**: `None`.

**Args**:

- `dinamic_depend`: `DinamicDepend` — container that will hold the instance.

**Kwargs**: None.

---

### `Module`

A `@dataclass` grouping services into a sub-agent, each with its own model, prompt, retries and middleware layer.

**Description**: Builds a pydantic-ai `Agent` for its services and wraps it in a `SubAgent`. Precondition: `services` is a non-empty sequence of `Service`. Postcondition: `self.agent` holds the built `Agent` and `self.dependency` the container with every service instance.

**Return**: `None` — a declaration object; call `build_as_agent()` or let `ToToolManager`/`TTMBuilder` do it.

**Args** (all keyword arguments, as a dataclass):

- `name`: `str` — *(required)* sub-agent name.
- `services`: `Sequence[Service]` — *(required)* services exposed by this sub-agent.
- `description`: `str` — *(required)* description handed to the sub-agent `Agent`; this is what the parent model reads when deciding to delegate.
- `capabilities`: `List[Capability] | None` = `None` — extra capabilities merged with the generated ones.
- `middleware`: `List | None` = `None` — middlewares appended to every service on `build_as_agent()`, subject to both `Module.disable_middlewares` and each service's own `disable_middlewares`.
- `disable_middlewares`: `Tuple[str, ...]` = `()` — names this module must not apply to its services. Disabling a middleware the module itself declares raises `SelfDisableMiddlewareError` **at construction time**.
- `model`: `Model | KnownModelName | str | None` = `None` — model for the sub-agent; falls back to the parent's when `None`.
- `instructions`: `Any` = `None` — agent instructions.
- `system_prompt`: `str | Sequence[str]` = `()` — system prompt.
- `model_settings`: `AgentModelSettings | None` = `None` — forwarded to `Agent`.
- `retries`: `int | AgentRetries | None` = `None` — retry budget.
- `validation_context`: `Any | Callable | None` = `None` — forwarded to `Agent`.
- `tools`: `Sequence[Any]` = `()` — extra hand-written tools.
- `toolsets`: `Sequence[AgentToolset] | None` = `None` — extra toolsets.
- `defer_model_check`: `bool` = `False` — skip model validation at construction.
- `end_strategy`: `EndStrategy` = `'graceful'` — `'graceful'`, `'exit'`, `'max'`… (pydantic-ai values).
- `metadata`: `Any` = `None` — forwarded to `Agent`.
- `tool_timeout`: `float | None` = `None` — per-tool timeout in seconds.
- `max_concurrency`: `Any` = `None` — concurrency limit.
- `output_type`: `Any` = `str` — output type of the sub-agent.

**Properties and methods**:

#### `Module.agent` — property

**Description**: Returns the sub-agent's `Agent`.

**Return**: `Agent[DinamicDepend]` — the built agent.

**Raises**: `AgentNotBuiltError` — if `build_as_agent()` has not been called yet.

**Args** / **Kwargs**: None.

The setter accepts an `Agent` and raises `AgentAlreadyBuiltError` if one is already present.

#### `Module.dependency` — property

**Description**: Returns the container holding one instance per service of this module.

**Return**: `DinamicDepend` — the dependency container, populated during `build_as_agent()`.

**Args** / **Kwargs**: None.

#### `Module.build_as_agent()` — method

**Description**: Applies this module's middleware to each service (respecting both disable lists), builds each service's capability, registers every instance on `self.dependency`, constructs the `Agent` and returns it wrapped in a `SubAgent`.

**Return**: `SubAgent[DinamicDepend]` — the sub-agent to hand to `ToToolManager` or `TTMBuilder`.

**Raises**: `AgentAlreadyBuiltError` — on a second call; the `agent` setter refuses to overwrite. Build each `Module` exactly once.

**Args**: None.

**Kwargs**: None.

---

### `ToToolManager`

Registers services and modules, then builds the top-level `Agent`.

**Description**: Holds the resources, exposes them by name and assembles the final agent. Precondition: every item of `resources` is a `Service` or a `Module`. Postcondition: after `build_agent()`, `self.agent` is a valid `Agent` and every service instance is registered on the internal dependency container.

**Return**: `None` — call `build_agent()`.

**Args** (constructor; positional `name` and `resources` are allowed):

- `name`: `str` — *(required)* agent name.
- `resources`: `Sequence[Service | Module]` — *(required)* services and modules to orchestrate.
- `middlewares`: `Sequence[Middleware] | None` = `None` — stored and exposed via `.middlewares`, but **not currently wired into tool-call dispatch**. Use `TTMBuilder.add_middleware()` for a middleware that actually runs.
- `model`: `Model | KnownModelName | str | None` = `None` — LLM model.
- `instructions`: `Any` = `None` — agent instructions.
- `system_prompt`: `str | Sequence[str]` = `()` — system prompt.
- `model_settings`: `AgentModelSettings | None` = `None` — forwarded to `Agent`.
- `retries`: `int | AgentRetries | None` = `None` — retry budget.
- `validation_context`: `Any` = `None` — forwarded to `Agent`.
- `tools`: `Sequence[Any]` = `()` — extra hand-written tools.
- `toolsets`: `Sequence[AgentToolset] | None` = `None` — extra toolsets; the `SubAgents` toolset is appended automatically.
- `defer_model_check`: `bool` = `False` — skip model validation at construction.
- `end_strategy`: `EndStrategy` = `'graceful'` — end strategy.
- `metadata`: `Any` = `None` — forwarded to `Agent`.
- `tool_timeout`: `float | None` = `None` — per-tool timeout in seconds.
- `max_concurrency`: `AnyConcurrencyLimit` = `None` — concurrency limit.
- `output_type`: `Any` = `str` — output type.
- `description`: `str | None` = `None` — agent description.

**Raises**: `InvalidResourceTypeError` — from the constructor, when an item of `resources` is neither `Service` nor `Module`.

> **Duplicate names are not validated here.** Two resources sharing a name silently overwrite each other (`to_tool_manager.py:90-93`). `ServiceAlreadyRegisteredError` and `ModuleAlreadyRegisteredError` come from `TTMBuilder`, which does check.

**Properties and methods**:

#### `ToToolManager.name` — property

**Description**: Returns the orchestrator name.

**Return**: `str` — the name given to the constructor.

**Args** / **Kwargs**: None.

#### `ToToolManager.agent` — property

**Description**: Returns the built agent.

**Return**: `Agent[DinamicDepend]` — the agent created by `build_agent()`.

**Raises**: `AgentNotBuiltError` — if `build_agent()` has not been called.

**Args** / **Kwargs**: None.

#### `ToToolManager.middlewares` — property

**Description**: Returns the middleware sequence given to the constructor.

**Return**: `Sequence[Middleware]` — the registered middlewares.

**Raises**: `MiddlewareNotInitializedError` — if the manager was built with `middlewares=None` and `build_agent()` has not supplied a sequence.

**Args** / **Kwargs**: None.

#### `ToToolManager.services` — property

**Description**: Returns a snapshot of the registered services.

**Return**: `Dict[str, Service]` — a shallow copy keyed by service name; mutating it does not affect the manager.

**Args** / **Kwargs**: None.

#### `ToToolManager.modules` — property

**Description**: Returns a snapshot of the registered modules.

**Return**: `Dict[str, Module]` — a shallow copy keyed by module name.

**Args** / **Kwargs**: None.

#### `ToToolManager.get_service(name)` — method

**Description**: Looks up a resource by name, checking services first and modules second.

**Return**: `Service | Module` — the registered resource.

**Args**:

- `name`: `str` — service or module name.

**Raises**: `ServiceNotFoundError` — when the name matches neither registry.

**Kwargs**: None.

#### `ToToolManager.build_agent(resources=None, middlewares=None)` — method

**Description**: Registers every service instance as a dependency, builds each module into a `SubAgent`, collects them into a `SubAgents` toolset and constructs the top-level `Agent`. Calling it more than once is safe — the agent is replaced.

**Return**: `Agent[DinamicDepend]` — the assembled agent, also available through `.agent`.

**Args**:

- `resources`: `Sequence[Service | Module] | None` = `None` — build from this set instead of the registered one. Items that are neither `Service` nor `Module` are **silently ignored**; they do not raise.
- `middlewares`: `Sequence[Middleware] | None` = `None` — replaces the middleware sequence. Setting it also makes the `.middlewares` property readable.

**Kwargs**: None.

#### `ToToolManager.add_middleware_to_service(service_name, middleware)` — method

**Description**: Appends a middleware to a registered service. Applied only if it is a `ToolMiddleware` and the capability is rebuilt afterwards.

**Return**: `None`.

**Args**:

- `service_name`: `str` — name of a registered **service**.
- `middleware`: `Middleware` — instance to append.

**Raises**: `ServiceNotFoundError` — unknown name; `MiddlewareTargetMismatchError` — the name refers to a module.

**Kwargs**: None.

#### `ToToolManager.add_middleware_to_module(module_name, middleware)` — method

**Description**: Appends a middleware to a registered module's list. Takes effect at the next `build_as_agent()`.

**Return**: `None`.

**Args**:

- `module_name`: `str` — name of a registered **module**.
- `middleware`: `Middleware` — instance to append.

**Raises**: `ServiceNotFoundError` — unknown name; `MiddlewareTargetMismatchError` — the name refers to a service.

**Kwargs**: None.

#### `ToToolManager.remove_middleware_to_service(service_name, middleware_type)` — method

**Description**: Removes every middleware of the given type from a service, keeping order.

**Return**: `None`.

**Args**:

- `service_name`: `str` — name of a registered service.
- `middleware_type`: `type` — class to filter out by `isinstance`.

**Raises**: `ServiceNotFoundError` — unknown name; `MiddlewareTargetMismatchError` — the name refers to a module.

**Kwargs**: None.

#### `ToToolManager.remove_middleware_to_module(module_name, middleware_type)` — method

**Description**: Removes every middleware of the given type from a module.

**Return**: `None`.

**Args**:

- `module_name`: `str` — name of a registered module.
- `middleware_type`: `type` — class to filter out by `isinstance`.

**Raises**: `ServiceNotFoundError` — unknown name; `MiddlewareTargetMismatchError` — the name refers to a service.

**Kwargs**: None.

---

### `TTMBuilder`

Fluent, declarative assembly. Same output as `ToToolManager`, different ergonomics — and it is the only entry point that **validates duplicate names** and the only one whose `add_middleware` actually reaches tool calls.

**Description**: Collects services, modules, skills and other managers, then builds the `Agent`. Precondition: `name` is a valid string. Postcondition: after `build()` (or on context-manager exit), `self.agent` is a valid `Agent`.

**Return**: `None` — call `build()`.

**Args** (constructor; `name` may be positional):

- `name`: `str` — *(required)* agent name; also used as the fallback `instructions`.
- `capabilities`: `List | None` = `None` — extra capabilities merged with generated ones.
- `toolsets`: `List | None` = `None` — extra toolsets; skills and modules are prepended.
- `model`: `Model | KnownModelName | str | None` = `None` — LLM model.
- `instructions`: `Any` = `None` — agent instructions; when falsy, `name` is used instead.
- `system_prompt`: `str | Sequence[str]` = `()` — system prompt.
- `model_settings`: `AgentModelSettings | None` = `None` — forwarded to `Agent`.
- `retries`: `int | AgentRetries | None` = `None` — retry budget.
- `validation_context`: `Any` = `None` — forwarded to `Agent`.
- `tools`: `Sequence[Any]` = `()` — extra hand-written tools.
- `defer_model_check`: `bool` = `False` — skip model validation at construction.
- `end_strategy`: `EndStrategy` = `'graceful'` — end strategy.
- `metadata`: `Any` = `None` — forwarded to `Agent`.
- `tool_timeout`: `float | None` = `None` — per-tool timeout in seconds.
- `max_concurrency`: `AnyConcurrencyLimit` = `None` — concurrency limit.
- `output_type`: `Any` = `str` — output type.
- `description`: `str | None` = `None` — agent description.

**Properties and methods**:

#### `TTMBuilder.agent` — property

**Description**: Returns the built agent.

**Return**: `Agent` — the agent created by `build()`.

**Raises**: `AgentNotBuiltError` — if `build()` has not been called.

**Args** / **Kwargs**: None. The setter raises `AgentAlreadyBuiltError` if an agent is already set.

#### `TTMBuilder.dependency` — property

**Description**: Returns the container holding one instance per registered service.

**Return**: `DinamicDepend` — populated as services are added.

**Args** / **Kwargs**: None.

#### `TTMBuilder.__enter__()` / `TTMBuilder.__exit__(...)` — context manager

**Description**: Using the builder as a context manager calls `build()` on exit, including when the block raised.

**Return**: `TTMBuilder` on `__enter__`; `None` on `__exit__`.

**Kwargs**: `__exit__` accepts the standard `exc_type`, `exc`, `tb` triple.

#### `TTMBuilder.add_service(...)` — method

**Description**: Builds a `Service` from loose arguments, registers it and returns `self` for chaining. The service instance is created immediately and stored on the dependency container.

**Return**: `TTMBuilder` — `self`.

**Args**:

- `name`: `str` — *(required)* unique service name.
- `service`: `type` — *(required)* class to wrap.
- `instructions`: `str` — *(required)* when the LLM should use this service.
- `middleware`: `List | None` = `None` — defaults to `[]`.
- `disable_middlewares`: `Tuple[str, ...]` = `()` — inherited middlewares to skip.
- `include`: `MethodsType | Include | None` = `None` — **not currently applied** (same as `Service.include`).
- `exclude`: `MethodsType | Exclude | None` = `None` — **not currently applied**.
- `args`: `tuple` = `()` — positional constructor arguments.
- `kwargs`: `dict | None` = `None` — keyword constructor arguments; defaults to `{}`.

**Raises**: `ServiceAlreadyRegisteredError` — a service with that name is already registered.

**Kwargs**: None.

#### `TTMBuilder.add_module(...)` — method

**Description**: Registers a `Module` (building its sub-agent immediately) and returns `self`.

**Return**: `TTMBuilder` — `self`.

**Args**:

- `name`: `str` — *(required)* unique module name.
- `services`: `Sequence[Service]` — *(required)* services of the sub-agent.
- `description`: `str` — *(required)* delegation description for the parent model.
- `middleware`: `List | None` = `None` — middlewares for the module.
- `disable_middlewares`: `Tuple[str, ...]` = `()` — names the module must not apply.
- `capabilities`: `List | None` = `None` — extra capabilities.
- `model`, `instructions`, `system_prompt`, `model_settings`, `retries`, `validation_context`, `tools`, `toolsets`, `defer_model_check`, `end_strategy`, `metadata`, `tool_timeout`, `max_concurrency`, `output_type` — same meaning and defaults as the corresponding [`Module`](#module) fields.

**Raises**: `ModuleAlreadyRegisteredError` — duplicate name; `SelfDisableMiddlewareError` — propagated from the `Module` constructor; `AgentAlreadyBuiltError` — if that module was already built.

**Kwargs**: None.

#### `TTMBuilder.add_middleware(middleware)` — method

**Description**: Registers a builder-level middleware. On `build()` it is appended to every registered service, so it becomes the **outermost** middleware of each chain. Only `ToolMiddleware` instances are actually invoked.

**Return**: `TTMBuilder` — `self`.

**Args**:

- `middleware`: `Middleware` — instance to register.

**Kwargs**: None.

#### `TTMBuilder.remove_middleware_to_service(service_name, middleware_type)` — method

**Description**: Removes every middleware of the given type from a registered service.

**Return**: `TTMBuilder` — `self`.

**Args**:

- `service_name`: `str` — name of a registered service.
- `middleware_type`: `type` — class to filter out.

**Raises**: `ServiceNotFoundError` — unknown service name.

**Kwargs**: None.

#### `TTMBuilder.add_skill(skill)` — method

**Description**: Registers a `pydantic-ai-skills` `Skill`. Skills are collected into the toolset list, ahead of any toolsets passed to the constructor.

**Return**: `TTMBuilder` — `self`.

**Args**:

- `skill`: `Skill` — the skill instance.

**Kwargs**: None.

#### `TTMBuilder.add_ttm(manager)` — method

**Description**: Registers an existing `ToToolManager` so its resources can be composed into this agent.

**Return**: `TTMBuilder` — `self`.

**Args**:

- `manager`: `ToToolManager` — the orchestrator to compose.

**Raises**: `ToToolManagerAlreadyRegisteredError` — a manager with that name is already registered.

**Kwargs**: None.

#### `TTMBuilder.build(...)` — method

**Description**: Assembles the final `Agent` from everything registered. Every parameter overrides the constructor value; anything left as `None` falls back to the constructor.

**Return**: `None` — read the result from the `agent` property.

**Args** (all optional, all default `None`):

- `model`: `Model | KnownModelName | str | None` — overrides the constructor model.
- `instructions`: `Any` — overrides instructions.
- `system_prompt`: `str | Sequence[str] | None` — overrides the system prompt.
- `model_settings`: `AgentModelSettings | None` — overrides model settings.
- `retries`: `int | AgentRetries | None` — overrides retries.
- `validation_context`: `Any` — overrides validation context.
- `tools`: `Sequence[Any] | None` — overrides extra tools.
- `defer_model_check`: `bool | None` — overrides model-check deferral.
- `end_strategy`: `EndStrategy | None` — overrides end strategy.
- `metadata`: `Any` — overrides metadata.
- `tool_timeout`: `float | None` — overrides the tool timeout.
- `max_concurrency`: `AnyConcurrencyLimit | None` — overrides the concurrency limit.
- `output_type`: `Any` — overrides the output type.
- `description`: `str | None` — overrides the description.

**Kwargs**: None.

#### `TTMBuilder.to_mcp_tool(name, instructions)` — method

**Description**: Exports the builder's tools as a `FastMCP` server, exposing each service method as a flat tool with the original signature (the injected `ctx` parameter is stripped and the types are preserved). Tools belonging to `Module` sub-agents are skipped — the sub-agent manages them internally. Builds the agent first if needed.

**Return**: `FastMCP` — a server instance you can run or mount.

**Args**:

- `name`: `str` — *(required)* MCP server name.
- `instructions`: `str` — *(required)* server-level instructions.

**Kwargs**: None.

---

### `DinamicDepend`

The dependency container attached to every agent. Not re-exported from the package root; reach it through `TTMBuilder.dependency` or `Module.dependency`, and inside tools through `ctx.deps`.

**Description**: Attribute bag whose keys are service names. Precondition: none. Postcondition: any attribute set on it is readable; reading a missing attribute raises `DependencyNotSetError`.

**Return**: n/a (instantiated by the framework).

**Args**: None.

**Methods**:

- `__setattr__(name, value)` — stores a service instance. Names starting with `_` bypass the bag and set a real instance attribute.
- `__getattribute__(name)` — returns the stored instance.

**Gotcha**: `DependencyNotSetError` also subclasses `AttributeError`, so `hasattr(deps, "x")` returns `False` and `getattr(deps, "x", default)` returns the default instead of raising.

---

### `Include` / `Exclude` / `MethodsType`

Helpers for the `include`/`exclude` parameters of `ToolMiddleware`.

**`Include`** — frozen dataclass wrapping a sequence of method names; iterable, sized, field `include: Sequence[str]`.
**`Exclude`** — frozen dataclass wrapping a sequence of method names; iterable, sized, field `exclude: Sequence[str]`.
**`MethodsType`** — type alias for `frozenset[str]`.

All three are accepted interchangeably wherever a filter is expected: a bare `frozenset`, a list/tuple of names, or the wrapper object.

---

## Middleware

Middlewares intercept tool calls or graph transitions without touching business logic. They are invoked in the order described in [Middleware resolution and ordering](#middleware-resolution-and-ordering).

### `Middleware`

**Description**: Abstract base class. Subclass it and implement `dispatch` to intercept tool calls. The concrete class name becomes `name`, which is what `disable_middlewares` matches. Precondition: `dispatch` is overridden. Postcondition: calling an instance with a function returns an `async` wrapper that routes through `dispatch`.

**Return**: n/a (instantiate directly).

**Args**: None.

**Members**:

- `dispatch(func, /, *args, **kw)` — **abstract, `async`**. Must be implemented. `func` is positional-only and always awaitable, so `await func(*args, **kw)` works for both sync and async targets.
- `__call__(func)` — returns the `async` wrapper. If `func` is a coroutine function the wrapper awaits it; otherwise it is adapted so `dispatch` still receives an awaitable callable.
- `call_func(func, *args, **kwargs)` — `staticmethod`, `async`. Helper to invoke a sync-or-async callable from inside `dispatch`. Pass it `ctx` explicitly if the wrapped tool takes a `RunContext`.
- `name` — property returning the class name.

```python
from to_tool_manager import Middleware


class TimingMiddleware(ToolMiddleware):  # subclass ToolMiddleware to be applied
    async def dispatch(self, func, /, *args, **kw):
        start = time.perf_counter()
        try:
            return await func(*args, **kw)
        finally:
            print(f"{func.__name__}: {time.perf_counter() - start:.3f}s")
```

### `ToolMiddleware`

**Description**: `Middleware` plus per-method filtering. The `include`/`exclude` filters are evaluated when the tool table is built, so filtered methods are simply not exposed to the LLM. Subclass it — do not instantiate it directly.

**Return**: n/a.

**Args** (constructor):

- `include`: `MethodsType | Include | None` = `None` — only these methods are wrapped. Takes priority over `exclude`.
- `exclude`: `MethodsType | Exclude | None` = `None` — these methods are left unwrapped.

**Properties and methods**:

- `include` — property → `frozenset[str] | None`. `None` when unset.
- `exclude` — property → `frozenset[str] | None`. `None` when unset.
- `is_allowed(method_name)` → `bool`. `True` when `include` is set iff the name is in it; otherwise `True` when `exclude` is set iff the name is not in it; `True` when neither is set.

```python
class AuthMiddleware(ToolMiddleware):
    async def dispatch(self, func, /, *args, **kw):
        if not current_user().is_admin:
            return "Forbidden: admin role required."
        return await func(*args, **kw)


# Only guard the destructive methods
middleware=[AuthMiddleware(include=frozenset({"delete", "update_status"}))]
```

### `NodeMiddleware`

**Description**: Abstract base for `pydantic_graph` transition guards. Intercepts a node→node transition and can approve or block it. Unlike tool middleware, only the hooks you override are meaningful — all three have safe defaults.

**Return**: n/a.

**Args**: None.

**Members** (all `async`):

- `before_transition(source_node_id, target_node_id, state)` → `bool`. `source_node_id` is `None` for the first transition. Return `True` to approve (default), `False` to block.
- `before_run(node, ctx)` → `None`. Runs before the wrapped node; mutate `ctx.state` here. Default: no-op.
- `after_run(node, ctx, next_node)` → `BaseNode | End`. Runs after the node, with the node's proposed successor. Return `next_node` to proceed (default) or a different node/`End` to redirect.
- `name` — property returning the class name.

### `NodeWrapper`

**Description**: `BaseNode` subclass that runs a wrapped node through a `NodeMiddleware` chain. Because `pydantic_graph` instantiates nodes with no arguments, the wrapped type and the middleware list are supplied as **class attributes** of a dynamically created subclass.

> **Import path:** `NodeWrapper` is **not** re-exported from the package root — import it from `to_tool_manager.core.middleware.middleware`. For guarding transitions in a real graph, prefer `GraphMiddlewareRunner` and `before_transition`; see the caveat below.

**Return**: n/a.

**Args**: None.

**Members**:

- `_wrapped_node_type: type[BaseNode]` — class attribute: the node to wrap.
- `_middlewares_attr: Sequence[NodeMiddleware]` — class attribute: the chain. `before_run` runs in order, `after_run` in reverse.
- `run(ctx)` → `BaseNode | End`. Instantiates the wrapped node, runs `before_run` on each middleware, executes the node, then runs `after_run` in reverse and returns the (possibly rewritten) successor.

```python
import asyncio

from pydantic_graph import BaseNode, End, GraphRunContext

from to_tool_manager.core.middleware.middleware import NodeMiddleware, NodeWrapper


@dataclass
class Real(BaseNode[State]):
    async def run(self, ctx) -> End[str]:
        return End("final")


class AuditMiddleware(NodeMiddleware):
    async def before_run(self, node, ctx):
        print("before node")

    async def after_run(self, node, ctx, next_node):
        print("after node")
        return next_node


WrappedReal = type(
    "WrappedReal",
    (NodeWrapper,),
    {"_wrapped_node_type": Real, "_middlewares_attr": [AuditMiddleware()]},
)

result = await WrappedReal().run(ctx)     # -> End('final'), hooks fired around the node
```

**Caveat**: `NodeWrapper.run` is annotated as returning `BaseNode | End`, and `GraphBuilder` cannot infer edges from a plain `BaseNode` union — it raises `GraphSetupError` when a `NodeWrapper` is registered with `builder.node(...)`. Use `GraphMiddlewareRunner` for graph-level guards.

### `GraphMiddlewareRunner`

**Description**: Runs a `pydantic_graph` while consulting a `NodeMiddleware` chain before every transition. Approval is evaluated through `GraphRun.override_next`.

**Return**: n/a.

**Args** (constructor):

- `graph`: `Graph[Any, Any, Any, Any]` — *(required)* the graph to run.
- `middlewares`: `Sequence[NodeMiddleware]` — *(required)* consulted in order for each transition; the first `False` blocks.

**Methods**:

#### `GraphMiddlewareRunner.run(state=None, deps=None, inputs=None)` — method

**Description**: Iterates the graph, checking `before_transition` before each node executes. If a middleware blocks, the run is overridden to `End(None)` and `None` is returned immediately.

**Return**: `Any` — the `End.value` of the graph, or `None` when a middleware blocked the transition (which is indistinguishable from a graph that legitimately ends with `None`).

**Args**:

- `state`: `Any` = `None` — initial state.
- `deps`: `Any` = `None` — initial dependencies.
- `inputs`: `Any` = `None` — input data.

**Kwargs**: None.

---

## Human-in-the-Loop

HITL suspends a tool call, emits an event to your transport, waits for a human decision and retries when validation fails.

```mermaid
sequenceDiagram
    participant LLM
    participant Agent
    participant MW as HITL Middleware
    participant H as HumanInTheLoop
    participant Client as Client (SSE/WS)
    participant Tool as Tool Function

    LLM->>Agent: calls tool(args)
    Agent->>MW: dispatch(func, args)
    MW->>H: execute(event_fn)
    H->>Client: emit(event_id, payload)
    Client-->>H: human response
    H->>H: validate response
    alt Validation passed
        H-->>MW: ok
        MW->>Tool: func(args)
        Tool-->>MW: result
        MW-->>Agent: result
    else Validation failed
        H-->>MW: HumanInputRetry
        MW->>H: retry (up to max_retries)
    end
```

When retries are exhausted the middleware returns the string `"Maximum retries reached."` — it does not raise.

### `EventEmitter`

**Description**: Abstract base you implement to bridge HITL events to your transport (SSE, WebSocket, in-process callback).

**Return**: n/a.

**Args**: None.

**Methods**:

- `emit(event_id, payload)` — **abstract, `async`**, returns `None`. `event_id` identifies the event; `payload` is a JSON-serialisable `dict`.

### `HumanInTheLoop`

**Description**: Coordinates the emit → wait → validate cycle. Precondition: `emitter` implements `EventEmitter` and `logic` is callable. Postcondition: an instance is ready for `execute()`.

**Return**: n/a.

**Args** (constructor):

- `emitter`: `EventEmitter` — your transport implementation.
- `logic`: `Callable[..., Any]` — `async def logic(emit, event_fn, *args, **kwargs) -> None`. Receives an `emit` coroutine, a zero-argument `event_fn` that performs the tool call, and your injected arguments. Raise `HumanInputRetry` to trigger a retry.
- `*args`: `Any` — positional arguments injected into `logic`.
- `**kwargs`: `Any` — keyword arguments injected into `logic`. This is how you parameterise one coordinator per action, e.g. `HumanInTheLoop(emitter, logic, action="delete_user")`.

**Methods**:

- `execute(event_fn)` — `async`, returns `None`. Builds an `emit` coroutine bound to the emitter and invokes `logic(emit, event_fn, *args, **kwargs)`. Sync and async `logic` are both supported.

### `HumanInputRetry`

**Description**: Raised by your `logic` when validation fails. The HITL middleware catches it and restarts the cycle, up to `max_retries`. Plain `Exception` subclass — it does not inherit from `TTMError`.

**Return**: n/a.

**Args**: None.

### `HumanInTheLoopMiddleware`

**Description**: Applies the HITL cycle to **every** tool call of the services it is attached to.

**Return**: n/a.

**Args** (constructor):

- `hitl`: `HumanInTheLoop` — *(required, keyword or positional)* the coordinator.
- `max_retries`: `int` = `3` — number of emit/wait/validate cycles before giving up.

**Methods**:

- `dispatch(func, /, *args, **kw)` — `async`. Runs the cycle, then invokes the tool.

### `HumanInTheLoopToolMiddleware`

**Description**: `ToolMiddleware` variant of the above, restricted to selected methods. `include`/`exclude` keep the exact position of `ToolMiddleware.__init__`; the HITL-specific parameters are keyword-only so any positional call valid for `ToolMiddleware` stays valid here.

**Return**: n/a.

**Args** (constructor):

- `include`: `MethodsType | Include | None` = `None` — only these methods require approval.
- `exclude`: `MethodsType | Exclude | None` = `None` — these methods skip approval.

**Kwargs** (keyword-only):

- `hitl`: `HumanInTheLoop` — *(required)* the coordinator.
- `max_retries`: `int` = `3` — cycles before giving up.

**Methods**:

- `dispatch(func, /, *args, **kw)` — `async`. Runs the cycle for allowed methods only.

---

## Exceptions

Every exception in the package inherits from `TTMError`, so a single `except TTMError` catches them all.

```text
TTMError
├── ConfigurationError
│   ├── InvalidResourceTypeError(got_type: str)
│   └── SelfDisableMiddlewareError(middleware_name: str)
├── ServiceError
│   ├── ServiceNotFoundError(name: str)
│   ├── ServiceAlreadyRegisteredError(name: str)
│   └── DependencyNotSetError(name: str)   ← also AttributeError
├── ModuleError
│   └── ModuleAlreadyRegisteredError(name: str)
├── AgentError
│   ├── AgentNotBuiltError(component: str)
│   └── AgentAlreadyBuiltError(component: str)
├── MiddlewareError
│   ├── MiddlewareNotInitializedError()
│   └── MiddlewareTargetMismatchError(name: str, expected: str)
└── BuilderError
    ├── ToToolManagerAlreadyRegisteredError(name: str)
    └── ToToolManagerNotFoundError(name: str)
```

| Exception | Message | Raised when |
|---|---|---|
| `InvalidResourceTypeError` | `Expected Service or Module, got {got_type}` | `ToToolManager(resources=[…])` receives an item of another type. **Not** raised by `build_agent(resources=…)`, which ignores unknown items. |
| `SelfDisableMiddlewareError` | `Cannot disable middleware '{middleware_name}' in the same class that declares it. Disable it in the parent layer (ToToolManager or Module) instead.` | `Module(...)` construction, when `disable_middlewares` names one of its own middlewares. |
| `ServiceNotFoundError` | `Unknown service '{name}'` | `ToToolManager.get_service`, `add_middleware_to_*`, `remove_middleware_to_*`, or `TTMBuilder.remove_middleware_to_service` for an unknown name. |
| `ServiceAlreadyRegisteredError` | `Service '{name}' already registered` | `TTMBuilder.add_service` with a duplicate name. |
| `DependencyNotSetError` | `DinamicDepend has no attribute '{name}'` | Reading a service name that was never registered. Also an `AttributeError`, so `hasattr` returns `False`. |
| `ModuleAlreadyRegisteredError` | `Module '{name}' already registered` | `TTMBuilder.add_module` with a duplicate name. |
| `AgentNotBuiltError` | `Agent not built. Call build() first on {component}.` | Reading `.agent` on `Module`, `ToToolManager` or `TTMBuilder` before building. |
| `AgentAlreadyBuiltError` | `Agent already built on {component}. Cannot rebuild.` | Assigning `.agent` twice, or calling `Module.build_as_agent()` a second time. |
| `MiddlewareNotInitializedError` | `Middleware sequence is not initialized (None)` | Reading `ToToolManager.middlewares` when none were configured. |
| `MiddlewareTargetMismatchError` | `'{name}' is not a {expected}. Use the correct method for the target type.` | Calling `add/remove_middleware_to_service` on a module name, or `…_to_module` on a service name. |
| `ToToolManagerAlreadyRegisteredError` | `ToToolManager '{name}' already registered` | `TTMBuilder.add_ttm` with a duplicate name. |
| `ToToolManagerNotFoundError` | `ToToolManager '{name}' not found` | Internal `Manager` lookup by TTM name. Not reachable through the documented public flow. |

`HumanInputRetry` is raised by *your* HITL logic and caught by the middleware; it is not part of this hierarchy.

---

## Configuration

The library has **no configuration file, no environment variables and no global settings** — it reads neither. Every setting is a constructor argument, and the pydantic-ai parameters are forwarded verbatim to `Agent`.

Model selection and provider credentials are pydantic-ai's concern: pass `model="openai:gpt-4o"` explicitly, or let pydantic-ai resolve it from its own environment (`OPENAI_API_KEY`, …). Building an agent validates the model, so credentials must be present at build time — use `model="test"` to develop offline.

| Value | Behaviour |
|---|---|
| `"openai:gpt-4o"`, `"anthropic:…"`, … | Real provider. Requires that provider's credentials at build time. |
| `"test"` | pydantic-ai's built-in test model. No credentials needed; ideal for local development and CI. |
| `None` | Inherits the parent model (`Module` inside an agent) or pydantic-ai's default resolution. |

### Shared `Agent` parameters

These appear on `Module`, `ToToolManager` and `TTMBuilder` with identical meaning and defaults, and are forwarded to the pydantic-ai `Agent`.

| Parameter | Type | Default | Effect |
|---|---|---|---|
| `model` | `Model \| KnownModelName \| str \| None` | `None` | Model for this agent. `None` inherits the parent's model. |
| `instructions` | `Any` | `None` | Behavioural instructions. On `TTMBuilder` a falsy value falls back to `name`. |
| `system_prompt` | `str \| Sequence[str]` | `()` | System prompt content. |
| `model_settings` | `AgentModelSettings \| None` | `None` | Temperature, tokens, provider flags. |
| `retries` | `int \| AgentRetries \| None` | `None` | Output validation retries. |
| `validation_context` | `Any \| Callable \| None` | `None` | Context for output validators. |
| `tools` | `Sequence[Any]` | `()` | Extra hand-written tools alongside generated ones. |
| `toolsets` | `Sequence[AgentToolset] \| None` | `None` | Extra toolsets. The `SubAgents` toolset is appended automatically by `ToToolManager`. |
| `defer_model_check` | `bool` | `False` | Defer model validation to first use. |
| `end_strategy` | `EndStrategy` | `'graceful'` | How the run terminates. |
| `metadata` | `Any` | `None` | Free-form metadata. |
| `tool_timeout` | `float \| None` | `None` | Per-tool timeout in seconds. |
| `max_concurrency` | `AnyConcurrencyLimit` | `None` | Concurrency limit for tool calls. |
| `output_type` | `Any` | `str` | Structured output type. |

### Middleware parameters

| Parameter | Applies to | Type | Default | Effect |
|---|---|---|---|---|
| `include` | `ToolMiddleware`, `Service`, `TTMBuilder.add_service` | `MethodsType \| Include \| None` | `None` | Allow-list. **Effective only on `ToolMiddleware` and its subclasses.** |
| `exclude` | `ToolMiddleware`, `Service`, `TTMBuilder.add_service` | `MethodsType \| Exclude \| None` | `None` | Deny-list. **Effective only on `ToolMiddleware` and its subclasses.** |
| `max_retries` | HITL middlewares | `int` | `3` | HITL cycles before returning `"Maximum retries reached."`. |
| `disable_middlewares` | `Service`, `Module`, `TTMBuilder.add_service/add_module` | `Tuple[str, ...]` | `()` | Names to skip when inherited from an outer layer. Matched against `Middleware.name` (the class name by default). |
| `defer_loading` | `Capability` (set internally) | `bool` | `True` | Tool schemas materialise only when the capability is used. |

### Name uniqueness

Names are global within a manager or builder and are **not** validated by `ToToolManager`:

| Component | Service names | Module names |
|---|---|---|
| `ToToolManager` | last registration wins, silently | last registration wins, silently |
| `TTMBuilder` | `ServiceAlreadyRegisteredError` | `ModuleAlreadyRegisteredError` |

---

## Examples and use cases

All examples assume these two in-memory services:

```python
from dataclasses import dataclass


@dataclass
class User:
    id: str
    name: str
    email: str


class UserManager:
    """In-memory CRUD for users."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    def create(self, id: str, name: str, email: str) -> str:
        """Create a user and return a confirmation."""
        self._users[id] = User(id=id, name=name, email=email)
        return f"User {id} created: {name}"

    def get(self, id: str) -> str:
        """Return a user by id."""
        user = self._users.get(id)
        return f"User {user.id}: {user.name} <{user.email}>" if user else f"User {id} not found."

    def delete(self, id: str) -> str:
        """Delete a user by id."""
        del self._users[id]
        return f"User {id} deleted."


class OrderManager:
    """In-memory CRUD for orders."""

    def __init__(self) -> None:
        self._orders: dict[str, str] = {}

    def create(self, id: str, user_id: str, product: str, quantity: int) -> str:
        """Place an order for a user."""
        self._orders[id] = f"{user_id}: {quantity}x {product}"
        return f"Order {id} created: {quantity}x {product}"

    def update_status(self, id: str, status: str) -> str:
        """Change the status of an order."""
        self._orders[id] = status
        return f"Order {id} status updated to {status}"
```

### Dependency injection into services

Pass constructor arguments through `args`/`kwargs`; the library instantiates the class for you.

```python
from to_tool_manager import Service, TTMBuilder


class UserRepository:
    def __init__(self, session) -> None:
        self._session = session


class UserService:
    """Business logic; knows nothing about the LLM."""

    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def get_user(self, id: str) -> str:
        """Look up a user in the database."""
        user = self._repo.find(id)
        return f"{user.name} <{user.email}>"


builder = TTMBuilder(name="App", model="openai:gpt-4o")
builder.add_service(
    name="user_service",
    service=UserService,
    instructions="Look up and manage user accounts.",
    args=(UserRepository(session),),   # injected into UserService.__init__
)
builder.build()

# The instance is available for direct use too
service_instance = builder.dependency.user_service
```

Because the instance is registered on `DinamicDepend`, you can also reach it from inside a tool or a middleware via `ctx.deps.user_service`.

### Async services and DI

Sync and async methods are both exposed, and the generated tool keeps the same flavour — await the service's own I/O inside the method.

```python
class NotificationService:
    def __init__(self, transport) -> None:
        self._transport = transport

    async def send(self, to: str, body: str) -> str:
        """Send an email notification."""
        await self._transport.send(to=to, body=body)
        return f"Notification sent to {to}"
```

### Error mapping and PII scrubbing

Because exceptions are converted to strings, map your domain errors into actionable text and redact sensitive payloads — as two independent middlewares. Continuing the previous example, with `NotFoundException` and `ValidationException` from your own error module:

```python
from to_tool_manager import TTMBuilder, ToolMiddleware


class DomainErrorMappingMiddleware(ToolMiddleware):
    """Translate domain exceptions into LLM-readable, retry-aware messages."""

    def __init__(self, mapping: dict, retryable: set | None = None) -> None:
        super().__init__()
        self._mapping = mapping
        self._retryable = retryable or set()

    async def dispatch(self, func, /, *args, **kw):
        try:
            return await func(*args, **kw)
        except Exception as exc:
            for error_type, code in self._mapping.items():
                if isinstance(exc, error_type):
                    hint = " Fix the input and retry." if error_type in self._retryable else ""
                    return f"[{code}] {exc}.{hint}"
            raise


class RedactPasswordsMiddleware(ToolMiddleware):
    """Strip password fields before the payload reaches the model."""

    async def dispatch(self, func, /, *args, **kw):
        result = await func(*args, **kw)
        if isinstance(result, dict):
            result.pop("password", None)
            result.pop("hashed_password", None)
        return result


builder = TTMBuilder(name="App")
builder.add_service(
    name="users",
    service=UserService,
    instructions="Manage user accounts.",
    middleware=[
        DomainErrorMappingMiddleware(
            {NotFoundException: "not_found", ValidationException: "validation_error"},
            retryable={ValidationException},
        ),
        RedactPasswordsMiddleware(include=frozenset({"get_user"})),
    ],
    args=(repo,),
)
builder.build()
```

The outer middleware sees the inner one's return value last, so ordering determines who gets to post-process the result.

### Sub-agents with Module

`Module` builds a separate `Agent` that the parent delegates to. Use it when a domain needs its own model, prompt and retry budget.

```python
from to_tool_manager import Module, Service, ToToolManager


class InventoryService:
    """Stock levels for the catalogue."""

    def check(self, sku: str) -> str:
        """Return the available quantity for a SKU."""
        return f"{sku}: 12 in stock"


commerce = Module(
    name="commerce",
    services=[
        Service(name="orders", service=OrderManager,
                instructions="Create and update orders."),
        Service(name="inventory", service=InventoryService,
                instructions="Check and adjust stock levels."),
    ],
    description=(
        "Commerce sub-agent. Use it for anything involving products, "
        "orders or payments."
    ),
    system_prompt="Always confirm stock availability before confirming an order.",
    model="openai:gpt-4o-mini",     # cheaper model for a narrow domain
    retries=3,
)

manager = ToToolManager(name="App", resources=[commerce], model="openai:gpt-4o")
agent = manager.build_agent()
```

The parent model only sees `commerce` as a delegation target, which keeps the top-level tool list small and the prompts focused.

### Disabling inherited middleware

An outer layer's middleware can be switched off for a specific service or module by name.

```python
from to_tool_manager import Middleware, Module, Service, ToolMiddleware


class RateLimitMiddleware(ToolMiddleware):
    """Allow at most `max_calls` tool calls per process."""

    def __init__(self, max_calls: int = 10) -> None:
        super().__init__()
        self._calls = 0
        self._max = max_calls

    async def dispatch(self, func, /, *args, **kw):
        self._calls += 1
        if self._calls > self._max:
            return "Rate limit exceeded. Try again later."
        return await func(*args, **kw)


module = Module(
    name="reports",
    services=[
        Service(
            name="orders",
            service=OrderManager,
            instructions="Read-only order queries.",
            disable_middlewares=("RateLimitMiddleware",),   # skip the outer limiter
        ),
    ],
    description="Reporting sub-agent.",
    middleware=[RateLimitMiddleware(max_calls=50)],
)
```

A module may not disable a middleware it declares itself — doing so raises `SelfDisableMiddlewareError` at construction. Disable it in the parent layer instead.

### Exporting tools to an MCP server

`to_mcp_tool` republishes the builder's tools over MCP with flat signatures, ready for Claude Desktop or any MCP client.

```python
mcp = builder.to_mcp_tool(
    name="ToToolManagerServer",
    instructions="User and order management tools.",
)

if __name__ == "__main__":
    mcp.run()   # stdio by default
```

Exported tool names use the `{service}__{method}` convention. Tools owned by `Module` sub-agents are not exported — the sub-agent handles them internally.

### Gateways and approvals with HITL

Gate destructive operations behind a human decision, emitting the request over your own transport.

```python
from typing import Any

from to_tool_manager import HumanInTheLoop, HumanInTheLoopToolMiddleware, HumanInputRetry
from to_tool_manager import EventEmitter


class SSEEventEmitter(EventEmitter):
    """Bridges HITL events onto a Server-Sent Events stream."""

    def __init__(self, send_fn) -> None:
        self._send = send_fn

    async def emit(self, event_id: str, payload: dict[str, Any]) -> None:
        await self._send({"event": event_id, "data": payload})


async def approval_logic(emit, event_fn, action: str) -> None:
    """Emit the request, wait for the answer, validate it."""
    await emit("approval_request", {"action": action, "message": "Approve?"})

    answer = await wait_for_human_answer()          # your transport-specific wait
    if answer != "approve":
        raise HumanInputRetry()                     # restart the cycle


hitl = HumanInTheLoop(
    emitter=SSEEventEmitter(send_fn=push_to_client),
    logic=approval_logic,
    action="delete_user",                           # injected into approval_logic
)

service = Service(
    name="users",
    service=UserManager,
    instructions="User administration.",
    middleware=[
        HumanInTheLoopToolMiddleware(
            include=frozenset({"delete"}),         # only delete needs approval
            hitl=hitl,
            max_retries=3,
        )
    ],
)
```

`event_fn` is the tool call itself — invoke it inside your logic if you need to run the operation as part of the approved transaction.

### Guarding graph transitions

`GraphMiddlewareRunner` applies a middleware chain to every transition of a `pydantic_graph`, so you can block a pipeline step without touching the nodes.

```python
from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, End, GraphBuilder, GraphRunContext

from to_tool_manager import GraphMiddlewareRunner, NodeMiddleware


@dataclass
class PipelineState:
    user_id: str
    validated: bool = False
    result: str | None = None


@dataclass
class ValidateUser(BaseNode[PipelineState]):
    async def run(self, ctx: GraphRunContext[PipelineState]) -> ProcessOrder:
        ctx.state.validated = True
        return ProcessOrder()


@dataclass
class ProcessOrder(BaseNode[PipelineState, None, str]):
    async def run(self, ctx: GraphRunContext[PipelineState]) -> End[str]:
        ctx.state.result = f"Order processed for user {ctx.state.user_id}"
        return End(ctx.state.result)


class AuditMiddleware(NodeMiddleware):
    """Log every transition and block an empty user id."""

    async def before_transition(self, source_node_id, target_node_id, state):
        print(f"[Audit] {source_node_id} -> {target_node_id}")
        return bool(getattr(state, "user_id", None))


# pydantic_graph does not infer an entry edge, so wire the start node explicitly.
builder = GraphBuilder(name="order_pipeline", state_type=PipelineState, output_type=str)
builder.add(
    builder.edge_from(builder.start_node).to(ValidateUser),
    builder.node(ValidateUser),
    builder.node(ProcessOrder),
)
pipeline = builder.build()


async def run_pipeline(user_id: str) -> str | None:
    runner = GraphMiddlewareRunner(graph=pipeline, middlewares=[AuditMiddleware()])
    return await runner.run(
        state=PipelineState(user_id=user_id),
        inputs=ValidateUser(),      # the start node runs this first
    )


# run_pipeline("user-42") -> 'Order processed for user user-42'
# run_pipeline("")         -> None   (blocked before the first transition)
```

---

## Gotchas and troubleshooting

### My service exposes no tools

Inherited methods are not discovered — only methods declared in the class body itself (`core/main/shared/discover.py:39`). Verify with:

```python
from to_tool_manager.core.main.shared.discover import discover_methods
print([m.name for m in discover_methods(MyService)])
```

Also confirm the method is a plain function (not a `property` or class attribute) and does not start with `_`.

### My middleware never runs

Subclass `ToolMiddleware`, not `Middleware`. `Service.build_as_capability` only wraps `ToolMiddleware` instances (`core/main/service.py:71`), so a plain `Middleware` in a service, module or builder list is stored but never invoked.

`ToToolManager(middlewares=[...])` is stored and readable but is not wired into dispatch either. Use `TTMBuilder.add_middleware(...)`, which appends to every service on `build()`.

### `include` / `exclude` on `Service` do nothing

`Service(include=…, exclude=…)` and `TTMBuilder.add_service(include=…, exclude=…)` are accepted and stored, but no code in the package reads them, so no method is filtered. Attach the filter to a `ToolMiddleware` instead:

```python
# Does not filter:
Service(name="users", service=UserManager, instructions="…", exclude=frozenset({"delete"}))

# Filters (the middleware only wraps the methods it allows):
Service(name="users", service=UserManager, instructions="…",
        middleware=[GuardMiddleware(exclude=frozenset({"delete"}))])
```

### Two tools with the same name

Tool names are bare method names, so `users.create` and `orders.create` are both exposed as `create`. Rename the methods, or move one into a `Module` so only one capability is loaded at a time.

### Middleware order is the reverse of the list

The last middleware in the list wraps the others, so it runs first. Outer layers (module, builder) run before inner ones (service). See [Middleware resolution and ordering](#middleware-resolution-and-ordering).

### `Module.build_as_agent()` raises on the second call

The `agent` setter refuses to overwrite, so a module builds exactly once. Create a fresh `Module` per build, or let a single `TTMBuilder`/`ToToolManager` own it.

### My exception never reaches my code

Service exceptions are caught by the generated wrapper and returned as the string `Error in <service>.<method>: <Type>: <message>`. Handle errors inside the method, or map them with a `ToolMiddleware`.

### `hasattr(deps, "name")` is always `False` for missing services

`DependencyNotSetError` subclasses `AttributeError`, so `hasattr` swallows it and `getattr(deps, "name", None)` returns the default. Catch `DependencyNotSetError` explicitly if you need to distinguish "no such service" from a service whose value is `None`.

### A blocked graph run returns `None`

`GraphMiddlewareRunner.run` returns `None` both when a middleware blocks and when the graph legitimately ends with `None`. Log inside `before_transition` if you need to tell them apart.

---

## Development

```bash
git clone https://github.com/Davidmg5k/ToToolManager.git
cd ToToolManager
uv sync --extra pydantic-ai
```

| Task | Command |
|---|---|
| Run the test suite | `uv run pytest -q` |
| Type-check | `uv run --with pyright pyright src/` |
| Dependency audit | `uv run --with pip-audit pip-audit` |
| Coverage | `uv run pytest --cov` (gate: `fail_under = 79`) |

The suite is organised as `tests/unit`, `tests/integration`, `tests/system`, `tests/use_cases` and `tests/perf`. CI runs tests on Python 3.12 and 3.13, plus pyright and pip-audit (`.github/workflows/ci.yml`).

A complete multi-domain FastAPI demo — users, orders, inventory, payments, notifications, auth and a chat UI — lives in [`example/`](example/README.md).

---

## License

MIT — Copyright (c) 2026 Conectar Wali SAS. See [LICENSE](LICENSE).

---

## Links

- **Repository:** https://github.com/Davidmg5k/ToToolManager
- **Issues:** https://github.com/Davidmg5k/ToToolManager/issues
- **Changelog:** https://github.com/Davidmg5k/ToToolManager/blob/main/CHANGELOG.md
- **Example app:** [`example/README.md`](example/README.md)
