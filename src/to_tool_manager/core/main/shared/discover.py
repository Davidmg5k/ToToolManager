from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class MethodMeta:
    """Metadata de un método descubierto de un servicio.

    Precondición: func es un método válido
    Postcondición: contiene toda la información necesaria para crear una tool
    """
    name: str
    func: Callable[..., Any]
    is_async: bool
    docstring: str | None
    parameters: dict[str, inspect.Parameter]


def discover_methods(service_class: type) -> list[MethodMeta]:
    """Descubre métodos públicos de una clase de servicio.

    Precondición: service_class es una clase válida
    Postcondición: retorna lista de MethodMeta con métodos públicos

    Reglas:
    - Excluye métodos privados (empiezan con _)
    - Excluye métodos dunder (__init__, __str__, etc)
    - Solo incluye métodos definidos directamente en la clase (no heredados)
    """
    methods = []
    for name, func in inspect.getmembers(service_class, predicate=inspect.isfunction):
        if name.startswith('_'):
            continue

        # Solo métodos definidos en la clase (no heredados de object)
        if name not in service_class.__dict__:
            continue

        sig = inspect.signature(func)
        params = {k: v for k, v in sig.parameters.items() if k != 'self'}

        methods.append(MethodMeta(
            name=name,
            func=func,
            is_async=inspect.iscoroutinefunction(func),
            docstring=inspect.getdoc(func),
            parameters=params,
        ))

    return methods
