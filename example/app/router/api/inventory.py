from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from app import get_session, engine
from app.controller.inventory import InventoryController
from app.response import ok, created, no_content
from app.service import ProductRepository
from app.types.inventory import AdjustStock, CreateProduct, UpdateProduct

inventory_router = APIRouter(prefix="/api/inventory", tags=["api", "inventory"])


def _get_controller(session: Annotated[Session, Depends(get_session)]):
    return InventoryController(ProductRepository(session))


@inventory_router.get("/")
async def list_products(controller: Annotated[InventoryController, Depends(_get_controller)]):
    products = await controller.list_products()
    return ok([p.model_dump(mode="json") for p in products])


@inventory_router.get("/low-stock")
async def get_low_stock(
    controller: Annotated[InventoryController, Depends(_get_controller)],
    threshold: int = Query(default=10, ge=0),
):
    products = await controller.get_low_stock(threshold)
    return ok([p.model_dump(mode="json") for p in products])


@inventory_router.get("/{product_id}")
async def get_product(
    product_id: UUID,
    controller: Annotated[InventoryController, Depends(_get_controller)],
):
    product = await controller.get_product(product_id)
    return ok(product.model_dump(mode="json"))


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
        product = await ctrl.create_product(data)
        return created(product.model_dump(mode="json"))


@inventory_router.patch("/{product_id}")
async def update_product(
    product_id: UUID,
    data: UpdateProduct,
    controller: Annotated[InventoryController, Depends(_get_controller)],
):
    product = await controller.update_product(product_id, data)
    return ok(product.model_dump(mode="json"))


@inventory_router.delete("/{product_id}")
async def delete_product(
    product_id: UUID, controller: Annotated[InventoryController, Depends(_get_controller)]
):
    await controller.delete_product(product_id)
    return no_content()


@inventory_router.post("/adjust-stock")
async def adjust_stock(
    data: AdjustStock,
    controller: Annotated[InventoryController, Depends(_get_controller)],
):
    product = await controller.adjust_stock(data)
    return ok(product.model_dump(mode="json"))

