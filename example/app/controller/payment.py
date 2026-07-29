from uuid import UUID

from app.service import PaymentService, PaymentRepository, OrderRepository
from app.types.payment import CreatePayment, GetPayment, UpdatePayment


class PaymentController:

    def __init__(self, repo: PaymentRepository, order_repo: OrderRepository) -> None:
        self.__service = PaymentService(repo, order_repo)

    async def get_payment(self, payment_id: UUID):
        return await self.__service.get_payment(GetPayment(payment_id=payment_id))

    async def create_payment(self, data: CreatePayment):
        return await self.__service.create_payment(data)

    async def update_payment(self, payment_id: UUID, data: UpdatePayment):
        return await self.__service.update_payment(payment_id, data)

    async def refund_payment(self, payment_id: UUID):
        return await self.__service.refund_payment(GetPayment(payment_id=payment_id))

    async def list_payments(self, order_id: UUID | None = None):
        return await self.__service.list_payments(order_id)

    async def delete_payment(self, payment_id: UUID):
        return await self.__service.delete_payment(GetPayment(payment_id=payment_id))
