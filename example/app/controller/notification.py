from uuid import UUID

from app.service import NotificationService, NotificationRepository
from app.types.notification import CreateNotification, GetNotification, UpdateNotification


class NotificationController:

    def __init__(self, repo: NotificationRepository) -> None:
        self.__service = NotificationService(repo)

    async def get_notification(self, notification_id: UUID):
        return await self.__service.get_notification(
            GetNotification(notification_id=notification_id)
        )

    async def create_notification(self, data: CreateNotification):
        return await self.__service.create_notification(data)

    async def update_notification(self, notification_id: UUID, data: UpdateNotification):
        return await self.__service.update_notification(
            UpdateNotification(notification_id=notification_id, **data.model_dump(exclude_unset=True))
        )

    async def resend_notification(self, notification_id: UUID):
        return await self.__service.resend_notification(
            GetNotification(notification_id=notification_id)
        )

    async def list_notifications(self, user_id: UUID | None = None):
        return await self.__service.list_notifications(user_id)
