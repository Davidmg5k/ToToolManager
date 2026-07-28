from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from app import get_session, engine
from app.controller.notification import NotificationController
from app.service import NotificationRepository
from app.types.notification import CreateNotification, UpdateNotification

notification_router = APIRouter(prefix="/api/notification", tags=["api", "notification"])


def _get_controller(session: Annotated[Session, Depends(get_session)]):
    return NotificationController(NotificationRepository(session))


@notification_router.get("/")
async def list_notifications(
    controller: Annotated[NotificationController, Depends(_get_controller)],
    user_id: UUID | None = Query(default=None),
):
    return await controller.list_notifications(user_id)


@notification_router.get("/{notification_id}")
async def get_notification(
    notification_id: UUID,
    controller: Annotated[NotificationController, Depends(_get_controller)],
):
    return await controller.get_notification(notification_id)


@notification_router.post("/")
async def create_notification(request: Request):
    form = await request.form()
    data = CreateNotification(
        user_id=UUID(form.get("user_id", "")),
        channel=form.get("channel", "email"),
        subject=form.get("subject", ""),
        body=form.get("body", ""),
        recipient=form.get("recipient", ""),
    )
    with Session(engine) as session:
        ctrl = NotificationController(NotificationRepository(session))
        return await ctrl.create_notification(data)


@notification_router.patch("/{notification_id}")
async def update_notification(
    notification_id: UUID,
    data: UpdateNotification,
    controller: Annotated[NotificationController, Depends(_get_controller)],
):
    return await controller.update_notification(notification_id, data)


@notification_router.post("/{notification_id}/resend")
async def resend_notification(
    notification_id: UUID,
    controller: Annotated[NotificationController, Depends(_get_controller)],
):
    return await controller.resend_notification(notification_id)

@notification_router.delete("/{notification_id}")
async def delete_notification(notification_id: UUID, controller: Annotated[NotificationController, Depends(_get_controller)]):
    return await controller.delete_notification(notification_id)
