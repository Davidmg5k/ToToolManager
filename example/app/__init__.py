from pathlib import Path
from functools import lru_cache
from typing import Any, Generator
from uuid import uuid4

from sqlmodel import Session, SQLModel, select, create_engine

_DB_DIR = Path(__file__).parent.parent / "data"
_DB_PATH = _DB_DIR / "app.db"
_DATABASE_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(
    _DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    import app.model  # noqa: F401 — ensure all models are registered
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    # Enable WAL mode: allows concurrent reads while background tasks write.
    # Wrapped in try/except so a corrupted DB doesn't block all imports.
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            conn.commit()
    except Exception:
        pass


def get_session() -> Generator[Session, Any, None]:
    with Session(engine) as session:
        yield session


@lru_cache
def _ensure_initialized() -> None:
    init_db()


def get_db() -> Session:
    _ensure_initialized()
    return Session(engine)
