from __future__ import annotations

import argparse

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import TestRun
from app.workers.execution import process_test_run


def drain_queued_test_runs(*, limit: int | None = None) -> int:
    settings = get_settings()
    batch_size = limit or settings.execution_worker_batch_size
    with SessionLocal() as db:
        queued_run_ids = db.scalars(
            select(TestRun.id)
            .where(TestRun.status == "queued")
            .order_by(TestRun.id.asc())
            .limit(batch_size)
        ).all()

    for test_run_id in queued_run_ids:
        process_test_run(test_run_id)
    return len(queued_run_ids)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Drain queued VisionAutoTest test runs."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum queued test runs to process in this invocation.",
    )
    args = parser.parse_args()
    processed = drain_queued_test_runs(limit=args.limit)
    print(f"processed={processed}")
