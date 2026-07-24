"""
Class introspection: turns a plain Python class into a list of
`MethodInfo` — a neutral description of what can become a tool.

No framework imports here. Only `inspect`, `re`, and stdlib typing.
"""
from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from to_tool_manager.core.types import ParamSpec, _MISSING

Visibility = Literal["public", "protected", "private"]

_ALL_VISIBILITIES: frozenset[Visibility] = frozenset({"public", "protected", "private"})


@dataclass(frozen=True, slots=True)
class MethodInfo:
    name: str
    visibility: Visibility
    is_property: bool
    is_coroutine: bool
    doc_summary: str
    parameters: tuple[ParamSpec, ...]


def classify_visibility(name: str, owner_name: str) -> Visibility | None:
    """
    Returns the visibility bucket for a class-member name, or None if the
    name is a "special" (dunder) method — which is NEVER eligible to
    become a tool, regardless of configuration.
    """
    if name.startswith("__") and name.endswith("__"):
        return None  # special/dunder: always excluded, no opt-in possible
    if name.startswith(f"_{owner_name}__"):
        return "private"  # name-mangled `__attr` accessed from outside
    if name.startswith("__"):
        return "private"
    if name.startswith("_"):
        return "protected"
    return "public"


# --- Lightweight, dependency-free docstring parsing -------------------
# Supports Google-style ("Args:") and NumPy-style ("Parameters\n------")
# sections well enough to pull a per-parameter description. Falls back
# gracefully to "no description" if the docstring doesn't follow either
# convention — it never raises.

_GOOGLE_ARG_RE = re.compile(
    r"^\s*(?P<name>\w+)\s*(?:\([^)]*\))?\s*:\s*(?P<desc>.+)$"
)
_NUMPY_ARG_NAME_RE = re.compile(r"^\s*(?P<name>\w+)\s*(?::\s*.+)?$")


def _split_summary_and_body(doc: str) -> tuple[str, str]:
    doc = inspect.cleandoc(doc)
    lines = doc.splitlines()
    if not lines:
        return "", ""
    summary = lines[0].strip()
    body = "\n".join(lines[1:])
    return summary, body


def parse_docstring(doc: str | None) -> tuple[str, dict[str, str]]:
    """
    Returns (summary, {param_name: description}).
    Best-effort: unknown/absent docstrings just yield ("", {}).
    """
    if not doc or not doc.strip():
        return "", {}

    summary, body = _split_summary_and_body(doc)
    param_docs: dict[str, str] = {}

    section_match = re.search(
        r"(Args|Arguments|Parameters)\s*:?\s*\n(?:-+\s*\n)?(?P<body>.+?)"
        r"(?=\n\s*(Returns|Return|Raises|Yields|Examples?|Notes?)\s*:?\s*\n|\Z)",
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not section_match:
        return summary, param_docs

    section_body = section_match.group("body")
    current_name: str | None = None
    current_desc: list[str] = []

    def _flush():
        if current_name:
            param_docs[current_name] = " ".join(current_desc).strip()

    for raw_line in section_body.splitlines():
        if not raw_line.strip():
            continue
        indented_continuation = raw_line.startswith((" " * 4, "\t")) and current_name
        google_match = _GOOGLE_ARG_RE.match(raw_line)
        if google_match and not indented_continuation:
            _flush()
            current_name = google_match.group("name")
            current_desc = [google_match.group("desc").strip()]
        elif indented_continuation:
            current_desc.append(raw_line.strip())
        else:
            # Possibly a NumPy-style "name : type" header line
            numpy_match = _NUMPY_ARG_NAME_RE.match(raw_line)
            if numpy_match and raw_line.strip()[0].isalpha() and not raw_line.startswith(" "):
                _flush()
                current_name = numpy_match.group("name")
                current_desc = []
            elif current_name:
                current_desc.append(raw_line.strip())
    _flush()
    return summary, param_docs


def _build_parameters(func, param_docs: dict[str, str]) -> tuple[ParamSpec, ...]:
    sig = inspect.signature(func)
    params: list[ParamSpec] = []
    for p in sig.parameters.values():
        if p.name == "self":
            continue
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            # *args / **kwargs can't be represented in a structured tool
            # call schema — skip them; the method simply won't accept
            # extra positional/keyword args through the tool interface.
            continue
        annotation = p.annotation if p.annotation is not inspect.Parameter.empty else str
        has_default = p.default is not inspect.Parameter.empty
        params.append(
            ParamSpec(
                name=p.name,
                annotation=annotation,
                required=not has_default,
                default=p.default if has_default else _MISSING,
                description=param_docs.get(p.name),
            )
        )
    return tuple(params)


def discover_methods(
    cls: type,
    *,
    visibility: frozenset[Visibility] = frozenset({"public"}),
    include: frozenset[str] | None = None,
    exclude: frozenset[str] | None = None,
    expose_properties: bool = False,
) -> list[MethodInfo]:
    """
    Inspects `cls.__dict__` (not inherited members, to avoid accidentally
    exposing object/base-class internals) and returns eligible methods.
    """
    unknown = visibility - _ALL_VISIBILITIES
    if unknown:
        raise ValueError(f"Unknown visibility level(s): {sorted(unknown)}")

    include_set = set(include or ())
    exclude_set = set(exclude or ())
    owner_name = cls.__name__

    results: list[MethodInfo] = []

    for name, member in list(cls.__dict__.items()):
        is_property = isinstance(member, property)
        is_plain_function = inspect.isfunction(member)

        if not is_property and not is_plain_function:
            continue
        if is_property and not expose_properties:
            continue
        if is_property and member.fget is None:
            continue

        vis = classify_visibility(name, owner_name)
        if vis is None:
            continue  # special method: never eligible

        if include_set:
            if name not in include_set:
                continue
        else:
            if vis not in visibility:
                continue
        if name in exclude_set:
            continue

        target = member.fget if is_property else member
        doc_summary, param_docs = parse_docstring(target.__doc__)
        parameters = () if is_property else _build_parameters(target, param_docs)

        results.append(
            MethodInfo(
                name=name,
                visibility=vis,
                is_property=is_property,
                is_coroutine=inspect.iscoroutinefunction(target),
                doc_summary=doc_summary or f"Performs the '{name}' operation.",
                parameters=parameters,
            )
        )

    return results


def class_summary(cls: type) -> str:
    summary, _ = parse_docstring(cls.__doc__)
    return summary
