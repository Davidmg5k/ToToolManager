from uuid import UUID

from sqlmodel import Field, SQLModel
from pydantic import EmailStr


class GetUser(SQLModel):
    user_id: UUID

class CreateUser(SQLModel):
    user_name: str
    email: EmailStr
    password: str


class UpdateUser(SQLModel):
    user_name: str | None = Field(default=None)
    email: EmailStr | None = Field(default=None)
    password: str | None = Field(default=None)
