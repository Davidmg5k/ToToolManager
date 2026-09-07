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
        """Helper to call sync or async from dispatch.

        Usage in dispatch:
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
        """Returns frozenset of included methods, or None.

        Precondition: __include was initialized in __init__
        Postcondition: returns frozenset[str] or None
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
        """Returns frozenset of excluded methods, or None.

        Precondition: __exclude was initialized in __init__
        Postcondition: returns frozenset[str] or None
        """
        if self.__exclude is None:
            return None
        if isinstance(self.__exclude, frozenset):
            return self.__exclude
        if isinstance(self.__exclude, Exclude):
            return frozenset(self.__exclude.exclude)
        return frozenset(self.__exclude)

    def is_allowed(self, method_name: str) -> bool:
        """Checks if a method is allowed.

        Precondition: method_name is a str
        Postcondition: returns True if the method is allowed

        Rules:
        - If include is defined, method_name must be in include
        - If exclude is defined, method_name must not be in exclude
        - include takes priority over exclude
        """
        # include takes priority over exclude
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
    """Base middleware for node transitions in pydantic_graph.

    Intercepts the node->node transition before the next node
    executes. Can approve or block the transition.

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
        """Pre-transition hook. Decides if the transition proceeds.

        Precondition: source_node_id can be None (from start),
                      target_node_id is the target node
        Postcondition: returns True if approved, False if blocked
        """
        return True

    async def before_run(
        self,
        node: BaseNode[Any, Any, Any],
        ctx: GraphRunContext[Any, Any],
    ) -> None:
        """Pre-execution hook (for NodeWrapper). Modify state before the node runs."""
        ...

    async def after_run(
        self,
        node: BaseNode[Any, Any, Any],
        ctx: GraphRunContext[Any, Any],
        next_node: BaseNode[Any, Any, Any] | End[Any],
    ) -> BaseNode[Any, Any, Any] | End[Any]:
        """Post-execution hook (for NodeWrapper). Decide if the transition proceeds."""
        return next_node


class NodeWrapper(BaseNode[StateT, DepsT, NodeRunEndT]):
    """Wrapper that applies a chain of NodeMiddleware to a node.

    Works as a class: pydantic_graph instantiates nodes without arguments,
    so the wrapped_node_type and middlewares are stored as
    class-level attributes in dynamic subclasses.

    Usage::

        # Create wrapper as a class
        WrappedMyNode = type(
            "WrappedMyNode",
            (NodeWrapper,),
            {"_wrapped_node_type": MyNode, "_middlewares_attr": [my_mw]},
        )

        # Use in graph
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
