"""Contract tests for `fastmcp` as an optional dependency.

Scenario (ADR/decisión de dependencia): `fastmcp` lives in a PEP 735
dependency-group, which is NOT published in the package metadata. Therefore a
consumer that runs `uv add <repo-url>` receives `to-tool-manager` WITHOUT
`fastmcp`.

Two guarantees are verified here:
  1. `import to_tool_manager` succeeds even when `fastmcp` cannot be imported.
  2. `TTMBuilder.to_mcp_tool()` fails with the typed `FastMCPNotInstalledError`
     (actionable message), never with a raw `ModuleNotFoundError`.
"""

import subprocess
import sys

import pytest

from to_tool_manager import FastMCPNotInstalledError, TTMBuilder
from to_tool_manager.exception import BuilderError, TTMError


class OrderService:
    """Service used to exercise the MCP entry point."""

    def create_order(self, product: str, qty: int) -> str:
        return f"Order created: {qty}x {product}"


def _builder() -> TTMBuilder:
    """Precondition: none. Postcondition: builder with one service, unbuilt."""
    builder = TTMBuilder(name="MCPAgent")
    builder.add_service(
        name="orders",
        service=OrderService,
        instructions="Order management.",
    )
    return builder


class TestPackageImportsWithoutFastMCP:
    """Guarantee 1: the package must import with `fastmcp` absent."""

    def test_import_ttm_succeeds_when_fastmcp_is_unimportable(self):
        """Precondition: a clean subprocess. Postcondition: import succeeds."""
        code = (
            "import sys\n"
            "class _Blocker:\n"
            "    def find_spec(self, name, path=None, target=None):\n"
            "        if name == 'fastmcp' or name.startswith('fastmcp.'):\n"
            "            raise ImportError('fastmcp blocked by test')\n"
            "sys.meta_path.insert(0, _Blocker())\n"
            "import to_tool_manager\n"
            "from to_tool_manager import TTMBuilder\n"
            "assert TTMBuilder is not None\n"
            "print('IMPORT_OK')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert "IMPORT_OK" in proc.stdout


class TestToMCPToolWithoutFastMCP:
    """Guarantee 2: the MCP entry point fails with a typed, actionable error."""

    def test_raises_fastmcp_not_installed_error(self, monkeypatch):
        """Precondition: `fastmcp` unavailable. Postcondition: typed error."""
        monkeypatch.setitem(sys.modules, "fastmcp", None)

        with pytest.raises(FastMCPNotInstalledError) as exc_info:
            _builder().to_mcp_tool(name="MCP", instructions="Tools")

        assert "fastmcp is not installed" in str(exc_info.value)

    def test_error_is_a_ttm_builder_error(self, monkeypatch):
        """Postcondition: catchable via the public exception hierarchy."""
        monkeypatch.setitem(sys.modules, "fastmcp", None)

        with pytest.raises(BuilderError):
            _builder().to_mcp_tool(name="MCP", instructions="Tools")

        with pytest.raises(TTMError):
            _builder().to_mcp_tool(name="MCP", instructions="Tools")

    def test_error_message_is_actionable(self, monkeypatch):
        """Postcondition: the message states how to restore the capability."""
        monkeypatch.setitem(sys.modules, "fastmcp", None)

        with pytest.raises(FastMCPNotInstalledError) as exc_info:
            _builder().to_mcp_tool(name="MCP", instructions="Tools")

        message = str(exc_info.value)
        assert "uv add" in message
        assert "fastmcp" in message

    def test_error_preserves_the_original_cause(self, monkeypatch):
        """Postcondition: the root ImportError is chained, not swallowed."""
        monkeypatch.setitem(sys.modules, "fastmcp", None)

        with pytest.raises(FastMCPNotInstalledError) as exc_info:
            _builder().to_mcp_tool(name="MCP", instructions="Tools")

        assert isinstance(exc_info.value.__cause__, ImportError)

    def test_rest_of_the_builder_still_works(self, monkeypatch):
        """Precondition: fastmcp absent. Postcondition: non-MCP paths intact."""
        monkeypatch.setitem(sys.modules, "fastmcp", None)

        builder = _builder()
        builder.build()

        assert builder.agent is not None
        assert builder.dependency is not None
