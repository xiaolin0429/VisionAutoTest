from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine, inspect

from tests.support.runtime import _reset_local_data

PREVIOUS_REVISION = "a1b2c3d4e5f6"


def get_step_result_metadata_column(
    database_url: str,
) -> dict[str, Any] | None:
    engine = create_engine(database_url, future=True)
    try:
        columns = inspect(engine).get_columns("exec_step_results")
        return next(
            (
                column
                for column in columns
                if column["name"] == "result_metadata_json"
            ),
            None,
        )
    finally:
        engine.dispose()


def test_step_result_metadata_migration_upgrades_and_downgrades() -> None:
    _reset_local_data()
    from app.db.migrations import downgrade_database, upgrade_database

    database_url = os.environ["VAT_DATABASE_URL"]
    upgraded_column = get_step_result_metadata_column(database_url)
    assert upgraded_column is not None
    assert upgraded_column["nullable"] is False
    assert upgraded_column["type"].__class__.__name__ == "JSON"
    assert "{}" in str(upgraded_column["default"])

    downgrade_database(
        database_url=database_url,
        revision=PREVIOUS_REVISION,
    )
    try:
        assert get_step_result_metadata_column(database_url) is None
    finally:
        upgrade_database(database_url=database_url)

    assert get_step_result_metadata_column(database_url) is not None
