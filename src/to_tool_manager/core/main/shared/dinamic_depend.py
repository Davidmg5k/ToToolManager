from typing import Any

from to_tool_manager.exception import DependencyNotSetError


class DinamicDepend:
    """Dependencia dinámica para servicios."""

    def __init__(self):
        # Usar object.__setattr__ directamente para evitar recursión
        object.__setattr__(self, '_data', {})

    def __setattr__(self, name: str, value: Any) -> None:
        """Establece un atributo dinámicamente."""
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            data = object.__getattribute__(self, '_data')
            data[name] = value

    def __getattribute__(self, name: str) -> Any:
        """Obtiene un atributo dinámicamente."""
        # Para atributos internos, usar object.__getattribute__
        if name.startswith('_'):
            return object.__getattribute__(self, name)
        data = object.__getattribute__(self, '_data')
        if name in data:
            return data[name]
        raise DependencyNotSetError(name)

    def __hasattr__(self, name: str) -> bool:
        """Verifica si existe un atributo."""
        if name.startswith('_'):
            return object.__getattribute__(self, name) is not None
        data = object.__getattribute__(self, '_data')
        return name in data
