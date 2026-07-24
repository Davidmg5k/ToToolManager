from __future__ import annotations

from copy import copy
from functools import wraps
from typing import Any, Callable, Sequence
from abc import ABC, abstractmethod


class Middleware:
    """Base middleware. Override dispatch to intercept tool calls."""

    __name: str = ""

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        if not cls.__name:
            cls.__name = cls.__name__

    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.dispatch(func, *args, **kwargs)
        return wrapper

    @property
    def name(self) -> str:
        return self.__name

    @abstractmethod
    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        ...


class ToolMiddleware(Middleware):
    """Middleware with method-level filtering via include/exclude.

    Subclass and override ``dispatch`` just like ``Middleware``.
    The ``include`` / ``exclude`` filters are checked at dispatch-table
    build time: methods that don't pass are excluded entirely so the
    LLM never sees them.

    Usage::

        class MyToolFilter(ToolMiddleware):
            async def dispatch(self, func, /, *args, **kw):
                print(f"Calling {func}")
                return await func(*args, **kw)

        svc = Service(
            name="Order",
            service=Order,
            middlewares=[MyToolFilter(include=["create", "list"])],
        )
    """

    __slots__ = ("__include", "__exclude")

    def __init__(
        self,
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
    ) -> None:
        super().__init__()
        self.__include = frozenset(include) if include else None
        self.__exclude = frozenset(exclude) if exclude else None

    @property
    def include(self) -> frozenset[str] | None:
        return copy(self.__include) if self.__include else None

    @property
    def exclude(self) -> frozenset[str] | None:
        return copy(self.__exclude) if self.__exclude else None

    def is_allowed(self, method_name: str) -> bool:
        if self.__include and method_name not in self.__include:
            return False
        if self.__exclude and method_name in self.__exclude:
            return False
        return True
