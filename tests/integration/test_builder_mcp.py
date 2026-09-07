import asyncio
from to_tool_manager.core.builder.ttm_builder import TTMBuilder
from to_tool_manager.core.main.service import Service


class OrderService:
    """Order service for testing."""

    def create_order(self, product: str, qty: int) -> str:
        return f"Order created: {qty}x {product}"

    def get_order(self, order_id: int) -> dict:
        return {"id": order_id, "status": "pending"}


class PaymentService:
    """Payment service for testing."""

    def process_payment(self, amount: float) -> str:
        return f"Payment of {amount} processed"

    def refund(self, payment_id: int) -> str:
        return f"Refund for payment {payment_id}"


class TestBuilderMcpIntegration:
    """Integration tests for TTMBuilder.to_mcp_tool."""

    def test_to_mcp_tool_with_multiple_services(self):
        """to_mcp_tool combines tools from multiple services."""
        builder = TTMBuilder(name="CommerceAgent")
        builder.add_service(
            name="Order",
            service=OrderService,
            instructions="Order management"
        )
        builder.add_service(
            name="Payment",
            service=PaymentService,
            instructions="Payment management"
        )
        app = builder.to_mcp_tool(name="CommerceMCP", instructions="Commerce tools")
        tools = asyncio.run(app.list_tools())
        tool_names = {t.name for t in tools}
        assert "Order__create_order" in tool_names
        assert "Order__get_order" in tool_names
        assert "Payment__process_payment" in tool_names
        assert "Payment__refund" in tool_names

    def test_to_mcp_tool_after_build(self):
        """to_mcp_tool works after explicit build()."""
        builder = TTMBuilder(name="Agent")
        builder.add_service(
            name="Order",
            service=OrderService,
            instructions="Order management"
        )
        builder.build()
        app = builder.to_mcp_tool(name="MCP", instructions="Tools")
        tools = asyncio.run(app.list_tools())
        assert len(tools) == 2

    def test_to_mcp_tool_preserves_agent_state(self):
        """to_mcp_tool does not overwrite the already built agent."""
        builder = TTMBuilder(name="Agent")
        builder.add_service(
            name="Order",
            service=OrderService,
            instructions="Order management"
        )
        builder.build()
        original_agent = builder.agent
        builder.to_mcp_tool(name="MCP", instructions="Tools")
        assert builder.agent is original_agent
