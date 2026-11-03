"""Verify every `from to_tool_manager... import X` documented in README.md.

Contract:
  Precondition: README.md and the package are importable from the repo root.
  Postcondition: prints one line per distinct documented import (OK/FAIL) and
  exits non-zero when at least one documented import does not resolve.

Rationale: the README ships as the PyPI landing page for a given release and
cannot be amended afterwards without publishing a new version, so every API it
documents must exist at release time.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
README = ROOT / "README.md"
IMPORT_RE = re.compile(r"from\s+(to_tool_manager[\w.]*)\s+import\s+([^\n]+)")
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def documented_imports(text: str) -> list[tuple[str, str, int]]:
    """Return distinct (module, name, readme_line) triples from README code."""
    seen: dict[tuple[str, str], int] = {}
    for match in IMPORT_RE.finditer(text):
        module, raw_names, line = match.group(1), match.group(2), text.count("\n", 0, match.start()) + 1
        for raw in raw_names.split(","):
            name = re.sub(r"\s+as\s+\w+", "", raw).strip()
            if NAME_RE.match(name):
                seen.setdefault((module, name), line)
    return [(mod, name, ln) for (mod, name), ln in seen.items()]


def main() -> int:
    text = README.read_text(encoding="utf-8")
    documented = documented_imports(text)
    failures: list[str] = []

    for module, name, line in documented:
        try:
            imported = __import__(module, fromlist=[name])
            getattr(imported, name)
        except Exception as exc:  # noqa: BLE001 - reporting harness, must not abort
            failures.append(f"FAIL README.md:{line}  from {module} import {name}  -> {type(exc).__name__}: {exc}")
        else:
            print(f"OK   README.md:{line}  from {module} import {name}")

    print(f"\nChecked {len(documented)} distinct imports documented in README.md")
    if failures:
        print("\n".join(failures))
        print(f"{len(failures)} documented import(s) do NOT resolve.")
        return 1
    print("All documented imports resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
