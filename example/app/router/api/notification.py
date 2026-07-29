from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from app import get_session, engine
from app.controller.notification import NotificationController
from app.response import ok, created, no_content
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
    notifications = await controller.list_notifications(user_id)
    return ok([n.model_dump(mode="json") for n in notifications])


@notification_router.get("/{notification_id}")
async def get_notification(
    notification_id: UUID,
    controller: Annotated[NotificationController, Depends(_get_controller)],
):
    notification = await controller.get_notification(notification_id)
    return ok(notification.model_dump(mode="json"))


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
        notification = await ctrl.create_notification(data)
        return created(notification.model_dump(mode="json"))


@notification_router.patch("/{notification_id}")
async def update_notification(
    notification_id: UUID,
    data: UpdateNotification,
    controller: Annotated[NotificationController, Depends(_get_controller)],
):
    notification = await controller.update_notification(notification_id, data)
    return ok(notification.model_dump(mode="json"))


@notification_router.post("/{notification_id}/resend")
async def resend_notification(
    notification_id: UUID,
    controller: Annotated[NotificationController, Depends(_get_controller)],
):
    notification = await controller.resend_notification(notification_id)
    return ok(notification.model_dump(mode="json"))


@notification_router.delete("/{notification_id}")
async def delete_notification(notification_id: UUID, controller: Annotated[NotificationController, Depends(_get_controller)]):
    await controller.delete_notification(notification_id)
    return no_content()

