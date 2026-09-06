from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable, Sequence
from abc import ABC, abstractmethod

from pydantic_graph import BaseNode, End, GraphRunContext
from pydantic_graph.basenode import StateT, DepsT, NodeRunEndT

from to_tool_manager.infra.types.main.service import Include, Exclude
from to_tool_manager.infra.types.main.signature import MethodsType


class Middleware(ABC):
    """Base middleware. Override dispatch to intercept tool calls."""

    _middleware_name: str = ""

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        if "_middleware_name" not in cls.__dict__:
            cls._middleware_name = cls.__name__

    def __call__(self, func):
        is_async_func = inspect.iscoroutinefunction(func)

        async def _to_awaitable(*args, **kwargs):
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                return await result
            return result

        if is_async_func:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await self.dispatch(func, *args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            async def sync_wrapper(*args, **kwargs):
                result = self.dispatch(_to_awaitable, *args, **kwargs)
                if inspect.isawaitable(result):
                    return await result
                return result
            return sync_wrapper

    @staticmethod
    async def call_func(func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Helper para llamar sync o async desde dispatch.

        Usage en dispatch:
            return await self.call_func(func, *args, **kwargs)
        """
        result = func(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    @property
    def name(self) -> str:
        return self._middleware_name

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
        include: MethodsType | Include | None = None,
        exclude: MethodsType | Exclude | None = None,
    ) -> None:
        super().__init__()
        self.__include = include
        self.__exclude = exclude

    @property
    def include(self) -> frozenset[str] | None:
        """Retorna frozenset de métodos incluidos, o None.

        Precondición: __include fue inicializado en __init__
        Postcondición: retorna frozenset[str] o None
        """
        if self.__include is None:
            return None
        if isinstance(self.__include, frozenset):
            return self.__include
        if isinstance(self.__include, Include):
            return frozenset(self.__include.include)
        return frozenset(self.__include)

    @property
    def exclude(self) -> frozenset[str] | None:
        """Retorna frozenset de métodos excluidos, o None.

        Precondición: __exclude fue inicializado en __init__
        Postcondición: retorna frozenset[str] o None
        """
        if self.__exclude is None:
            return None
        if isinstance(self.__exclude, frozenset):
            return self.__exclude
        if isinstance(self.__exclude, Exclude):
            return frozenset(self.__exclude.exclude)
        return frozenset(self.__exclude)

    def is_allowed(self, method_name: str) -> bool:
        """Verifica si un método está permitido.

        Precondición: method_name es un str
        Postcondición: retorna True si el método está permitido

        Reglas:
        - Si include está definido, method_name debe estar en include
        - Si exclude está definido, method_name no debe estar en exclude
        - include tiene prioridad sobre exclude
        """
        # include tiene prioridad sobre exclude
        if self.__include is not None:
            include_set = self.include
            if include_set is not None:
                return method_name in include_set

        if self.__exclude is not None:
            exclude_set = self.exclude
            if exclude_set is not None:
                return method_name not in exclude_set

        return True


class NodeMiddleware(ABC):
    """Base middleware para transiciones de nodo en grafo (pydantic_graph).

    Intercepta la transición nodo→nodo antes de que el siguiente nodo
    se ejecute. Puede aprobar o bloquear la transición.

    Usage::

        class AuthMiddleware(NodeMiddleware):
            async def before_transition(self, source_id, target_id, state):
                if target_id == "AdminNode":
                    return await self._check_permission(state)
                return True
    """

    _middleware_name: str = ""

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        if "_middleware_name" not in cls.__dict__:
            cls._middleware_name = cls.__name__

    @property
    def name(self) -> str:
        return self._middleware_name

    async def before_transition(
        self,
        source_node_id: str | None,
        target_node_id: str,
        state: Any,
    ) -> bool:
        """Hook pre-transición. Decide si la transición procede.

        Precondición: source_node_id puede ser None (desde start),
                      target_node_id es el nodo destino
        Postcondición: retorna True si aprobado, False si bloqueado
        """
        return True

    async def before_run(
        self,
        node: BaseNode[Any, Any, Any],
        ctx: GraphRunContext[Any, Any],
    ) -> None:
        """Hook pre-ejecución (para NodeWrapper). Modificar state antes de que el nodo corra."""
        ...

    async def after_run(
        self,
        node: BaseNode[Any, Any, Any],
        ctx: GraphRunContext[Any, Any],
        next_node: BaseNode[Any, Any, Any] | End[Any],
    ) -> BaseNode[Any, Any, Any] | End[Any]:
        """Hook post-ejecución (para NodeWrapper). Decidir si la transición procede."""
        return next_node


class NodeWrapper(BaseNode[StateT, DepsT, NodeRunEndT]):
    """Wrapper que aplica una cadena de NodeMiddleware a un nodo.

    Funciona como clase: pydantic_graph instancia nodos sin argumentos,
    así que el wrapped_node_type y middlewares se almacenan como
    class-level attributes en las subclases dinámicas.

    Usage::

        # Crear wrapper como clase
        WrappedMyNode = type(
            "WrappedMyNode",
            (NodeWrapper,),
            {"_wrapped_node_type": MyNode, "_middlewares_attr": [my_mw]},
        )

        # Usar en graph
        graph = Graph(nodes=[WrappedMyNode, ...])
    """

    _wrapped_node_type: type[BaseNode[Any, Any, Any]]
    _middlewares_attr: Sequence[NodeMiddleware]

    async def run(
        self,
        ctx: GraphRunContext[StateT, DepsT],
    ) -> BaseNode[StateT, DepsT, Any] | End[NodeRunEndT]:
        wrapped = self._wrapped_node_type()
        middlewares = self._middlewares_attr

        for mw in middlewares:
            await mw.before_run(wrapped, ctx)

        next_node = await wrapped.run(ctx)

        for mw in reversed(middlewares):
            next_node = await mw.after_run(wrapped, ctx, next_node)

        return next_node
