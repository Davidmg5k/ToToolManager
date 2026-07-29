from uuid import UUID

from app.service import UserService, UserRepository
from app.types.user import CreateUser, GetUser, UpdateUser


class UserController:

    def __init__(self, repo: UserRepository) -> None:
        self.__service = UserService(repo)

    async def get_user(self, user_id: UUID):
        return await self.__service.get_user(GetUser(user_id=user_id))

    async def create_user(self, data: CreateUser):
        return await self.__service.create_user(data)

    async def update_user(self, user_id: UUID, data: UpdateUser):
        return await self.__service.update_user(user_id, data)

    async def delete_user(self, user_id: UUID):
        return await self.__service.delete_user(GetUser(user_id=user_id))

    async def list_users(self):
        return await self.__service.list_users()
