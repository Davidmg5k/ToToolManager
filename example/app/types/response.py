from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | list[T] | None = None
    error: str | None = None
    detail: dict[str, Any] | None = None
