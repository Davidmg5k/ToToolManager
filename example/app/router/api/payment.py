from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from app import get_session, engine
from app.controller.payment import PaymentController
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
    return await controller.list_payments(order_id)


@payment_router.get("/{payment_id}")
async def get_payment(
    payment_id: UUID,
    controller: Annotated[PaymentController, Depends(_get_controller)],
):
    return await controller.get_payment(payment_id)


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
        return await ctrl.create_payment(data)


@payment_router.patch("/{payment_id}")
async def update_payment(
    payment_id: UUID,
    data: UpdatePayment,
    controller: Annotated[PaymentController, Depends(_get_controller)],
):
    return await controller.update_payment(payment_id, data)


@payment_router.post("/{payment_id}/refund")
async def refund_payment(
    payment_id: UUID,
    controller: Annotated[PaymentController, Depends(_get_controller)],
):
    return await controller.refund_payment(payment_id)