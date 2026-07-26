from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app import get_session, engine
from app.controller.user import UserController
from app.service import UserRepository
from app.types.user import CreateUser, UpdateUser

user_router = APIRouter(prefix="/api/user", tags=["api", "user"])


def _get_controller(session: Annotated[Session, Depends(get_session)]):
    return UserController(UserRepository(session))


@user_router.get("/")
async def list_users(controller: Annotated[UserController, Depends(_get_controller)]):
    return await controller.list_users()


@user_router.get("/{user_id}")
async def get_user(user_id: UUID, controller: Annotated[UserController, Depends(_get_controller)]):
    return await controller.get_user(user_id)


@user_router.post("/")
async def create_user(request: Request):
    form = await request.form()
    data = CreateUser(
        user_name=form.get("user_name", ""),
        email=form.get("email", ""),
        password=form.get("password", ""),
    )
    with Session(engine) as session:
        ctrl = UserController(UserRepository(session))
        return await ctrl.create_user(data)


@user_router.patch("/{user_id}")
async def update_user(
    user_id: UUID,
    data: UpdateUser,
    controller: Annotated[UserController, Depends(_get_controller)],
):
    return await controller.update_user(user_id, data)


@user_router.delete("/{user_id}")
async def delete_user(user_id: UUID, controller: Annotated[UserController, Depends(_get_controller)]):
    return await controller.delete_user(user_id)