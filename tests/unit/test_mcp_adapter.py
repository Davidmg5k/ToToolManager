import pytest
from to_tool_manager.core.builder.ttm_builder import TTMBuilder


class RefundService:
    """Servicio de reembolsos para testing."""

    def status(self, order_id: str) -> str:
        return f"Order {order_id}: refund status is not available yet."

    def issue(self, order_id: str, reason: str) -> str:
        return f"Refund issued for order {order_id}. Reason: {reason}"


class TestMCPAdapter:
    """Tests para el adaptador MCP."""

    def test_to_mcp_tool_creates_fastmcp(self):
        """to_mcp_tool() crea una instancia FastMCP"""
        from fastmcp import FastMCP

        builder = TTMBuilder(name="MCPAgent")
        builder.add_service(
            name="refunds",
            service=RefundService,
            instructions="Reembolsos."
        )
        builder.build()

        mcp_app = builder.to_mcp_tool(
            name="CustomerSupportMCP",
            instructions="Servidor MCP de soporte al cliente."
        )
        assert isinstance(mcp_app, FastMCP)

    def test_to_mcp_tool_has_name(self):
        """FastMCP tiene el nombre correcto"""
        builder = TTMBuilder(name="MCPAgent")
        builder.add_service(
            name="refunds",
            service=RefundService,
            instructions="Reembolsos."
        )
        builder.build()

        mcp_app = builder.to_mcp_tool(
            name="CustomerSupportMCP",
            instructions="Servidor MCP de soporte al cliente."
        )
        assert mcp_app.name == "CustomerSupportMCP"

    def test_to_mcp_tool_with_multiple_services(self):
        """to_mcp_tool() funciona con múltiples servicios"""
        builder = TTMBuilder(name="MCPAgent")
        builder.add_service(
            name="refunds",
            service=RefundService,
            instructions="Reembolsos."
        )
        builder.add_service(
            name="refunds2",
            service=RefundService,
            instructions="Reembolsos v2."
        )
        builder.build()

        mcp_app = builder.to_mcp_tool(
            name="CustomerSupportMCP",
            instructions="Servidor MCP de soporte al cliente."
        )
        assert mcp_app is not None

    def test_to_mcp_tool_without_build_raises(self):
        """to_mcp_tool() sin build() no debe fallar (build se llama en context manager)"""
        builder = TTMBuilder(name="MCPAgent")
        builder.add_service(
            name="refunds",
            service=RefundService,
            instructions="Reembolsos."
        )
        # to_mcp_tool no requiere build previo, usa __get_capabilities
        mcp_app = builder.to_mcp_tool(
            name="CustomerSupportMCP",
            instructions="Servidor MCP de soporte al cliente."
        )
        assert mcp_app is not None
