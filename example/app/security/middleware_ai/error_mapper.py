from typing import Any, Callable, Mapping, Type

from to_tool_manager import Middleware


class DomainErrorMappingMiddleware(Middleware):
    """Mapea excepciones de dominio a mensajes legibles para el LLM.

    Reemplaza al antiguo ErrorMap de la librería: en la API actual los
    middlewares viven en la capa de aplicación (example), no en la
    librería, y los tools devuelven el valor crudo del método.

    Precondition: error_map es un dict type[Exception] -> categoría
    Postcondition: si el tool lanza una excepción mapeada, devuelve un
    dict legible {"error": categoria, "message": ...}; si no está en el
    mapa, la excepción se relanza (errores de infraestructura propagan).
    """

    def __init__(
        self,
        error_map: Mapping[Type[Exception], str],
        retryable: set[Type[Exception]] | None = None,
    ) -> None:
        self.__error_map = dict(error_map)
        self.__retryable = set(retryable or ())

    @property
    def error_map(self) -> dict[Type[Exception], str]:
        """Returns a copy of the error map.

        Precondition: none
        Postcondition: returns a dict copy of the mapping
        """
        return dict(self.__error_map)

    @property
    def retryable(self) -> set[Type[Exception]]:
        """Returns the set of retryable exception types.

        Precondition: none
        Postcondition: returns a set copy
        """
        return set(self.__retryable)

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        try:
            return await func(*args, **kw)
        except Exception as exc:
            for exc_type, category in self.__error_map.items():
                if isinstance(exc, exc_type):
                    return {
                        "error": category,
                        "message": str(exc),
                        "retryable": any(isinstance(exc, r) for r in self.__retryable),
                    }
            raise