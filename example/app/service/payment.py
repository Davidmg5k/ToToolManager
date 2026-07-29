from uuid import UUID

from app.exception import (
    ConflictException,
    NotFoundException,
    PaymentFailedException,
    ValidationException,
)
from app.service.resource.repository import OrderRepository, PaymentRepository
from app.types.payment import CreatePayment, GetPayment, PaymentStatus, UpdatePayment


class PaymentService:

    def __init__(self, repo: PaymentRepository, order_repo: OrderRepository) -> None:
        self.__repo = repo
        self.__order_repo = order_repo

    async def get_payment(self, data: GetPayment):
        payment = self.__repo.get(data.payment_id)
        if payment is None:
            raise NotFoundException("Payment", data.payment_id)
        return payment

    async def create_payment(self, data: CreatePayment):
        if data.amount <= 0:
            raise ValidationException("Payment amount must be positive", field="amount")
        order = self.__order_repo.get(data.order_id)
        if order is None:
            raise NotFoundException("Order", data.order_id)
        if order.status == "cancelled":
            raise ConflictException("Cannot pay for a cancelled order")

        payment = self.__repo.create(data)
        processed = await self._process_payment(payment)
        return processed

    async def update_payment(self, payment_id: UUID, data: UpdatePayment):
        payment = self.__repo.get(payment_id)
        if payment is None:
            raise NotFoundException("Payment", payment_id)
        if payment.status in (PaymentStatus.COMPLETED, PaymentStatus.REFUNDED):
            raise ConflictException(
                f"Cannot update payment in '{payment.status}' status"
            )
        fields = data.model_dump(exclude_unset=True)
        return self.__repo.update(payment_id, fields)

    async def refund_payment(self, data: GetPayment):
        payment = self.__repo.get(data.payment_id)
        if payment is None:
            raise NotFoundException("Payment", data.payment_id)
        if payment.status != PaymentStatus.COMPLETED:
            raise ConflictException("Only completed payments can be refunded")
        return self.__repo.update_status(data.payment_id, PaymentStatus.REFUNDED)

    async def list_payments(self, order_id: UUID | None = None):
        if order_id:
            return self.__repo.list_by_order(order_id)
        return self.__repo.list_all()

    async def _process_payment(self, payment) -> object:
        try:
            self.__repo.update_status(payment.payment_id, PaymentStatus.COMPLETED)
            payment.status = PaymentStatus.COMPLETED
            return payment
        except Exception as exc:
            self.__repo.update_status(payment.payment_id, PaymentStatus.FAILED)
            raise PaymentFailedException(
                f"Payment processing failed: {exc}", provider="mock_gateway"
            ) from exc

    async def delete_payment(self, data: GetPayment):
        self.__repo.get_or_raise(data.payment_id, "Payment")
        self.__repo.delete(data.payment_id)
        return {"deleted": True}
