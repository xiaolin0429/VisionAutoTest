from __future__ import annotations

from contextlib import contextmanager
import os
import sys
import tempfile
from pathlib import Path

from tests.support.constants import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME


def _require_test_database_url() -> str:
    database_url = os.environ.get("VAT_TEST_DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "VAT_TEST_DATABASE_URL is required. Please prepare an external PostgreSQL test database before running backend tests."
        )
    return database_url


def _reset_local_data() -> None:
    if "app.db.session" in sys.modules:
        from app.db.session import engine

        engine.dispose()
    stale_modules = [module_name for module_name in sys.modules if module_name == "app" or module_name.startswith("app.")]
    for module_name in stale_modules:
        sys.modules.pop(module_name, None)
    backend_root = Path(__file__).resolve().parents[2]
    testdata_root = backend_root / ".testdata"
    testdata_root.mkdir(exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="case_", dir=testdata_root))
    os.environ["VAT_DATABASE_URL"] = _require_test_database_url()
    os.environ["VAT_APP_ENV"] = "test"
    os.environ["VAT_DATABASE_AUTO_CREATE"] = "false"
    os.environ["VAT_DATABASE_AUTO_MIGRATE"] = "true"
    os.environ.pop("VAT_DATABASE_ADMIN_URL", None)
    os.environ["VAT_LOCAL_STORAGE_PATH"] = str(temp_dir / "media")
    os.environ["VAT_DEFAULT_ADMIN_USERNAME"] = TEST_ADMIN_USERNAME
    os.environ["VAT_DEFAULT_ADMIN_PASSWORD"] = TEST_ADMIN_PASSWORD
    os.environ["VAT_JWT_SECRET_KEY"] = "test-jwt-secret-key-visionautotest-2026"
    os.environ["VAT_JWT_ALGORITHM"] = "HS256"
    os.environ["VAT_JWT_ISSUER"] = "visionautotest-backend-test"
    os.environ["VAT_DATA_ENCRYPTION_KEY"] = "test-data-encryption-key-visionautotest-2026"

    from app.db.migrations import reset_database_schema, upgrade_database

    reset_database_schema(database_url=os.environ["VAT_DATABASE_URL"])
    upgrade_database(database_url=os.environ["VAT_DATABASE_URL"])


def load_app():
    from app.main import app

    return app


@contextmanager
def app_client(*, reset: bool = False):
    from fastapi.testclient import TestClient

    if reset:
        _reset_local_data()
    with TestClient(load_app()) as client:
        yield client
