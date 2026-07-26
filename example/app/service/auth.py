from app.exception import UnauthorizedException
from app.service.resource.repository import UserRepository
from app.types.auth import LoginRequest, RefreshTokenRequest, TokenResponse


class AuthService:

    def __init__(self, repo: UserRepository) -> None:
        self.__repo = repo

    async def login(self, data: LoginRequest):
        user = self.__repo.find_by_email(data.email)
        if user is None:
            raise UnauthorizedException("Invalid email or password")
        if user.password != data.password:
            raise UnauthorizedException("Invalid email or password")
        token = self.__generate_token(user)
        return TokenResponse(user_id=user.user_id, access_token=token)

    async def refresh_token(self, data: RefreshTokenRequest):
        payload = self.__decode_token(data.refresh_token)
        if payload is None:
            raise UnauthorizedException("Invalid or expired refresh token")
        from uuid import UUID

        user = self.__repo.get(UUID(payload.get("user_id")))
        if user is None:
            raise UnauthorizedException("User no longer exists")
        token = self.__generate_token(user)
        return TokenResponse(user_id=user.user_id, access_token=token)

    async def validate_token(self, token: str):
        payload = self.__decode_token(token)
        if payload is None:
            raise UnauthorizedException("Invalid or expired token")
        return payload

    def __generate_token(self, user) -> str:
        import base64
        import json

        payload = {"user_id": str(user.user_id), "email": user.email}
        return base64.b64encode(json.dumps(payload).encode()).decode()

    def __decode_token(self, token: str) -> dict | None:
        import base64
        import json

        try:
            return json.loads(base64.b64decode(token).decode())
        except Exception:
            return None
