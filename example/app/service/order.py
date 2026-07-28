from uuid import UUID

from app.exception import (
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.service.resource.repository import OrderRepository
from app.types.order import CreateOrder, GetOrder, UpdateOrder


class OrderService:

    def __init__(self, repo: OrderRepository) -> None:
        self.__repo = repo

    async def get_order(self, data: GetOrder):
        order = self.__repo.get(data.order_id)
        if order is None:
            raise NotFoundException("Order", data.order_id)
        return order

    async def create_order(self, data: CreateOrder):
        if data.quantity < 1:
            raise ValidationException("Quantity must be at least 1", field="quantity")
        return self.__repo.create(data)

    async def update_order(self, data: UpdateOrder):
        order = self.__repo.get(data.order_id)
        if order is None:
            raise NotFoundException("Order", data.order_id)
        if order.status in ("shipped", "delivered", "cancelled"):
            raise ConflictException(
                f"Cannot update order in '{order.status}' status",
                detail={"order_id": str(data.order_id), "current_status": order.status},
            )
        fields = data.model_dump(exclude_unset=True, exclude={"order_id"})
        return self.__repo.update(data.order_id, fields)

    async def cancel_order(self, data: GetOrder):
        order = self.__repo.get(data.order_id)
        if order is None:
            raise NotFoundException("Order", data.order_id)
        if order.status == "cancelled":
            raise ConflictException("Order is already cancelled")
        return self.__repo.update_status(data.order_id, "cancelled")

    async def list_orders(self, user_id: UUID | None = None):
        if user_id:
            return self.__repo.list_by_user(user_id)
        return self.__repo.list_all()

    async def delete_order(self, data: GetOrder):
        self.__repo.get_or_raise(data.order_id, "Order")
        self.__repo.delete(data.order_id)
        return {"deleted": True}
