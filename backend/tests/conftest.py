from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEV_ENV_FILE = BACKEND_ROOT / ".env"
TEST_ENV_FILE = BACKEND_ROOT / ".env.test.local"


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _database_target(url: str) -> tuple[str, int | None, str]:
    parsed = urlsplit(url)
    return parsed.hostname or "", parsed.port, parsed.path.lstrip("/")


def pytest_configure() -> None:
    if "VAT_TEST_DATABASE_URL" not in os.environ:
        test_env = _read_env_file(TEST_ENV_FILE)
        test_database_url = test_env.get("VAT_TEST_DATABASE_URL")
        if test_database_url:
            os.environ["VAT_TEST_DATABASE_URL"] = test_database_url

    test_database_url = os.environ.get("VAT_TEST_DATABASE_URL")
    if not test_database_url:
        raise pytest.UsageError(
            "VAT_TEST_DATABASE_URL is required. Set it in backend/.env.test.local or export it before running pytest."
        )

    dev_database_url = os.environ.get("VAT_DATABASE_URL")
    if not dev_database_url:
        dev_database_url = _read_env_file(DEV_ENV_FILE).get("VAT_DATABASE_URL")

    if dev_database_url and _database_target(dev_database_url) == _database_target(test_database_url):
        raise pytest.UsageError(
            "VAT_TEST_DATABASE_URL must point to a database that is different from backend/.env VAT_DATABASE_URL."
        )
