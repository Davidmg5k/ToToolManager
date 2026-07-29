from typing import Any, Callable
from uuid import UUID

from pydantic import BaseModel

from to_tool_manager.core.types import ToolResponse
from to_tool_manager.security.middleware import Middleware, ToolMiddleware


class SensitiveFieldMiddlewareAI(Middleware):

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        response: ToolResponse = await func(*args, **kw)
        if response.error is not None:
            return response
        return self._sanitize(response)

    def _get_uuid_field_names(self, model: BaseModel) -> set[str]:
        return {
            name
            for name, field in model.model_fields.items()
            if field.annotation is UUID or field.annotation is UUID | None
        }

    def _sanitize(self, data: ToolResponse) -> ToolResponse:
        return ToolResponse(content=self._sanitize_content(data.content))

    def _sanitize_content(self, data: Any) -> Any:
        if isinstance(data, BaseModel):
            uuid_fields = self._get_uuid_field_names(data)
            return self._sanitize_content(data.model_dump(exclude=uuid_fields))
        if isinstance(data, dict):
            return {
                k: self._sanitize_content(v)
                for k, v in data.items()
                if not isinstance(v, UUID)
            }
        if isinstance(data, list):
            return [self._sanitize_content(item) for item in data if not isinstance(item, UUID)]
        return data


class RemoverPasswordsMiddlewareAI(ToolMiddleware):

    async def dispatch(self, func: Callable[..., Any], /, *args: Any, **kw: Any) -> Any:
        response = await func(*args, **kw)
        if response.error is not None:
            return response
        return self._sanitize(response)

    def _sanitize(self, data: ToolResponse) -> ToolResponse:
        return ToolResponse(content=self._sanitize_content(data.content))

    def _sanitize_content(self, data: Any) -> Any:
        if isinstance(data, BaseModel):
            return self._sanitize_content(data.model_dump())
        if isinstance(data, dict):
            return {
                k: self._sanitize_content(v)
                for k, v in data.items()
                if k != "password"
            }
        if isinstance(data, list):
            return [self._sanitize_content(item) for item in data]
        return data
