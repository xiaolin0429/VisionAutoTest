from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.models import RunReport, TestCaseRun, TestRun, utc_now
from app.services.execution_report import build_report_summary


def truncate_failure_summary(message: str | None, *, limit: int = 500) -> str | None:
    if message is None:
        return None
    normalized = message.strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def finalize_cancelled_test_run(db: Session, test_run: TestRun) -> TestRun:
    now = utc_now()
    cancellation_code = "TEST_RUN_CANCELLED"
    cancellation_summary = "Test run was cancelled."
    case_runs = db.scalars(
        select(TestCaseRun)
        .where(TestCaseRun.test_run_id == test_run.id)
        .order_by(TestCaseRun.sort_order.asc())
    ).all()
    cancelled_count = 0
    passed_count = 0
    failed_count = 0
    error_count = 0
    for case_run in case_runs:
        if case_run.status == "passed":
            passed_count += 1
            continue
        if case_run.status == "failed":
            failed_count += 1
            continue
        if case_run.status == "error":
            error_count += 1
            continue
        if case_run.status != "cancelled":
            case_run.status = "cancelled"
            case_run.finished_at = case_run.finished_at or now
            if case_run.started_at is not None and case_run.duration_ms is None:
                finished_at = case_run.finished_at
                assert finished_at is not None
                case_run.duration_ms = max(
                    1,
                    int((finished_at - case_run.started_at).total_seconds() * 1000),
                )
            case_run.failure_reason_code = (
                case_run.failure_reason_code or cancellation_code
            )
            case_run.failure_summary = case_run.failure_summary or cancellation_summary
        cancelled_count += 1

    test_run.status = "cancelled"
    test_run.finished_at = test_run.finished_at or now
    test_run.passed_case_count = passed_count
    test_run.failed_case_count = failed_count
    test_run.error_case_count = error_count

    report = db.scalar(select(RunReport).where(RunReport.test_run_id == test_run.id))
    summary_json = build_report_summary(
        status="cancelled",
        total_case_count=test_run.total_case_count,
        passed_count=passed_count,
        failed_count=failed_count,
        error_count=error_count,
        cancelled_count=cancelled_count,
        started_at=test_run.started_at,
        finished_at=test_run.finished_at,
        failure_code=cancellation_code,
        failure_summary=cancellation_summary,
    )
    if report is None:
        db.add(
            RunReport(
                test_run_id=test_run.id,
                summary_status="cancelled",
                summary_json=summary_json,
                generated_at=now,
            )
        )
    else:
        report.summary_status = "cancelled"
        report.summary_json = summary_json
        report.generated_at = now

    db.commit()
    db.refresh(test_run)
    return test_run


def finalize_completed_test_run(
    db: Session,
    test_run: TestRun,
    *,
    passed_count: int,
    failed_count: int,
    error_count: int,
) -> TestRun:
    now = utc_now()
    if passed_count == 0 and failed_count == 0 and error_count > 0:
        final_status = "error"
    elif failed_count > 0 and error_count == 0 and passed_count == 0:
        final_status = "failed"
    elif failed_count == 0 and error_count == 0:
        final_status = "passed"
    else:
        final_status = "partial_failed"
    case_runs: list[TestCaseRun] = list(
        db.scalars(
            select(TestCaseRun)
            .where(TestCaseRun.test_run_id == test_run.id)
            .order_by(TestCaseRun.sort_order.asc())
        ).all()
    )
    failure_code, failure_summary = resolve_run_failure(
        case_runs=case_runs, final_status=final_status
    )
    update_result: Any = db.execute(
        update(TestRun)
        .where(TestRun.id == test_run.id, TestRun.status == "running")
        .values(
            finished_at=now,
            passed_case_count=passed_count,
            failed_case_count=failed_count,
            error_case_count=error_count,
            status=final_status,
        )
    )
    if not update_result.rowcount:
        db.expire_all()
        latest_test_run = db.get(TestRun, test_run.id)
        if latest_test_run is not None and latest_test_run.status == "cancelling":
            return finalize_cancelled_test_run(db, latest_test_run)
        if latest_test_run is None:
            raise ApiError(
                code="TEST_RUN_NOT_FOUND",
                message="Test run not found.",
                status_code=404,
            )
        return latest_test_run

    report = db.scalar(select(RunReport).where(RunReport.test_run_id == test_run.id))
    summary_json = build_report_summary(
        status=final_status,
        total_case_count=test_run.total_case_count,
        passed_count=passed_count,
        failed_count=failed_count,
        error_count=error_count,
        cancelled_count=0,
        started_at=test_run.started_at,
        finished_at=now,
        failure_code=failure_code,
        failure_summary=failure_summary,
    )
    if report is None:
        db.add(
            RunReport(
                test_run_id=test_run.id,
                summary_status=final_status,
                summary_json=summary_json,
                generated_at=now,
            )
        )
    else:
        report.summary_status = final_status
        report.summary_json = summary_json
        report.generated_at = now
    db.commit()
    latest_test_run = db.get(TestRun, test_run.id)
    if latest_test_run is None:
        raise ApiError(
            code="TEST_RUN_NOT_FOUND", message="Test run not found.", status_code=404
        )
    return latest_test_run


def finalize_errored_test_run(
    db: Session,
    test_run: TestRun,
    *,
    failure_reason_code: str = "TEST_RUN_EXECUTION_ERROR",
    error_message: str,
) -> TestRun:
    now = utc_now()
    case_runs = db.scalars(
        select(TestCaseRun)
        .where(TestCaseRun.test_run_id == test_run.id)
        .order_by(TestCaseRun.sort_order.asc())
    ).all()
    error_count = 0
    passed_count = 0
    failed_count = 0
    for case_run in case_runs:
        if case_run.status == "passed":
            passed_count += 1
            continue
        if case_run.status == "failed":
            failed_count += 1
            continue
        if case_run.status != "error":
            case_run.status = "error"
            case_run.finished_at = case_run.finished_at or now
            case_run.duration_ms = case_run.duration_ms or 1
            case_run.failure_reason_code = failure_reason_code
            case_run.failure_summary = truncate_failure_summary(error_message)
        error_count += 1

    test_run.status = "error"
    test_run.finished_at = now
    test_run.passed_case_count = passed_count
    test_run.failed_case_count = failed_count
    test_run.error_case_count = error_count

    report = db.scalar(select(RunReport).where(RunReport.test_run_id == test_run.id))
    summary_json = build_report_summary(
        status="error",
        total_case_count=test_run.total_case_count,
        passed_count=passed_count,
        failed_count=failed_count,
        error_count=error_count,
        cancelled_count=0,
        started_at=test_run.started_at,
        finished_at=now,
        failure_code=failure_reason_code,
        failure_summary=truncate_failure_summary(error_message),
    )
    if report is None:
        db.add(
            RunReport(
                test_run_id=test_run.id,
                summary_status="error",
                summary_json=summary_json,
                generated_at=now,
            )
        )
    else:
        report.summary_status = "error"
        report.summary_json = summary_json
        report.generated_at = now

    db.commit()
    db.refresh(test_run)
    return test_run


def normalize_failure_payload(
    *,
    status: str,
    failure_code: str | None,
    failure_summary: str | None,
) -> tuple[str, str]:
    if failure_code and failure_summary:
        return failure_code, failure_summary
    default_code = {
        "failed": "ASSERTION_FAILED",
        "error": "STEP_EXECUTION_ERROR",
        "cancelled": "TEST_RUN_CANCELLED",
    }.get(status, "TEST_RUN_EXECUTION_ERROR")
    default_summary = {
        "failed": "Execution finished with assertion failure.",
        "error": "Execution finished with runtime error.",
        "cancelled": "Test run was cancelled.",
    }.get(status, "Execution failed.")
    return failure_code or default_code, failure_summary or default_summary


def resolve_run_failure(
    *, case_runs: list[TestCaseRun], final_status: str
) -> tuple[str | None, str | None]:
    if final_status == "passed":
        return None, None
    if final_status == "cancelled":
        return "TEST_RUN_CANCELLED", "Test run was cancelled."
    for case_run in case_runs:
        if case_run.status not in {"failed", "error", "cancelled"}:
            continue
        return normalize_failure_payload(
            status=case_run.status,
            failure_code=case_run.failure_reason_code,
            failure_summary=case_run.failure_summary,
        )
    if final_status == "partial_failed":
        return (
            "TEST_RUN_PARTIAL_FAILED",
            "Test run completed with failed or errored cases.",
        )
    if final_status == "failed":
        return "TEST_RUN_FAILED", "Test run completed with failed cases."
    if final_status == "error":
        return "TEST_RUN_EXECUTION_ERROR", "Test run completed with execution errors."
    return None, None
