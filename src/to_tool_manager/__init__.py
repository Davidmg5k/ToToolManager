"""
to_tool_manager
================

Turns plain Python classes ("services") into agent tools, without tying
you to any specific agent framework.

Core usage (framework-agnostic)::

    from to_tool_manager import ToToolManager, Service

    manager = ToToolManager([
        Service(name="Order", service=Order, description="..."),
    ])
    specs = manager.tool_specs  # list[ToolSpec] — pure data, no framework

Adapters translate `tool_specs` into whatever a specific framework
expects, and are imported separately so this package has ZERO hard
dependency on any agent framework::

    from to_tool_manager.adapters.pydantic_ai import to_pydantic_ai_tools
    from to_tool_manager.adapters.fastmcp import register_on_mcp
    from to_tool_manager.adapters.raw import to_openai_tool_schemas, dispatch
"""
from to_tool_manager.core import (
    ErrorEntry,
    ErrorMap,
    Module,
    ParamSpec,
    Service,
    ToolError,
    ToolResponse,
    ToolSpec,
    ToToolManager,
    build_instructions,
    build_service_description,
    build_system_prompt,
    class_summary,
    discover_methods,
    make_safe_caller,
)
from to_tool_manager.core.planner import (
    JSONPatchOp,
    Plan,
    PlanEvent,
    PlanEventHandler,
    Planner,
    ServiceDependency,
    ServiceDependencyGraph,
    Step,
    StepOperation,
    StepStatus,
)
from to_tool_manager.security.middleware import Middleware, ToolMiddleware

__all__ = [
    "ToToolManager",
    "Service",
    "Module",
    "ToolSpec",
    "ToolResponse",
    "ToolError",
    "ParamSpec",
    "ErrorMap",
    "ErrorEntry",
    "discover_methods",
    "class_summary",
    "make_safe_caller",
    "build_system_prompt",
    "build_instructions",
    "build_service_description",
    # Planning
    "Plan",
    "Step",
    "StepStatus",
    "StepOperation",
    "Planner",
    "ServiceDependency",
    "ServiceDependencyGraph",
    "PlanEvent",
    "PlanEventHandler",
    "JSONPatchOp",
    # Security
    "Middleware",
    "ToolMiddleware",
]

__version__ = "0.2.0"
