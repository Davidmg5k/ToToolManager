"""
Centralized contracts and constants for tool descriptions.

Single source of truth for the operations contract text used across
manager.py, module.py, and prompts.py. Keeping these here prevents
drift between the two dispatch paths (Service-level and Module-level)
and ensures the LLM receives consistent instructions regardless of
which boundary the tool lives behind.
"""
from __future__ import annotations

OPERATIONS_CONTRACT = (
    "Each operation: {{\"method\": <name>, \"args\": {{\"<param_name>\": <value>, ...}}}}. "
    "The \"args\" keys MUST match the parameter names listed in each operation description. "
    "Optional \"id\" and \"when\" for sequencing."
)

EMPTY_OPERATIONS_ERROR = (
    "`operations` must be a non-empty list of "
    '{"method": ..., "args": {...}} objects.'
)

INVALID_OPERATION_ERROR = "Each operation must be an object with 'method' and 'args'."

INVALID_ARGS_ERROR = "'args' must be an object."
