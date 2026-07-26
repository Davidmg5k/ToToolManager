from pathlib import Path
from functools import lru_cache
from typing import Any, Generator
from uuid import uuid4

from sqlmodel import Session, SQLModel, select, create_engine

_DB_DIR = Path(__file__).parent.parent / "data"
_DB_PATH = _DB_DIR / "app.db"
_DATABASE_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(_DATABASE_URL, echo=False)


def init_db() -> None:
    """Create the data directory and all tables."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def seed_admin() -> None:
    """Create default admin user if it doesn't exist."""
    from app.model import User

    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == "admin@ttm.com")).first()
        if existing is None:
            admin = User(
                user_id=uuid4(),
                user_name="Admin",
                email="admin@ttm.com",
                password="admin",
            )
            session.add(admin)
            session.commit()


def get_session() -> Generator[Session, Any, None]:
    """Yields a SQLModel session."""
    with Session(engine) as session:
        yield session


@lru_cache
def _ensure_initialized() -> None:
    init_db()


def get_db() -> Session:
    """Public accessor: initializes DB on first call, returns a session."""
    _ensure_initialized()
    return Session(engine)
