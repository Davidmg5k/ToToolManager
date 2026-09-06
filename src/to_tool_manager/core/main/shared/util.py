from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Sequence

if TYPE_CHECKING:
    from to_tool_manager.core.main.service import Service

from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend


def service_to_dependency(service: Service, dinamic_depend: DinamicDepend) -> None:
    """Registra el servicio como dependencia dinámica.

    Precondición: service es un Service válido, dinamic_depend es válido
    Postcondición: servicio registrado como atributo en dinamic_depend
    """
    dinamic_depend.__setattr__(
        service.name,
        service.service(*service.args, **service.kwargs)
    )


def build_module_capabilities(
    services: Sequence[Service],
    capabilities: list,
    apply_middleware_fn: Callable[[Service], None],
    dep: DinamicDepend,
) -> list:
    """Construye capabilities para cada servicio de un módulo.

    Precondición: services es una secuencia válida, capabilities es una lista
    Postcondición: capabilities enriquecida con las capabilities de cada servicio

    Flujo: Para cada servicio → aplicar middlewares del módulo →
           construir capability → registrar dependencia

    Referencia: REQ-002, REQ-007
    """
    for service in services:
        apply_middleware_fn(service)
        capabilities.append(service.build_as_capability())
        service.service_to_dependency(dep)
    return capabilities
