from uuid import UUID

from app.exception import (
    NotificationDeliveryException,
    NotFoundException,
    ValidationException,
)
from app.service.resource.repository import NotificationRepository
from app.types.notification import (
    CreateNotification,
    GetNotification,
    NotificationChannel,
    NotificationStatus,
    UpdateNotification,
)


class NotificationService:

    def __init__(self, repo: NotificationRepository) -> None:
        self.__repo = repo

    async def get_notification(self, data: GetNotification):
        notification = self.__repo.get(data.notification_id)
        if notification is None:
            raise NotFoundException("Notification", data.notification_id)
        return notification

    async def create_notification(self, data: CreateNotification):
        if not data.recipient:
            raise ValidationException("Recipient is required", field="recipient")
        notification = self.__repo.create(data)
        sent = await self._send_notification(notification)
        return sent

    async def update_notification(self, data: UpdateNotification):
        self.__repo.get_or_raise(data.notification_id, "Notification")
        fields = data.model_dump(exclude_unset=True, exclude={"notification_id"})
        return self.__repo.update(data.notification_id, fields)

    async def resend_notification(self, data: GetNotification):
        notification = self.__repo.get(data.notification_id)
        if notification is None:
            raise NotFoundException("Notification", data.notification_id)
        sent = await self._send_notification(notification)
        return sent

    async def list_notifications(self, user_id: UUID | None = None):
        if user_id:
            return self.__repo.list_by_user(user_id)
        return self.__repo.list_all()

    async def _send_notification(self, notification) -> object:
        channel = notification.channel
        recipient = notification.recipient
        try:
            if channel == NotificationChannel.EMAIL:
                await self._send_email(recipient, notification)
            elif channel == NotificationChannel.SMS:
                await self._send_sms(recipient, notification)
            elif channel == NotificationChannel.PUSH:
                await self._send_push(recipient, notification)
            else:
                raise ValidationException(f"Unsupported channel: {channel}", field="channel")

            self.__repo.update_status(notification.notification_id, NotificationStatus.SENT)
            notification.status = NotificationStatus.SENT
            return notification
        except NotificationDeliveryException:
            self.__repo.update_status(notification.notification_id, NotificationStatus.FAILED)
            notification.status = NotificationStatus.FAILED
            return notification

    async def _send_email(self, recipient: str, notification) -> None:
        print(f"[EMAIL] To: {recipient} | Subject: {notification.subject}")

    async def _send_sms(self, recipient: str, notification) -> None:
        print(f"[SMS] To: {recipient} | Body: {notification.body}")

    async def _send_push(self, recipient: str, notification) -> None:
        print(f"[PUSH] To: {recipient} | Body: {notification.body}")

    async def delete_notification(self, data: GetNotification):
        self.__repo.get_or_raise(data.notification_id, "Notification")
        self.__repo.delete(data.notification_id)
        return {"deleted": True}
