from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VisionAutoTest Backend"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite+pysqlite:///./.data/visionautotest.db"
    local_storage_path: Path = Path(".data/media")
    access_token_ttl_seconds: int = 7200
    refresh_token_ttl_seconds: int = 7 * 24 * 3600
    default_admin_username: str = "admin"
    default_admin_password: str = "admin123456"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="VAT_", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

