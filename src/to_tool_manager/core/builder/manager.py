from typing import Dict, List, Sequence

from pydantic_ai import Capability
from pydantic_ai_harness.subagents import SubAgent, SubAgents
from pydantic_ai_skills import Skill

from to_tool_manager.core.main.module import Module
from to_tool_manager.core.main.service import Service
from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend
from to_tool_manager.core.main.to_tool_manager import ToToolManager
from to_tool_manager.core.middleware.middleware import Middleware
from to_tool_manager.exception import (
    ModuleAlreadyRegisteredError,
    ServiceAlreadyRegisteredError,
    ServiceNotFoundError,
    ToToolManagerAlreadyRegisteredError,
    ToToolManagerNotFoundError,
)


class Manager:
    """Manages services, modules, skills, and ToToolManagers.

    Precondition: none
    Postcondition: data structures initialized
    """

    def __init__(self) -> None:
        self.__services: Dict[str, Capability] = {}
        self.__service_objects: Dict[str, Service] = {}
        self.__modules: Dict[str, SubAgent[DinamicDepend]] = {}
        self.__skills: List[Skill] = []
        self.__ttm: Dict[str, ToToolManager] = {}

    def toolsets(self, toolsets: List | None):
        """Builds the toolsets list by combining modules and skills.

        Precondition: toolsets is None or a valid list
        Postcondition: returns combined list
        """
        toolsets_ = []
        skills = self.__skills

        if len(skills) > 0:
            toolsets_ += self.__skills

        if toolsets is None:
            return toolsets_
        return toolsets_ + toolsets

    def capabilities(self, capabilities: List | None):
        """Combines registered capabilities with provided ones.

        Precondition: capabilities is None or a valid list
        Postcondition: returns combined list
        """
        caps = list(self.__services.values())
        modules = self.__modules

        if len(modules) > 0:
            caps.append(SubAgents(agents=list(modules.values())))

        if capabilities is None:
            return caps
        return caps + capabilities

    @property
    def service_objects(self) -> Dict[str, Service]:
        """Returns the original registered Service objects.

        Precondition: none
        Postcondition: returns dict with Service objects
        """
        return self.__service_objects

    def add_service(self, service: Service, dep: DinamicDepend):
        """Adds a service to the manager.

        Precondition: service.name is unique, dep is valid
        Postcondition: service registered as Capability
        """
        name = service.name
        if name in self.__services:
            raise ServiceAlreadyRegisteredError(name)
        self.__services[name] = service.build_as_capability()
        self.__service_objects[name] = service
        service.service_to_dependency(dep)

    def add_module(self, module: Module):
        """Adds a module to the manager.

        Precondition: module.name is unique
        Postcondition: module registered as SubAgent
        """
        name = module.name
        if name in self.__modules:
            raise ModuleAlreadyRegisteredError(name)
        self.__modules[name] = module.build_as_agent()

    def add_skill(self, skill: Skill):
        """Adds a skill to the manager.

        Precondition: skill is valid
        Postcondition: skill added to list
        """
        self.__skills.append(skill)

    def add_middleware_to_service(self, ttm_name: str, service_name: str, middleware):
        """Adds a middleware to a service via ToToolManager.

        Precondition: ttm_name and service_name exist
        Postcondition: middleware added
        """
        ttm = self.__get_ttm(ttm_name)
        ttm.add_middleware_to_service(service_name, middleware)

    def add_middleware_to_module(self, ttm_name: str, module_name: str, middleware):
        """Adds a middleware to a module via ToToolManager.

        Precondition: ttm_name and module_name exist
        Postcondition: middleware added
        """
        ttm = self.__get_ttm(ttm_name)
        ttm.add_middleware_to_module(module_name, middleware)

    def remove_middleware_to_service(self, ttm_name: str, service_name: str, middleware):
        """Removes a middleware from a service via ToToolManager.

        Precondition: ttm_name and service_name exist
        Postcondition: middleware removed
        """
        ttm = self.__get_ttm(ttm_name)
        ttm.remove_middleware_to_service(service_name, middleware)

    def remove_middleware_from_services(self, service_name: str, middleware_type: type):
        """Removes a middleware from a service by type.

        Precondition: service_name exists in registered services
        Postcondition: middleware removed from the original Service
        """
        if service_name not in self.__service_objects:
            raise ServiceNotFoundError(service_name)
        service = self.__service_objects[service_name]
        if service.middleware is not None:
            service.middleware = [
                m for m in service.middleware if not isinstance(m, middleware_type)
            ]

    def apply_middlewares_to_services(self, middlewares: Sequence[Middleware]) -> None:
        """Applies middlewares to the original registered Services.

        Precondition: middlewares is a valid sequence
        Postcondition: middlewares added to each Service
        """
        for service in self.__service_objects.values():
            for mw in middlewares:
                if service.middleware is None:
                    service.middleware = []
                service.middleware.append(mw)

    def rebuild_capabilities(self) -> None:
        """Rebuilds Capabilities from the original Services.

        Precondition: services have been registered
        Postcondition: __services updated with fresh Capabilities
        """
        for name, service in self.__service_objects.items():
            self.__services[name] = service.build_as_capability()

    def remove_middleware_to_module(self, ttm_name: str, module_name: str, middleware):
        """Removes a middleware from a module via ToToolManager.

        Precondition: ttm_name and module_name exist
        Postcondition: middleware removed
        """
        ttm = self.__get_ttm(ttm_name)
        ttm.remove_middleware_to_module(module_name, middleware)

    def add_ttm(self, ttm: ToToolManager):
        """Adds a ToToolManager to the manager.

        Precondition: ttm.name is unique
        Postcondition: ToToolManager registered
        """
        name = ttm.name
        if name in self.__ttm:
            raise ToToolManagerAlreadyRegisteredError(name)
        self.__ttm[name] = ttm

    def __get_ttm(self, name: str):
        """Gets a ToToolManager by name.

        Precondition: name exists in __ttm
        Postcondition: returns ToToolManager
        """
        if name not in self.__ttm:
            raise ToToolManagerNotFoundError(name)
        return self.__ttm[name]
