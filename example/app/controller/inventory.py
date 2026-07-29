from uuid import UUID

from app.service import InventoryService, ProductRepository
from app.types.inventory import AdjustStock, CreateProduct, GetProduct, UpdateProduct


class InventoryController:

    def __init__(self, repo: ProductRepository) -> None:
        self.__service = InventoryService(repo)

    async def get_product(self, product_id: UUID):
        return await self.__service.get_product(GetProduct(product_id=product_id))

    async def create_product(self, data: CreateProduct):
        return await self.__service.create_product(data)

    async def update_product(self, product_id: UUID, data: UpdateProduct):
        return await self.__service.update_product(product_id, data)

    async def delete_product(self, product_id: UUID):
        return await self.__service.delete_product(GetProduct(product_id=product_id))

    async def adjust_stock(self, data: AdjustStock):
        return await self.__service.adjust_stock(data)

    async def get_low_stock(self, threshold: int = 10):
        return await self.__service.get_low_stock(threshold)

    async def list_products(self):
        return await self.__service.list_products()
