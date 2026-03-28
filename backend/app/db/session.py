from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.security import hash_secret
from app.models import Base, User

settings = get_settings()


def _sqlite_connect_args() -> dict[str, bool]:
    if settings.database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(settings.database_url, future=True, connect_args=_sqlite_connect_args())
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
    settings.local_storage_path.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.username == settings.default_admin_username, User.is_deleted.is_(False)))
        if admin is None:
            db.add(
                User(
                    username=settings.default_admin_username,
                    display_name="Administrator",
                    password_hash=hash_secret(settings.default_admin_password),
                    status="active",
                )
            )
            db.commit()
