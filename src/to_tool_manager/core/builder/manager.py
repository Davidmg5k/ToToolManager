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
    """Gestiona servicios, módulos, skills y ToToolManagers.

    Precondición: ninguno
    Postcondición: estructuras de datos inicializadas
    """

    def __init__(self) -> None:
        self.__services: Dict[str, Capability] = {}
        self.__service_objects: Dict[str, Service] = {}
        self.__modules: Dict[str, SubAgent[DinamicDepend]] = {}
        self.__skills: List[Skill] = []
        self.__ttm: Dict[str, ToToolManager] = {}

    def toolsets(self, toolsets: List | None):
        """Construye la lista de toolsets combinando módulos y skills.

        Precondición: toolsets es None o lista válida
        Postcondición: retorna lista combinada
        """
        toolsets_ = []
        skills = self.__skills

        if len(skills) > 0:
            toolsets_ += self.__skills

        if toolsets is None:
            return toolsets_
        return toolsets_ + toolsets

    def capabilities(self, capabilities: List | None):
        """Combina capabilities registradas con las proporcionadas.

        Precondición: capabilities es None o lista válida
        Postcondición: retorna lista combinada
        """
        caps = list(self.__services.values())
        modules = self.__modules

        if len(modules) > 0:
            caps.append(SubAgents(agents=list(modules.values())))

        if capabilities is None:
            return caps
        return caps + capabilities

    def add_service(self, service: Service, dep: DinamicDepend):
        """Añade un servicio al manager.

        Precondición: service.name es único, dep es válido
        Postcondición: servicio registrado como Capability
        """
        name = service.name
        if name in self.__services:
            raise ServiceAlreadyRegisteredError(name)
        self.__services[name] = service.build_as_capability()
        self.__service_objects[name] = service
        service.service_to_dependency(dep)

    def add_module(self, module: Module):
        """Añade un módulo al manager.

        Precondición: module.name es único
        Postcondición: módulo registrado como SubAgent
        """
        name = module.name
        if name in self.__modules:
            raise ModuleAlreadyRegisteredError(name)
        self.__modules[name] = module.build_as_agent()

    def add_skill(self, skill: Skill):
        """Añade un skill al manager.

        Precondición: skill es válido
        Postcondición: skill añadido a lista
        """
        self.__skills.append(skill)

    def add_middleware_to_service(self, ttm_name: str, service_name: str, middleware):
        """Añade un middleware a un servicio vía ToToolManager.

        Precondición: ttm_name y service_name existen
        Postcondición: middleware añadido
        """
        ttm = self.__get_ttm(ttm_name)
        ttm.add_middleware_to_service(service_name, middleware)

    def add_middleware_to_module(self, ttm_name: str, module_name: str, middleware):
        """Añade un middleware a un módulo vía ToToolManager.

        Precondición: ttm_name y module_name existen
        Postcondición: middleware añadido
        """
        ttm = self.__get_ttm(ttm_name)
        ttm.add_middleware_to_module(module_name, middleware)

    def remove_middleware_to_service(self, ttm_name: str, service_name: str, middleware):
        """Remueve un middleware de un servicio vía ToToolManager.

        Precondición: ttm_name y service_name existen
        Postcondición: middleware removido
        """
        ttm = self.__get_ttm(ttm_name)
        ttm.remove_middleware_to_service(service_name, middleware)

    def remove_middleware_from_services(self, service_name: str, middleware_type: type):
        """Remueve un middleware de un servicio por tipo.

        Precondición: service_name existe en servicios registrados
        Postcondición: middleware removido del Service original
        """
        if service_name not in self.__service_objects:
            raise ServiceNotFoundError(service_name)
        service = self.__service_objects[service_name]
        if service.middleware is not None:
            service.middleware = [
                m for m in service.middleware if not isinstance(m, middleware_type)
            ]

    def apply_middlewares_to_services(self, middlewares: Sequence[Middleware]) -> None:
        """Aplica middlewares a los Service originales registrados.

        Precondición: middlewares es una secuencia válida
        Postcondición: middlewares añadidos a cada Service
        """
        for service in self.__service_objects.values():
            for mw in middlewares:
                if service.middleware is None:
                    service.middleware = []
                service.middleware.append(mw)

    def rebuild_capabilities(self) -> None:
        """Reconstruye las Capabilities desde los Service originales.

        Precondición: servicios han sido registrados
        Postcondición: __services actualizado con Capabilities frescas
        """
        for name, service in self.__service_objects.items():
            self.__services[name] = service.build_as_capability()

    def remove_middleware_to_module(self, ttm_name: str, module_name: str, middleware):
        """Remueve un middleware de un módulo vía ToToolManager.

        Precondición: ttm_name y module_name existen
        Postcondición: middleware removido
        """
        ttm = self.__get_ttm(ttm_name)
        ttm.remove_middleware_to_module(module_name, middleware)

    def add_ttm(self, ttm: ToToolManager):
        """Añade un ToToolManager al manager.

        Precondición: ttm.name es único
        Postcondición: ToToolManager registrado
        """
        name = ttm.name
        if name in self.__ttm:
            raise ToToolManagerAlreadyRegisteredError(name)
        self.__ttm[name] = ttm

    def __get_ttm(self, name: str):
        """Obtiene un ToToolManager por nombre.

        Precondición: name existe en __ttm
        Postcondición: retorna ToToolManager
        """
        if name not in self.__ttm:
            raise ToToolManagerNotFoundError(name)
        return self.__ttm[name]
