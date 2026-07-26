from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app import get_session
from app.controller.auth import AuthController
from app.service import UserRepository
from app.types.auth import LoginRequest, RefreshTokenRequest

auth_router = APIRouter(prefix="/api/auth", tags=["api", "auth"])


def _get_controller(session: Annotated[Session, Depends(get_session)]):
    return AuthController(UserRepository(session))


@auth_router.post("/login")
async def login(request: Request):
    form = await request.form()
    email = form.get("email", "")
    password = form.get("password", "")
    from app import engine
    from sqlmodel import Session, select
    from app.model import User

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None or user.password != password:
            resp = JSONResponse(content={"error": "Invalid email or password"}, status_code=401)
            resp.headers["HX-Trigger"] = '{"showToast": {"message": "Invalid email or password", "type": "error"}}'
            return resp

        import base64, json
        token = base64.b64encode(json.dumps({"user_id": str(user.user_id), "email": user.email}).encode()).decode()

        resp = JSONResponse(content={"ok": True})
        resp.set_cookie("user_id", str(user.user_id), httponly=True, samesite="lax")
        resp.headers["HX-Redirect"] = "/admin/dashboard"
        return resp


@auth_router.post("/refresh")
async def refresh_token(
    data: RefreshTokenRequest,
    controller: Annotated[AuthController, Depends(_get_controller)],
):
    return await controller.refresh_token(data)


@auth_router.post("/logout")
async def logout():
    from fastapi.responses import Response
    resp = Response(status_code=200)
    resp.delete_cookie("user_id")
    resp.headers["HX-Redirect"] = "/"
    return resp