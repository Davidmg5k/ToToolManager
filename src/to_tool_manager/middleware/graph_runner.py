from __future__ import annotations

from typing import Any, Sequence

from pydantic_graph import Graph
from pydantic_graph.graph_builder import EndMarker

from to_tool_manager.core.middleware.middleware import NodeMiddleware


class GraphMiddlewareRunner:
    """Executes a pydantic_graph with a chain of NodeMiddleware.

    Intercepts node->node transitions using GraphRun's override_next.
    Each transition passes through the middleware chain before executing
    the next node.

    Precondition: graph is valid, middlewares is not empty
    Postcondition: graph executed with middleware applied to each transition
    """

    __slots__ = ("_graph", "_middlewares")

    def __init__(
        self,
        graph: Graph[Any, Any, Any, Any],
        middlewares: Sequence[NodeMiddleware],
    ) -> None:
        """
        Precondition: graph is valid, middlewares is a sequence of NodeMiddleware
        Postcondition: graph and middlewares initialized
        """
        self._graph = graph
        self._middlewares = middlewares

    async def run(
        self,
        state: Any = None,
        deps: Any = None,
        inputs: Any = None,
    ) -> Any:
        """Executes the graph with middleware applied to each transition.

        Precondition: graph is valid, middlewares configured
        Postcondition: returns the final result of the graph
        """
        async with self._graph.iter(
            state=state, deps=deps, inputs=inputs, infer_name=False
        ) as graph_run:
            last_node_id: str | None = None

            result = await anext(graph_run)

            while not isinstance(result, EndMarker):
                if isinstance(result, Sequence) and len(result) > 0:
                    next_task = result[0]
                    next_node_id = next_task.node_id

                    approved = await self._run_middlewares(
                        last_node_id, next_node_id, state
                    )

                    if not approved:
                        graph_run.override_next(EndMarker(None))
                        return None

                    last_node_id = next_node_id

                result = await anext(graph_run)

            return result.value if isinstance(result, EndMarker) else None

    async def _run_middlewares(
        self,
        source_node_id: str | None,
        target_node_id: str,
        state: Any,
    ) -> bool:
        """Executes the middleware chain for a transition.

        Precondition: source_node_id can be None (start), target_node_id is valid
        Postcondition: returns True if transition is approved, False if blocked
        """
        for mw in self._middlewares:
            approved = await mw.before_transition(source_node_id, target_node_id, state)
            if not approved:
                return False

        return True
