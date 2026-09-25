from typing import Any, Callable
from uuid import UUID

from pydantic import BaseModel

from to_tool_manager import Middleware, ToolMiddleware


class SensitiveFieldMiddlewareAI(Middleware):
    """Removes UUID fields/values from tool results before reaching the LLM.

    Precondition: func is the wrapped tool method (sync or async)
    Postcondition: returned value is sanitized (UUID fields and values removed)

    Esta migración elimina ToolResponse: el middleware opera directamente
    sobre el valor devuelto por el tool (BaseModel/dict/list), que es el
    contrato de la API actual (core.middleware.middleware.Middleware).
    """

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        result = await func(*args, **kw)
        return self._sanitize(result)

    def _get_uuid_field_names(self, model: BaseModel) -> set[str]:
        return {
            name
            for name, field in model.model_fields.items()
            if field.annotation is UUID or field.annotation is UUID | None
        }

    def _sanitize(self, data: Any) -> Any:
        if isinstance(data, BaseModel):
            uuid_fields = self._get_uuid_field_names(data)
            return self._sanitize(data.model_dump(exclude=uuid_fields))
        if isinstance(data, dict):
            return {
                k: self._sanitize(v)
                for k, v in data.items()
                if not isinstance(v, UUID)
            }
        if isinstance(data, list):
            return [self._sanitize(item) for item in data if not isinstance(item, UUID)]
        return data


class RemoverPasswordsMiddlewareAI(ToolMiddleware):
    """Removes password fields from tool results.

    Precondition: func is the wrapped tool method (sync or async)
    Postcondition: returned value is sanitized (password keys removed)
    """

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        result = await func(*args, **kw)
        return self._sanitize(result)

    def _sanitize(self, data: Any) -> Any:
        if isinstance(data, BaseModel):
            return self._sanitize(data.model_dump())
        if isinstance(data, dict):
            return {
                k: self._sanitize(v)
                for k, v in data.items()
                if k != "password"
            }
        if isinstance(data, list):
            return [self._sanitize(item) for item in data]
        return data