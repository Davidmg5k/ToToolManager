from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class MethodMeta:
    """Metadata of a discovered service method.

    Precondition: func is a valid method
    Postcondition: contains all information needed to create a tool
    """
    name: str
    func: Callable[..., Any]
    is_async: bool
    docstring: str | None
    parameters: dict[str, inspect.Parameter]


def discover_methods(service_class: type) -> list[MethodMeta]:
    """Discovers public methods of a service class.

    Precondition: service_class is a valid class
    Postcondition: returns list of MethodMeta with public methods

    Rules:
    - Excludes private methods (start with _)
    - Excludes dunder methods (__init__, __str__, etc)
    - Only includes methods defined directly in the class (not inherited)
    """
    methods = []
    for name, func in inspect.getmembers(service_class, predicate=inspect.isfunction):
        if name.startswith('_'):
            continue

        # Only methods defined in the class (not inherited from object)
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
