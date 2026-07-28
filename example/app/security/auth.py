from uuid import UUID

from fastapi import Request, HTTPException
from sqlmodel import Session

from app import engine
from app.model import User


def get_current_user(request: Request) -> User | None:
    """Extract user from session cookie."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    try:
        uid = UUID(user_id)
    except ValueError:
        return None
    with Session(engine) as session:
        return session.get(User, uid)


def require_admin(request: Request) -> User:
    """Raise redirect to login if not authenticated."""
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    return user
