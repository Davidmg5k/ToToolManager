from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from app import get_session, engine
from app.controller.inventory import InventoryController
from app.service import ProductRepository
from app.types.inventory import AdjustStock, CreateProduct, UpdateProduct

inventory_router = APIRouter(prefix="/api/inventory", tags=["api", "inventory"])


def _get_controller(session: Annotated[Session, Depends(get_session)]):
    return InventoryController(ProductRepository(session))


@inventory_router.get("/")
async def list_products(controller: Annotated[InventoryController, Depends(_get_controller)]):
    return await controller.list_products()


@inventory_router.get("/low-stock")
async def get_low_stock(
    controller: Annotated[InventoryController, Depends(_get_controller)],
    threshold: int = Query(default=10, ge=0),
):
    return await controller.get_low_stock(threshold)


@inventory_router.get("/{product_id}")
async def get_product(
    product_id: UUID,
    controller: Annotated[InventoryController, Depends(_get_controller)],
):
    return await controller.get_product(product_id)


@inventory_router.post("/")
async def create_product(request: Request):
    form = await request.form()
    data = CreateProduct(
        name=form.get("name", ""),
        sku=form.get("sku", ""),
        price=float(form.get("price", 0)),
        stock=int(form.get("stock", 0)),
        description=form.get("description", ""),
    )
    with Session(engine) as session:
        ctrl = InventoryController(ProductRepository(session))
        return await ctrl.create_product(data)


@inventory_router.patch("/{product_id}")
async def update_product(
    product_id: UUID,
    data: UpdateProduct,
    controller: Annotated[InventoryController, Depends(_get_controller)],
):
    return await controller.update_product(product_id, data)


@inventory_router.delete("/{product_id}")
async def delete_product(
    product_id: UUID, controller: Annotated[InventoryController, Depends(_get_controller)]
):
    return await controller.delete_product(product_id)


@inventory_router.post("/adjust-stock")
async def adjust_stock(
    data: AdjustStock,
    controller: Annotated[InventoryController, Depends(_get_controller)],
):
    return await controller.adjust_stock(data)