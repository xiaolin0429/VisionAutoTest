from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, create_engine

from app.core.config import get_settings


def backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_alembic_config(*, database_url: str | None = None) -> Config:
    settings = get_settings()
    config = Config(str(backend_root() / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root() / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url or settings.database_url)
    return config


def upgrade_database(*, database_url: str | None = None, revision: str = "head") -> None:
    command.upgrade(get_alembic_config(database_url=database_url), revision)


def downgrade_database(*, database_url: str | None = None, revision: str = "base") -> None:
    command.downgrade(get_alembic_config(database_url=database_url), revision)


def reset_database_schema(*, database_url: str | None = None) -> None:
    settings = get_settings()
    url = database_url or settings.database_url
    engine = create_engine(url, future=True, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            metadata = MetaData()
            metadata.reflect(bind=connection)
            if metadata.tables:
                metadata.drop_all(bind=connection)
    finally:
        engine.dispose()
