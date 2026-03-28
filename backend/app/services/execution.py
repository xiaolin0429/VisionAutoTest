from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.models import (
    DeviceProfile,
    EnvironmentProfile,
    RunReport,
    StepResult,
    SuiteCase,
    TestCaseRun,
    TestRun,
    TestSuite,
    User,
    utc_now,
)
from app.services.helpers import count_total, require_workspace_access


def create_test_run(
    db: Session,
    *,
    user: User,
    workspace_id: int,
    test_suite_id: int,
    environment_profile_id: int,
    device_profile_id: int | None,
    trigger_source: str,
    idempotency_key: str | None,
) -> TestRun:
    require_workspace_access(db, user, workspace_id)
    if idempotency_key:
        existing = db.scalar(
            select(TestRun).where(
                TestRun.workspace_id == workspace_id,
                TestRun.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            raise ApiError(code="IDEMPOTENCY_KEY_CONFLICT", message="Idempotency key already exists.", status_code=409)
    suite = db.get(TestSuite, test_suite_id)
    if suite is None or suite.workspace_id != workspace_id or suite.is_deleted:
        raise ApiError(code="TEST_SUITE_NOT_FOUND", message="Test suite not found.", status_code=404)
    environment = db.get(EnvironmentProfile, environment_profile_id)
    if environment is None or environment.workspace_id != workspace_id or environment.is_deleted:
        raise ApiError(code="ENVIRONMENT_PROFILE_NOT_FOUND", message="Environment profile not found.", status_code=404)
    if device_profile_id is not None:
        device = db.get(DeviceProfile, device_profile_id)
        if device is None or device.workspace_id != workspace_id or device.is_deleted:
            raise ApiError(code="DEVICE_PROFILE_NOT_FOUND", message="Device profile not found.", status_code=404)

    suite_cases = db.scalars(
        select(SuiteCase).where(SuiteCase.test_suite_id == test_suite_id).order_by(SuiteCase.sort_order.asc())
    ).all()
    if not suite_cases:
        raise ApiError(
            code="TEST_SUITE_EMPTY",
            message="Test suite must contain at least one test case before execution.",
            status_code=422,
        )
    test_run = TestRun(
        workspace_id=workspace_id,
        test_suite_id=test_suite_id,
        environment_profile_id=environment_profile_id,
        device_profile_id=device_profile_id,
        trigger_source=trigger_source,
        triggered_by=user.id,
        idempotency_key=idempotency_key,
        status="queued",
        total_case_count=len(suite_cases),
    )
    db.add(test_run)
    db.flush()
    for suite_case in suite_cases:
        db.add(
            TestCaseRun(
                test_run_id=test_run.id,
                test_case_id=suite_case.test_case_id,
                sort_order=suite_case.sort_order,
                status="pending",
            )
        )
    db.commit()
    db.refresh(test_run)
    return test_run


def list_test_runs(db: Session, *, user: User, workspace_id: int, page: int, page_size: int, status: str | None):
    require_workspace_access(db, user, workspace_id)
    stmt = select(TestRun).where(TestRun.workspace_id == workspace_id)
    if status:
        stmt = stmt.where(TestRun.status == status)
    total = count_total(db, stmt)
    items = db.scalars(stmt.order_by(TestRun.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def get_test_run(db: Session, test_run_id: int) -> TestRun:
    test_run = db.get(TestRun, test_run_id)
    if test_run is None:
        raise ApiError(code="TEST_RUN_NOT_FOUND", message="Test run not found.", status_code=404)
    return test_run


def update_test_run_status(db: Session, *, user: User, test_run: TestRun, status: str) -> TestRun:
    require_workspace_access(db, user, test_run.workspace_id)
    if status != "cancelling" or test_run.status not in {"queued", "running"}:
        raise ApiError(code="TEST_RUN_STATUS_CONFLICT", message="Invalid test run status transition.", status_code=409)
    test_run.status = "cancelling"
    db.commit()
    db.refresh(test_run)
    return test_run


def finalize_cancelled_test_run(db: Session, test_run: TestRun) -> TestRun:
    now = utc_now()
    case_runs = db.scalars(
        select(TestCaseRun).where(TestCaseRun.test_run_id == test_run.id).order_by(TestCaseRun.sort_order.asc())
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
                case_run.duration_ms = max(1, int((case_run.finished_at - case_run.started_at).total_seconds() * 1000))
        cancelled_count += 1

    test_run.status = "cancelled"
    test_run.finished_at = test_run.finished_at or now
    test_run.passed_case_count = passed_count
    test_run.failed_case_count = failed_count
    test_run.error_case_count = error_count

    report = db.scalar(select(RunReport).where(RunReport.test_run_id == test_run.id))
    summary_json = {
        "total_case_count": test_run.total_case_count,
        "passed_case_count": passed_count,
        "failed_case_count": failed_count,
        "error_case_count": error_count,
        "cancelled_case_count": cancelled_count,
    }
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
    final_status = "passed" if failed_count == 0 and error_count == 0 else "partial_failed"
    update_result = db.execute(
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
    if update_result.rowcount == 0:
        db.expire_all()
        latest_test_run = db.get(TestRun, test_run.id)
        if latest_test_run is not None and latest_test_run.status == "cancelling":
            return finalize_cancelled_test_run(db, latest_test_run)
        if latest_test_run is None:
            raise ApiError(code="TEST_RUN_NOT_FOUND", message="Test run not found.", status_code=404)
        return latest_test_run

    report = db.scalar(select(RunReport).where(RunReport.test_run_id == test_run.id))
    summary_json = {
        "total_case_count": test_run.total_case_count,
        "passed_case_count": passed_count,
        "failed_case_count": failed_count,
        "error_case_count": error_count,
    }
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
        raise ApiError(code="TEST_RUN_NOT_FOUND", message="Test run not found.", status_code=404)
    return latest_test_run


def list_case_runs(db: Session, *, user: User, test_run: TestRun):
    require_workspace_access(db, user, test_run.workspace_id)
    return db.scalars(
        select(TestCaseRun).where(TestCaseRun.test_run_id == test_run.id).order_by(TestCaseRun.sort_order.asc())
    ).all()


def get_case_run(db: Session, case_run_id: int) -> TestCaseRun:
    case_run = db.get(TestCaseRun, case_run_id)
    if case_run is None:
        raise ApiError(code="CASE_RUN_NOT_FOUND", message="Case run not found.", status_code=404)
    return case_run


def list_step_results(db: Session, case_run_id: int):
    return db.scalars(
        select(StepResult).where(StepResult.case_run_id == case_run_id).order_by(StepResult.step_no.asc())
    ).all()


def get_report(db: Session, report_id: int) -> RunReport:
    report = db.get(RunReport, report_id)
    if report is None:
        raise ApiError(code="REPORT_NOT_FOUND", message="Report not found.", status_code=404)
    return report
