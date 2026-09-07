from typing import Any

from to_tool_manager.exception import DependencyNotSetError


class DinamicDepend:
    """Dynamic dependency for services."""

    def __init__(self):
        # Use object.__setattr__ directly to avoid recursion
        object.__setattr__(self, '_data', {})

    def __setattr__(self, name: str, value: Any) -> None:
        """Sets an attribute dynamically."""
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            data = object.__getattribute__(self, '_data')
            data[name] = value

    def __getattribute__(self, name: str) -> Any:
        """Gets an attribute dynamically."""
        # For internal attributes, use object.__getattribute__
        if name.startswith('_'):
            return object.__getattribute__(self, name)
        data = object.__getattribute__(self, '_data')
        if name in data:
            return data[name]
        raise DependencyNotSetError(name)

    def __hasattr__(self, name: str) -> bool:
        """Checks if an attribute exists."""
        if name.startswith('_'):
            return object.__getattribute__(self, name) is not None
        data = object.__getattribute__(self, '_data')
        return name in data
