from uuid import UUID

from sqlmodel import Field, SQLModel


class GetProduct(SQLModel):
    product_id: UUID


class CreateProduct(SQLModel):
    name: str
    description: str = ""
    sku: str
    price: float = Field(ge=0.0)
    stock: int = Field(ge=0, default=0)


class UpdateProduct(SQLModel):
    name: str | None = Field(default=None)
    description: str | None = Field(default=None)
    sku: str | None = Field(default=None)
    price: float | None = Field(default=None, ge=0.0)
    stock: int | None = Field(default=None, ge=0)


class AdjustStock(SQLModel):
    product_id: UUID
    quantity: int
    reason: str = ""
