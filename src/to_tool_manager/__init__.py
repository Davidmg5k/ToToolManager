"""
to_tool_manager
===============

Turns plain Python classes ("services") into agent tools, without tying
you to any specific agent framework.

Core usage (framework-agnostic)::

    from to_tool_manager import ToToolManager, Service

    manager = ToToolManager([
        Service(name="Order", service=Order, description="..."),
    ])
    specs = manager.tool_specs  # list[ToolSpec] -- pure data, no framework

Adapters translate `tool_specs` into whatever a specific framework
expects, and are imported separately so this package has ZERO hard
dependency on any agent framework::

    from to_tool_manager.adapters.pydantic_ai import to_pydantic_ai_tools
    from to_tool_manager.adapters.fastmcp import register_on_mcp
    from to_tool_manager.adapters.raw import to_openai_tool_schemas, dispatch
"""
from typing import TYPE_CHECKING

from to_tool_manager.adapters.pydantic_ai import build_agent

if TYPE_CHECKING:
    # Only for static analysis -- see the module-level __getattr__ below
    # for why this isn't a real, unconditional runtime import.
    from to_tool_manager.adapters.fastmcp import build_mcp_agent, build_mcp_server
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
    # Builders
    "build_agent",
    "build_mcp_agent",
    "build_mcp_server",
]

__version__ = "0.4.5"


def __getattr__(name: str):
    """Lazily loads the fastmcp adapter's public names.

    `build_mcp_agent`/`build_mcp_server` are listed in `__all__` (and thus
    part of the public API accessible as `to_tool_manager.build_mcp_agent`
    / `from to_tool_manager import build_mcp_agent`) but the fastmcp
    adapter itself -- and only that adapter -- requires the optional
    `fastmcp` package. Importing it lazily here (PEP 562), instead of at
    module load time, means `import to_tool_manager` never fails just
    because `fastmcp` isn't installed; the adapter's own friendly
    `ImportError` (see `adapters/fastmcp.py`) still fires, just at first
    use of one of these two names instead of at package import time --
    matching the package-level promise ("ZERO hard dependency on any
    agent framework") stated in this module's own docstring.
    """
    if name in ("build_mcp_agent", "build_mcp_server"):
        from to_tool_manager.adapters.fastmcp import build_mcp_agent, build_mcp_server

        globals()["build_mcp_agent"] = build_mcp_agent
        globals()["build_mcp_server"] = build_mcp_server
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
