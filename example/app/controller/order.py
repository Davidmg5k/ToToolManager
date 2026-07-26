from uuid import UUID

from app.service import OrderService, OrderRepository
from app.types.order import CreateOrder, GetOrder, UpdateOrder


class OrderController:

    def __init__(self, repo: OrderRepository) -> None:
        self.__service = OrderService(repo)

    async def get_order(self, order_id: UUID):
        return await self.__service.get_order(GetOrder(order_id=order_id))

    async def create_order(self, data: CreateOrder):
        return await self.__service.create_order(data)

    async def update_order(self, order_id: UUID, data: UpdateOrder):
        return await self.__service.update_order(
            UpdateOrder(order_id=order_id, **data.model_dump(exclude_unset=True))
        )

    async def cancel_order(self, order_id: UUID):
        return await self.__service.cancel_order(GetOrder(order_id=order_id))

    async def list_orders(self, user_id: UUID | None = None):
        return await self.__service.list_orders(user_id)
