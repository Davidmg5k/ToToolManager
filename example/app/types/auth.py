from uuid import UUID

from sqlmodel import SQLModel


class LoginRequest(SQLModel):
    email: str
    password: str


class TokenResponse(SQLModel):
    user_id: UUID
    access_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(SQLModel):
    refresh_token: str
