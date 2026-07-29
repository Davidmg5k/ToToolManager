from uuid import UUID

from app.exception import (
    AlreadyExistsException,
    NotFoundException,
)
from app.service.resource.repository import UserRepository
from app.types.user import CreateUser, GetUser, UpdateUser


class UserService:

    def __init__(self, repo: UserRepository) -> None:
        self.__repo = repo

    async def get_user(self, data: GetUser):
        user = self.__repo.get(data.user_id)
        if user is None:
            raise NotFoundException("User", data.user_id)
        return user

    async def create_user(self, data: CreateUser):
        existing = self.__repo.find_by_email(data.email)
        if existing:
            raise AlreadyExistsException("User", "email", data.email)
        return self.__repo.create(data)

    async def update_user(self, user_id: UUID, data: UpdateUser):
        self.__repo.get_or_raise(user_id, "User")
        fields = data.model_dump(exclude_unset=True)
        return self.__repo.update(user_id, fields)

    async def delete_user(self, data: GetUser):
        self.__repo.get_or_raise(data.user_id, "User")
        self.__repo.delete(data.user_id)
        return {"deleted": True}

    async def list_users(self):
        return self.__repo.list_all()
