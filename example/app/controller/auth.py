from app.service import AuthService, UserRepository
from app.types.auth import LoginRequest, RefreshTokenRequest


class AuthController:

    def __init__(self, repo: UserRepository) -> None:
        self.__service = AuthService(repo)

    async def login(self, data: LoginRequest):
        return await self.__service.login(data)

    async def refresh_token(self, data: RefreshTokenRequest):
        return await self.__service.refresh_token(data)

    async def validate_token(self, token: str):
        return await self.__service.validate_token(token)
