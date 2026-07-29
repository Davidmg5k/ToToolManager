from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from app import get_session, engine
from app.controller.order import OrderController
from app.response import ok, created, no_content
from app.service import OrderRepository
from app.types.order import CreateOrder, UpdateOrder

order_router = APIRouter(prefix="/api/order", tags=["api", "order"])


def _get_controller(session: Annotated[Session, Depends(get_session)]):
    return OrderController(OrderRepository(session))


@order_router.get("/")
async def list_orders(
    controller: Annotated[OrderController, Depends(_get_controller)],
    user_id: UUID | None = Query(default=None),
):
    orders = await controller.list_orders(user_id)
    return ok([o.model_dump(mode="json") for o in orders])


@order_router.get("/{order_id}")
async def get_order(
    order_id: UUID,
    controller: Annotated[OrderController, Depends(_get_controller)],
):
    order = await controller.get_order(order_id)
    return ok(order.model_dump(mode="json"))


@order_router.post("/")
async def create_order(request: Request):
    form = await request.form()
    data = CreateOrder(
        user_id=UUID(form.get("user_id", "")),
        product_name=form.get("product_name", ""),
        quantity=int(form.get("quantity", 1)),
        unit_price=float(form.get("unit_price", 0)),
    )
    with Session(engine) as session:
        ctrl = OrderController(OrderRepository(session))
        order = await ctrl.create_order(data)
        return created(order.model_dump(mode="json"))


@order_router.patch("/{order_id}")
async def update_order(
    order_id: UUID,
    data: UpdateOrder,
    controller: Annotated[OrderController, Depends(_get_controller)],
):
    order = await controller.update_order(order_id, data)
    return ok(order.model_dump(mode="json"))


@order_router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: UUID,
    controller: Annotated[OrderController, Depends(_get_controller)],
):
    order = await controller.cancel_order(order_id)
    return ok(order.model_dump(mode="json"))


@order_router.delete("/{order_id}")
async def delete_order(order_id: UUID, controller: Annotated[OrderController, Depends(_get_controller)]):
    await controller.delete_order(order_id)
    return no_content()

