from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from app import get_session, engine
from app.controller.payment import PaymentController
from app.response import ok, created, no_content
from app.service import PaymentRepository, OrderRepository
from app.types.payment import CreatePayment, UpdatePayment

payment_router = APIRouter(prefix="/api/payment", tags=["api", "payment"])


def _get_controller(session: Annotated[Session, Depends(get_session)]):
    return PaymentController(PaymentRepository(session), OrderRepository(session))


@payment_router.get("/")
async def list_payments(
    controller: Annotated[PaymentController, Depends(_get_controller)],
    order_id: UUID | None = Query(default=None),
):
    payments = await controller.list_payments(order_id)
    return ok([p.model_dump(mode="json") for p in payments])


@payment_router.get("/{payment_id}")
async def get_payment(
    payment_id: UUID,
    controller: Annotated[PaymentController, Depends(_get_controller)],
):
    payment = await controller.get_payment(payment_id)
    return ok(payment.model_dump(mode="json"))


@payment_router.post("/")
async def create_payment(request: Request):
    form = await request.form()
    data = CreatePayment(
        order_id=UUID(form.get("order_id", "")),
        amount=float(form.get("amount", 0)),
        method=form.get("method", "credit_card"),
    )
    with Session(engine) as session:
        ctrl = PaymentController(PaymentRepository(session), OrderRepository(session))
        payment = await ctrl.create_payment(data)
        return created(payment.model_dump(mode="json"))


@payment_router.patch("/{payment_id}")
async def update_payment(
    payment_id: UUID,
    data: UpdatePayment,
    controller: Annotated[PaymentController, Depends(_get_controller)],
):
    payment = await controller.update_payment(payment_id, data)
    return ok(payment.model_dump(mode="json"))


@payment_router.post("/{payment_id}/refund")
async def refund_payment(
    payment_id: UUID,
    controller: Annotated[PaymentController, Depends(_get_controller)],
):
    payment = await controller.refund_payment(payment_id)
    return ok(payment.model_dump(mode="json"))


@payment_router.delete("/{payment_id}")
async def delete_payment(payment_id: UUID, controller: Annotated[PaymentController, Depends(_get_controller)]):
    await controller.delete_payment(payment_id)
    return no_content()

