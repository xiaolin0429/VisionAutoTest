from __future__ import annotations

import argparse
import re

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import URL, make_url

from app.core.config import get_settings
from app.core.security import hash_secret
from app.db.migrations import upgrade_database
from app.db.session import SessionLocal
from app.models import User

DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def initialize_database(*, ensure_database: bool = True, run_migrations: bool = True, seed_admin: bool = True) -> None:
    settings = get_settings()
    if ensure_database:
        ensure_application_database()
    if run_migrations and settings.database_auto_migrate:
        upgrade_database(database_url=settings.database_url)
    settings.local_storage_path.mkdir(parents=True, exist_ok=True)
    if seed_admin:
        seed_default_admin()


def ensure_application_database() -> None:
    settings = get_settings()
    database_url = make_url(settings.database_url)
    if not should_auto_create_database(database_url):
        return

    admin_database_url = resolve_admin_database_url(database_url)
    database_name = database_url.database
    if database_name is None:
        raise RuntimeError("Application database name is missing from VAT_DATABASE_URL.")
    validate_database_name(database_name)

    admin_engine = create_engine(
        admin_database_url.render_as_string(hide_password=False),
        future=True,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    try:
        with admin_engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
                {"database_name": database_name},
            )
            if exists:
                return
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        admin_engine.dispose()


def seed_default_admin() -> None:
    settings = get_settings()
    if not settings.default_admin_username or not settings.default_admin_password:
        return
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.username == settings.default_admin_username, User.is_deleted.is_(False)))
        if admin is not None:
            return
        db.add(
            User(
                username=settings.default_admin_username,
                display_name="Administrator",
                password_hash=hash_secret(settings.default_admin_password),
                status="active",
            )
        )
        db.commit()


def should_auto_create_database(database_url: URL) -> bool:
    settings = get_settings()
    return (
        settings.app_env == "development"
        and settings.database_auto_create
        and database_url.get_backend_name() == "postgresql"
        and database_url.database == "AutoTestDev"
    )


def resolve_admin_database_url(database_url: URL) -> URL:
    settings = get_settings()
    if settings.database_admin_url:
        return make_url(settings.database_admin_url)
    return database_url.set(database="postgres")


def validate_database_name(database_name: str) -> None:
    if not DATABASE_NAME_PATTERN.fullmatch(database_name):
        raise RuntimeError(
            "Unsafe database name detected. Only letters, numbers and underscores are allowed for auto-created databases."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the application database.")
    parser.add_argument("--skip-create-db", action="store_true", help="Do not create the database before migrations.")
    parser.add_argument("--skip-migrate", action="store_true", help="Do not run Alembic migrations.")
    parser.add_argument("--skip-seed-admin", action="store_true", help="Do not create the default admin user.")
    args = parser.parse_args()
    initialize_database(
        ensure_database=not args.skip_create_db,
        run_migrations=not args.skip_migrate,
        seed_admin=not args.skip_seed_admin,
    )


if __name__ == "__main__":
    main()
