from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER_DEFAULT_ADMIN_PASSWORD = "change-me-before-use"
PLACEHOLDER_JWT_SECRET_KEY = "change-me-jwt-secret"
PLACEHOLDER_DATA_ENCRYPTION_KEY = "change-me-data-encryption-key"


class Settings(BaseSettings):
    app_name: str = "VisionAutoTest Backend"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field(..., min_length=1)
    database_admin_url: str | None = None
    database_auto_create: bool = False
    database_auto_migrate: bool = False
    local_storage_path: Path = Path(".data/media")
    demo_target_base_url: str = "http://127.0.0.1:8000/demo/acceptance-target"
    playwright_headless: bool = True
    playwright_navigation_timeout_ms: int = 15000
    access_token_ttl_seconds: int = 7200
    refresh_token_ttl_seconds: int = 7 * 24 * 3600
    jwt_secret_key: str = PLACEHOLDER_JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "visionautotest-backend"
    data_encryption_key: str = PLACEHOLDER_DATA_ENCRYPTION_KEY
    default_admin_username: str | None = None
    default_admin_password: str | None = None

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_prefix="VAT_",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_security_defaults(self) -> "Settings":
        placeholder_markers = ("<db-user>", "<db-password>")
        if any(marker in self.database_url for marker in placeholder_markers):
            raise ValueError("VAT_DATABASE_URL contains placeholder values. Please set real local credentials.")
        if self.database_admin_url and any(marker in self.database_admin_url for marker in placeholder_markers):
            raise ValueError("VAT_DATABASE_ADMIN_URL contains placeholder values. Please set real local credentials.")
        if self.app_env in {"staging", "production"}:
            if self.database_auto_create:
                raise ValueError("VAT_DATABASE_AUTO_CREATE must be false outside development or test.")
            if self.database_auto_migrate:
                raise ValueError("VAT_DATABASE_AUTO_MIGRATE must be false outside development or test.")
        if (self.default_admin_username is None) != (self.default_admin_password is None):
            raise ValueError(
                "VAT_DEFAULT_ADMIN_USERNAME and VAT_DEFAULT_ADMIN_PASSWORD must either both be set or both be omitted."
            )
        if self.default_admin_password == PLACEHOLDER_DEFAULT_ADMIN_PASSWORD:
            raise ValueError("VAT_DEFAULT_ADMIN_PASSWORD must be changed from the placeholder value before startup.")
        if self.jwt_secret_key == PLACEHOLDER_JWT_SECRET_KEY:
            raise ValueError("VAT_JWT_SECRET_KEY must be changed from the placeholder value before startup.")
        if self.data_encryption_key == PLACEHOLDER_DATA_ENCRYPTION_KEY:
            raise ValueError("VAT_DATA_ENCRYPTION_KEY must be changed from the placeholder value before startup.")
        if self.jwt_algorithm != "HS256":
            raise ValueError("VAT_JWT_ALGORITHM currently only supports HS256.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
