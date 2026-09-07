"""Base for all to_tool_manager exceptions.

All package exceptions inherit from TTMError to allow
generic catching and subtype discrimination.
"""


class TTMError(Exception):
    """Base for all to_tool_manager exceptions."""
