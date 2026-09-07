import pytest
from to_tool_manager.core.builder.ttm_builder import TTMBuilder


class RefundService:
    """Refund service for testing."""

    def status(self, order_id: str) -> str:
        return f"Order {order_id}: refund status is not available yet."

    def issue(self, order_id: str, reason: str) -> str:
        return f"Refund issued for order {order_id}. Reason: {reason}"


class TestMCPAdapter:
    """Tests for the MCP adapter."""

    def test_to_mcp_tool_creates_fastmcp(self):
        """to_mcp_tool() creates a FastMCP instance"""
        from fastmcp import FastMCP

        builder = TTMBuilder(name="MCPAgent")
        builder.add_service(
            name="refunds",
            service=RefundService,
            instructions="Refunds."
        )
        builder.build()

        mcp_app = builder.to_mcp_tool(
            name="CustomerSupportMCP",
            instructions="Customer support MCP server."
        )
        assert isinstance(mcp_app, FastMCP)

    def test_to_mcp_tool_has_name(self):
        """FastMCP has the correct name"""
        builder = TTMBuilder(name="MCPAgent")
        builder.add_service(
            name="refunds",
            service=RefundService,
            instructions="Refunds."
        )
        builder.build()

        mcp_app = builder.to_mcp_tool(
            name="CustomerSupportMCP",
            instructions="Customer support MCP server."
        )
        assert mcp_app.name == "CustomerSupportMCP"

    def test_to_mcp_tool_with_multiple_services(self):
        """to_mcp_tool() works with multiple services"""
        builder = TTMBuilder(name="MCPAgent")
        builder.add_service(
            name="refunds",
            service=RefundService,
            instructions="Refunds."
        )
        builder.add_service(
            name="refunds2",
            service=RefundService,
            instructions="Refunds v2."
        )
        builder.build()

        mcp_app = builder.to_mcp_tool(
            name="CustomerSupportMCP",
            instructions="Customer support MCP server."
        )
        assert mcp_app is not None

    def test_to_mcp_tool_without_build_raises(self):
        """to_mcp_tool() without build() should not fail (build is called in context manager)"""
        builder = TTMBuilder(name="MCPAgent")
        builder.add_service(
            name="refunds",
            service=RefundService,
            instructions="Refunds."
        )
        # to_mcp_tool does not require prior build, uses __get_capabilities
        mcp_app = builder.to_mcp_tool(
            name="CustomerSupportMCP",
            instructions="Customer support MCP server."
        )
        assert mcp_app is not None
