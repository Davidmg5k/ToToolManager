from typing import Any, Callable
from uuid import UUID

from pydantic import BaseModel

from to_tool_manager.security.middleware import Middleware, ToolMiddleware


class SensitiveFieldMiddlewareAI(Middleware):

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        response = await func(*args, **kw)
        return self._sanitize(response)

    def _get_uuid_field_names(self, model: BaseModel) -> set[str]:
        return {
            name
            for name, field in model.model_fields.items()
            if field.annotation is UUID or field.annotation is UUID | None
        }

    def _sanitize(self, data: Any) -> Any:
        if isinstance(data, BaseModel):
            uuid_fields = self._get_uuid_field_names(data)
            return data.model_dump(exclude=uuid_fields)
        if isinstance(data, list):
            return [self._sanitize(item) for item in data]
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if not isinstance(v, UUID)}
        return data

class RemoverPasswordsMiddlewareAI(ToolMiddleware):

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        response = await func(*args, **kw)
        return self._sanitize(response)

    def _sanitize(self, data: Any) -> Any:
        if isinstance(data, BaseModel):
            return data.model_dump(exclude={"password"})
        if isinstance(data, list):
            return [self._sanitize(item) for item in data]
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if k != "password"}
        return data