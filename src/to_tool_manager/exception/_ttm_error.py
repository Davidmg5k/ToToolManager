"""Base para todas las excepciones de to_tool_manager.

Todas las excepciones del paquete heredan de TTMError para permitir
capture genérico y discriminación por subtipo.
"""


class TTMError(Exception):
    """Base para todas las excepciones de to_tool_manager."""
