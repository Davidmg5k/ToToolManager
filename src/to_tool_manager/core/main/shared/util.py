from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Sequence

if TYPE_CHECKING:
    from to_tool_manager.core.main.service import Service

from to_tool_manager.core.main.shared.dinamic_depend import DinamicDepend


def service_to_dependency(service: Service, dinamic_depend: DinamicDepend) -> None:
    """Registers the service as a dynamic dependency.

    Precondition: service is a valid Service, dinamic_depend is valid
    Postcondition: service registered as an attribute in dinamic_depend
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
    """Builds capabilities for each service in a module.

    Precondition: services is a valid sequence, capabilities is a list
    Postcondition: capabilities enriched with each service's capabilities

    Flow: For each service -> apply module middlewares ->
           build capability -> register dependency

    Reference: REQ-002, REQ-007
    """
    for service in services:
        apply_middleware_fn(service)
        capabilities.append(service.build_as_capability())
        service.service_to_dependency(dep)
    return capabilities
