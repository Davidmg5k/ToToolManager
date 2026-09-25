"""Unit tests for GraphMiddlewareRunner.

Requirement: R-MW-GR-001 (node-transition middleware interception)
Target: src/to_tool_manager/middleware/graph_runner.py
"""

from __future__ import annotations

from typing import Any

from pydantic_graph import BaseNode, End, GraphBuilder

from to_tool_manager.core.middleware.middleware import NodeMiddleware
from to_tool_manager.middleware.graph_runner import GraphMiddlewareRunner


class _RecordingMiddleware(NodeMiddleware):
    """Records every transition and applies a blocking rule."""

    def __init__(self, blocked_target: str | None = None) -> None:
        self.blocked_target = blocked_target
        self.calls: list[tuple[str | None, str, Any]] = []

    async def before_transition(
        self,
        source_node_id: str | None,
        target_node_id: str,
        state: Any,
    ) -> bool:
        self.calls.append((source_node_id, target_node_id, state))
        return target_node_id != self.blocked_target


class NodeB(BaseNode[dict, None, str]):
    """Terminal node: produces the graph output."""

    async def run(self, ctx) -> End[str]:
        return End("DONE")


class NodeA(BaseNode[dict, None, str]):
    """Entry node: always delegates to NodeB."""

    async def run(self, ctx) -> NodeB:
        return NodeB()


def _build_graph():
    """Builds the A -> B -> End demo graph.

    The start node is wired explicitly because pydantic_graph does not
    infer an entry edge from a plain BaseNode subclass.
    """
    builder = GraphBuilder(name="graph_runner_test", output_type=str)
    builder.add(
        builder.edge_from(builder.start_node).to(NodeA),
        builder.node(NodeA),
        builder.node(NodeB),
    )
    return builder.build()


class TestGraphMiddlewareRunner:
    """Tests for graph execution with node-transition middleware."""

    async def test_run_returns_final_output_when_middleware_approves(self):
        """Approved transitions reach the End node and return its value."""
        mw = _RecordingMiddleware()
        runner = GraphMiddlewareRunner(_build_graph(), [mw])

        out = await runner.run(state={"k": "v"}, inputs=NodeA())

        assert out == "DONE"
        # First transition: start (None source) -> NodeA
        assert (None, "NodeA", {"k": "v"}) in mw.calls
        # Second transition: NodeA -> NodeB
        assert ("NodeA", "NodeB", {"k": "v"}) in mw.calls

    async def test_run_blocks_start_transition_and_returns_none(self):
        """Blocking the very first transition short-circuits to None."""
        mw = _RecordingMiddleware(blocked_target="NodeA")
        runner = GraphMiddlewareRunner(_build_graph(), [mw])

        out = await runner.run(state={}, inputs=NodeA())

        assert out is None
        assert len(mw.calls) == 1
        assert mw.calls[0][1] == "NodeA"

    async def test_run_blocks_mid_transition_and_returns_none(self):
        """Blocking the A -> B transition stops the graph before End."""
        mw = _RecordingMiddleware(blocked_target="NodeB")
        runner = GraphMiddlewareRunner(_build_graph(), [mw])

        out = await runner.run(state={}, inputs=NodeA())

        assert out is None
        assert [c[1] for c in mw.calls] == ["NodeA", "NodeB"]

    async def test_run_multiple_middlewares_require_all_approve(self):
        """The chain short-circuits as soon as one middleware blocks."""
        allow = _RecordingMiddleware()
        block = _RecordingMiddleware(blocked_target="NodeB")
        runner = GraphMiddlewareRunner(_build_graph(), [allow, block])

        out = await runner.run(state={}, inputs=NodeA())

        assert out is None
        # 'allow' saw both transitions; 'block' denied the A -> B one.
        assert [c[1] for c in allow.calls] == ["NodeA", "NodeB"]
        assert [c[1] for c in block.calls] == ["NodeA", "NodeB"]