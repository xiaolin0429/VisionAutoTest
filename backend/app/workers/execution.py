from __future__ import annotations

from app.db.session import SessionLocal
from app.models import RunReport, StepResult, TestCaseRun, TestCaseStep, TestRun, utc_now
from app.services.execution import finalize_cancelled_test_run, finalize_completed_test_run
from sqlalchemy import select


def process_test_run(test_run_id: int) -> None:
    with SessionLocal() as db:
        test_run = db.get(TestRun, test_run_id)
        if test_run is None:
            return
        if test_run.status == "cancelling":
            finalize_cancelled_test_run(db, test_run)
            return
        if test_run.status != "queued":
            return

        started_at = utc_now()
        test_run.status = "running"
        test_run.started_at = started_at
        db.commit()

        case_runs = db.scalars(
            select(TestCaseRun).where(TestCaseRun.test_run_id == test_run_id).order_by(TestCaseRun.sort_order.asc())
        ).all()

        passed_count = 0
        failed_count = 0
        error_count = 0

        for case_run in case_runs:
            db.refresh(test_run)
            if test_run.status == "cancelling":
                finalize_cancelled_test_run(db, test_run)
                return
            case_started_at = utc_now()
            case_run.status = "running"
            case_run.started_at = case_started_at
            db.commit()

            steps = db.scalars(
                select(TestCaseStep).where(TestCaseStep.test_case_id == case_run.test_case_id).order_by(TestCaseStep.step_no.asc())
            ).all()
            for step in steps:
                db.refresh(test_run)
                if test_run.status == "cancelling":
                    finalize_cancelled_test_run(db, test_run)
                    return
                step_started_at = utc_now()
                db.add(
                    StepResult(
                        case_run_id=case_run.id,
                        step_no=step.step_no,
                        step_type=step.step_type,
                        status="passed",
                        score_value=1.0,
                        started_at=step_started_at,
                        finished_at=utc_now(),
                        duration_ms=1,
                    )
                )

            case_run.status = "passed"
            case_run.finished_at = utc_now()
            case_run.duration_ms = max(1, int((case_run.finished_at - case_started_at).total_seconds() * 1000))
            passed_count += 1
            db.commit()

        if test_run.total_case_count <= 0:
            test_run.finished_at = utc_now()
            test_run.status = "error"
            db.add(
                RunReport(
                    test_run_id=test_run.id,
                    summary_status="error",
                    summary_json={
                        "total_case_count": 0,
                        "passed_case_count": 0,
                        "failed_case_count": 0,
                        "error_case_count": 0,
                        "message": "Test run contains no executable cases.",
                    },
                    generated_at=utc_now(),
                )
            )
            db.commit()
            return

        finalize_completed_test_run(
            db,
            test_run,
            passed_count=passed_count,
            failed_count=failed_count,
            error_count=error_count,
        )
