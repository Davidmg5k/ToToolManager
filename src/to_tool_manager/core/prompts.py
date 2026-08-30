"""
Layered prompt building. Every default block is generic (mentions no
concrete domain like "Order" or "User") and is generated dynamically
from whatever Services and Modules are actually registered. A programmer
can EXTEND it with their own text (default) or OVERRIDE it entirely.

All default prompt text is in English by design (the library is meant
to ship English defaults regardless of the host application's locale;
callers can pass their own `custom` text in any language).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Sequence
from to_tool_manager.core.contracts import OPERATIONS_CONTRACT


if TYPE_CHECKING:
    from to_tool_manager.core.module import Module
    from to_tool_manager.core.service import Service

Mode = Literal["extend", "override"]

_DEFAULT_BEGIN = "<!-- DEFAULT:BEGIN -->"
_DEFAULT_END = "<!-- DEFAULT:END -->"
_USER_BEGIN = "<!-- USER:BEGIN -->"
_USER_END = "<!-- USER:END -->"


DEFAULT_SYSTEM_PROMPT_TEMPLATE = """\
{DEFAULT_BEGIN}
You are an assistant with access to tools. Each tool corresponds to a
Service or Module (sub-agent) and accepts a single `operations`
argument: a list of {{"method": <name>, "args": {{...}}}} objects.
Call a tool ONCE with every operation you need -- never call it
multiple times.

{operations_contract}

Example: {{"operations": [{{"id": "s1", "method": "create_user",
"args": {{"user_name": "...", "email": "..."}}}},
{{"method": "list_users", "args": {{}},
"when": {{"op": "s1", "outcome": "error"}}}}]}}

Available tools:
{services_overview}

Read each tool's own description for its operations and arguments.

Guidelines:
- Only use information returned by tools; never invent data.
- For multi-service requests, call each tool with all needed operations
  and combine results into a single answer.
- Each operation result has "success" + "result"|"error"; a batch call
  can mix successes and failures.
- Retry with different args only if the error is retryable; if the
  resource already exists or is not found, accept and move on.
- Ask only for strictly necessary information when the request is
  ambiguous.
- Never expose internal implementation details.
{DEFAULT_END}"""

DEFAULT_INSTRUCTIONS_TEMPLATE = """\
{DEFAULT_BEGIN}
When a request implies multiple independent operations (e.g. creating
several records, or performing actions across more than one service),
execute all tool calls before writing your final answer, running
independent calls in parallel where possible.

Error handling -- hard rules:
- Do not retry a tool call with the exact same arguments after it fails.
- If a tool reports that a resource already exists or is not needed,
  accept that as a completed/no-op outcome and move on to the remaining
  tasks; do not treat it as a blocking failure.
- If a tool reports a resource was not found, record that and continue
  with the rest of the request.
- Never loop indefinitely retrying failed operations.

Once every requested operation has been attempted, stop calling tools
and produce a final, conversational summary:
- What succeeded
- What failed or was skipped, and why
- If the user asked to see/list something, mention the key details
  naturally (e.g. names, emails) without exposing internal IDs or
  technical field names. Do NOT dump raw data tables.
{DEFAULT_END}"""


def _services_overview(services: Sequence[Service | Module]) -> str:
    lines = []
    for item in services:
        from to_tool_manager.core.module import Module

        if isinstance(item, Module):
            desc = item.description.strip() if item.description else f"Module grouping {len(item.services)} services."
            lines.append(f"- **{item.name}** (Module): {desc}")
        else:
            desc = item.description.strip() if item.description else f"Service for {item.name} management."
            lines.append(f"- **{item.name}**: {desc}")
    return "\n".join(lines) if lines else "- (no services registered)"


def _merge(default_block: str, custom: str | None, mode: Mode) -> str:
    if custom is None:
        return default_block
    custom = custom.strip()
    if mode == "override":
        return custom
    return f"{default_block}\n\n{_USER_BEGIN}\n{custom}\n{_USER_END}"


def build_system_prompt(
    services: Sequence[Service | Module],
    *,
    custom: str | None = None,
    mode: Mode = "extend",
) -> str:
    default_block = DEFAULT_SYSTEM_PROMPT_TEMPLATE.format(
        DEFAULT_BEGIN=_DEFAULT_BEGIN,
        DEFAULT_END=_DEFAULT_END,
        services_overview=_services_overview(services),
        operations_contract=OPERATIONS_CONTRACT,
    )
    return _merge(default_block, custom, mode)


def build_instructions(*, custom: str | None = None, mode: Mode = "extend") -> str:
    default_block = DEFAULT_INSTRUCTIONS_TEMPLATE.format(
        DEFAULT_BEGIN=_DEFAULT_BEGIN, DEFAULT_END=_DEFAULT_END
    )
    return _merge(default_block, custom, mode)


def build_service_description(service: Service, *, custom: str | None = None, mode: Mode = "extend") -> str:
    """Per-service instructions/description, for adapters that support
    per-toolset instructions (e.g. pydantic-ai's FunctionToolset)."""
    default_block = (
        f"{_DEFAULT_BEGIN}\n"
        f"Provides {service.name} management capabilities.\n"
        f"{_DEFAULT_END}"
    )
    base = service.description.strip() if service.description else default_block
    return _merge(base, custom, mode)
