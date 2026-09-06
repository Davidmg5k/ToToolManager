from __future__ import annotations

from typing import Any, Sequence

from pydantic_graph import Graph
from pydantic_graph.graph_builder import EndMarker

from to_tool_manager.core.middleware.middleware import NodeMiddleware


class GraphMiddlewareRunner:
    """Ejecuta un grafo de pydantic_graph con una cadena de NodeMiddleware.

    Intercepta transiciones nodo→nodo usando override_next del GraphRun.
    Cada transición pasa por la cadena de middleware antes de ejecutar
    el siguiente nodo.

    Precondición: graph es válido, middlewares no está vacío
    Postcondición: grafo ejecutado con middleware aplicado a cada transición
    """

    __slots__ = ("_graph", "_middlewares")

    def __init__(
        self,
        graph: Graph[Any, Any, Any, Any],
        middlewares: Sequence[NodeMiddleware],
    ) -> None:
        """
        Precondición: graph es válido, middlewares es secuencia de NodeMiddleware
        Postcondición: graph y middlewares inicializados
        """
        self._graph = graph
        self._middlewares = middlewares

    async def run(
        self,
        state: Any = None,
        deps: Any = None,
        inputs: Any = None,
    ) -> Any:
        """Ejecuta el grafo con middleware aplicado a cada transición.

        Precondición: graph es válido, middlewares configurados
        Postcondición: retorna el resultado final del grafo
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
        """Ejecuta la cadena de middleware para una transición.

        Precondición: source_node_id puede ser None (start), target_node_id es válido
        Postcondición: retorna True si la transición está aprobada, False si bloqueada
        """
        for mw in self._middlewares:
            approved = await mw.before_transition(source_node_id, target_node_id, state)
            if not approved:
                return False

        return True
