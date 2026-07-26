from uuid import UUID

from app.exception import (
    InsufficientStockException,
    NotFoundException,
    ValidationException,
)
from app.service.resource.repository import ProductRepository
from app.types.inventory import AdjustStock, CreateProduct, GetProduct, UpdateProduct


class InventoryService:

    def __init__(self, repo: ProductRepository) -> None:
        self.__repo = repo

    async def get_product(self, data: GetProduct):
        product = self.__repo.get(data.product_id)
        if product is None:
            raise NotFoundException("Product", data.product_id)
        return product

    async def create_product(self, data: CreateProduct):
        if data.stock < 0:
            raise ValidationException("Initial stock cannot be negative", field="stock")
        if data.price < 0:
            raise ValidationException("Price cannot be negative", field="price")
        return self.__repo.create(data)

    async def update_product(self, data: UpdateProduct):
        self.__repo.get_or_raise(data.product_id, "Product")
        fields = data.model_dump(exclude_unset=True, exclude={"product_id"})
        return self.__repo.update(data.product_id, fields)

    async def delete_product(self, data: GetProduct):
        self.__repo.get_or_raise(data.product_id, "Product")
        self.__repo.delete(data.product_id)
        return {"deleted": True}

    async def adjust_stock(self, data: AdjustStock):
        product = self.__repo.get(data.product_id)
        if product is None:
            raise NotFoundException("Product", data.product_id)
        current_stock = product.stock
        new_stock = current_stock + data.quantity
        if new_stock < 0:
            raise InsufficientStockException(
                data.product_id, requested=abs(data.quantity), available=current_stock
            )
        return self.__repo.update_stock(data.product_id, new_stock)

    async def get_low_stock(self, threshold: int = 10):
        return self.__repo.list_below_stock(threshold)

    async def list_products(self):
        return self.__repo.list_all()
