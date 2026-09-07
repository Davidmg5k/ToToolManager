"""to_tool_manager — Core main module.

Public API:
- Service: Exposes methods as tools for LLMs
- Module: Groups services as a sub-agent
- ToToolManager: Orchestrator of services and modules
"""

from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.to_tool_manager import ToToolManager

__all__ = ["Service", "Module", "ToToolManager"]
