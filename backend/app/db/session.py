from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def _connect_args() -> dict[str, bool]:
    if settings.database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(settings.database_url, future=True, connect_args=_connect_args(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def _ensure_sqlite_parent() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    sqlite_path = settings.database_url.split("///", maxsplit=1)[-1]
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    _ensure_sqlite_parent()
    from app.db.bootstrap import initialize_database

    initialize_database()
