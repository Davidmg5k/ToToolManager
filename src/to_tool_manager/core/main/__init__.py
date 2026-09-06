"""to_tool_manager — Core main module.

Public API:
- Service: Expone métodos como tools para LLMs
- Module: Agrupa servicios como sub-agente
- ToToolManager: Orquestador de servicios y módulos
"""

from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.to_tool_manager import ToToolManager

__all__ = ["Service", "Module", "ToToolManager"]
