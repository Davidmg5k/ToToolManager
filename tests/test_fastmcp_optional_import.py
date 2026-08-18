"""Regression coverage for hallazgo 1.3 (handoff doc, section 1.3):

`to_tool_manager/__init__.py` used to import the fastmcp adapter
unconditionally, so `import to_tool_manager` would fail with the
adapter's `ImportError` for anyone without `fastmcp` installed --
even if they never intended to use the fastmcp adapter at all. This
contradicted the package's own docstring promise of "ZERO hard
dependency on any agent framework".

Because the real environment this suite normally runs in already has
`fastmcp` (or the `fastmcp-slim` shim, pulled in transitively by
`pydantic-ai-harness`) importable, and other test modules in this same
session already import `to_tool_manager.adapters.fastmcp` (populating
`sys.modules`), this can't be verified reliably via in-process
monkeypatching. Instead, run a real subprocess with `fastmcp` (and
anything providing that name, e.g. `fastmcp_slim`) made unimportable,
matching the "install without the fastmcp extra" scenario the handoff
doc describes.
"""

import subprocess
import sys


_SCRIPT = """
import builtins

_real_import = builtins.__import__

def _blocking_import(name, *args, **kwargs):
    if name == "fastmcp" or name.startswith("fastmcp."):
        raise ImportError("No module named 'fastmcp' (simulated for test)")
    return _real_import(name, *args, **kwargs)

builtins.__import__ = _blocking_import

# The package itself must import cleanly with fastmcp unavailable.
import to_tool_manager  # noqa: E402

# The two fastmcp-adapter names are still part of the public API...
assert "build_mcp_agent" in to_tool_manager.__all__
assert "build_mcp_server" in to_tool_manager.__all__

# ...but only fail, with the adapter's own friendly message, at first
# actual use -- not at package-import time.
try:
    to_tool_manager.build_mcp_agent
except ImportError as exc:
    assert "fastmcp" in str(exc)
else:
    raise AssertionError("expected ImportError when fastmcp is unavailable")

print("OK")
"""


def test_import_to_tool_manager_without_fastmcp_does_not_fail():
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "OK" in result.stdout
