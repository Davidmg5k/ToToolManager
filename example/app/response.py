from typing import Any

from fastapi.responses import JSONResponse


def ok(data: Any = None, status: int = 200) -> JSONResponse:
    return JSONResponse(content={"success": True, "data": data}, status_code=status)


def created(data: Any = None) -> JSONResponse:
    return JSONResponse(content={"success": True, "data": data}, status_code=201)


def no_content() -> JSONResponse:
    return JSONResponse(content={"success": True}, status_code=200)


def error(message: str, detail: dict[str, Any] | None = None, status: int = 400) -> JSONResponse:
    return JSONResponse(
        content={"success": False, "error": message, "detail": detail},
        status_code=status,
    )
