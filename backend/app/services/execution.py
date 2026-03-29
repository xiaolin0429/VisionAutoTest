from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.models import (
    BaselineRevision,
    Component,
    ComponentStep,
    DeviceProfile,
    EnvironmentProfile,
    MediaObject,
    ReportArtifact,
    RunReport,
    StepResult,
    SuiteCase,
    Template,
    TestCase,
    TestCaseRun,
    TestCaseStep,
    TestRun,
    TestSuite,
    User,
    utc_now,
)
from app.services.helpers import count_total, require_workspace_access


@dataclass(slots=True)
class ResolvedExecutionStep:
    step_no: int
    step_type: str
    step_name: str
    template_id: int | None
    component_id: int | None
    payload_json: dict
    timeout_ms: int
    retry_times: int


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
    if suite.status != "active":
        raise ApiError(
            code="TEST_SUITE_NOT_ACTIVE",
            message="Test suite must be active before execution.",
            status_code=422,
        )
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
    for suite_case in suite_cases:
        _validate_case_execution_readiness(db, workspace_id=workspace_id, test_case_id=suite_case.test_case_id)

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


def build_execution_steps(db: Session, *, workspace_id: int, test_case_id: int) -> list[ResolvedExecutionStep]:
    test_case = db.get(TestCase, test_case_id)
    if test_case is None or test_case.workspace_id != workspace_id or test_case.is_deleted:
        raise ApiError(code="TEST_CASE_NOT_FOUND", message="Test case not found.", status_code=404)

    case_steps = db.scalars(
        select(TestCaseStep).where(TestCaseStep.test_case_id == test_case_id).order_by(TestCaseStep.step_no.asc())
    ).all()
    resolved_steps: list[ResolvedExecutionStep] = []

    for case_step in case_steps:
        if case_step.step_type != "component_call":
            resolved_steps.append(
                ResolvedExecutionStep(
                    step_no=0,
                    step_type=case_step.step_type,
                    step_name=case_step.step_name,
                    template_id=case_step.template_id,
                    component_id=case_step.component_id,
                    payload_json=case_step.payload_json or {},
                    timeout_ms=case_step.timeout_ms,
                    retry_times=case_step.retry_times,
                )
            )
            continue

        component = _get_component_in_workspace(db, workspace_id=workspace_id, component_id=case_step.component_id)
        component_steps = db.scalars(
            select(ComponentStep).where(ComponentStep.component_id == component.id).order_by(ComponentStep.step_no.asc())
        ).all()
        for component_step in component_steps:
            resolved_steps.append(
                ResolvedExecutionStep(
                    step_no=0,
                    step_type=component_step.step_type,
                    step_name=component_step.step_name,
                    template_id=component_step.template_id,
                    component_id=component.id,
                    payload_json=component_step.payload_json or {},
                    timeout_ms=case_step.timeout_ms,
                    retry_times=case_step.retry_times,
                )
            )

    for index, step in enumerate(resolved_steps, start=1):
        step.step_no = index
    return resolved_steps


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
    if passed_count == 0 and failed_count == 0 and error_count > 0:
        final_status = "error"
    elif failed_count > 0 and error_count == 0 and passed_count == 0:
        final_status = "failed"
    elif failed_count == 0 and error_count == 0:
        final_status = "passed"
    else:
        final_status = "partial_failed"
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


def finalize_errored_test_run(
    db: Session,
    test_run: TestRun,
    *,
    error_message: str,
) -> TestRun:
    now = utc_now()
    case_runs = db.scalars(
        select(TestCaseRun).where(TestCaseRun.test_run_id == test_run.id).order_by(TestCaseRun.sort_order.asc())
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
            case_run.failure_reason_code = "TEST_RUN_EXECUTION_ERROR"
            case_run.failure_summary = error_message
        error_count += 1

    test_run.status = "error"
    test_run.finished_at = now
    test_run.passed_case_count = passed_count
    test_run.failed_case_count = failed_count
    test_run.error_case_count = error_count

    report = db.scalar(select(RunReport).where(RunReport.test_run_id == test_run.id))
    summary_json = {
        "total_case_count": test_run.total_case_count,
        "passed_case_count": passed_count,
        "failed_case_count": failed_count,
        "error_case_count": error_count,
        "message": error_message,
    }
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


def get_report_by_test_run(db: Session, test_run_id: int) -> RunReport | None:
    return db.scalar(select(RunReport).where(RunReport.test_run_id == test_run_id))


def create_report_artifact(
    db: Session,
    *,
    report: RunReport,
    media: MediaObject,
    artifact_type: str = "screenshot",
) -> ReportArtifact:
    artifact = ReportArtifact(
        report_id=report.id,
        artifact_type=artifact_type,
        media_object_id=media.id,
        artifact_url=media.object_key,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


def _validate_case_execution_readiness(db: Session, *, workspace_id: int, test_case_id: int) -> None:
    test_case = db.get(TestCase, test_case_id)
    if test_case is None or test_case.workspace_id != workspace_id or test_case.is_deleted:
        raise ApiError(code="TEST_CASE_NOT_FOUND", message="Test case not found.", status_code=404)
    if test_case.status != "published":
        raise ApiError(
            code="PUBLISHED_VERSION_REQUIRED",
            message="Test case must be published before execution.",
            status_code=422,
        )

    case_steps = db.scalars(
        select(TestCaseStep).where(TestCaseStep.test_case_id == test_case_id).order_by(TestCaseStep.step_no.asc())
    ).all()
    for case_step in case_steps:
        _validate_visual_step_readiness(db, workspace_id=workspace_id, step=case_step)
        if case_step.component_id is None:
            continue
        component = _get_component_in_workspace(db, workspace_id=workspace_id, component_id=case_step.component_id)
        if component.status != "published":
            raise ApiError(
                code="PUBLISHED_VERSION_REQUIRED",
                message="Component must be published before execution.",
                status_code=422,
            )
        component_steps = db.scalars(
            select(ComponentStep).where(ComponentStep.component_id == component.id).order_by(ComponentStep.step_no.asc())
        ).all()
        for component_step in component_steps:
            _validate_visual_step_readiness(db, workspace_id=workspace_id, step=component_step)


def _get_component_in_workspace(db: Session, *, workspace_id: int, component_id: int | None) -> Component:
    if component_id is None:
        raise ApiError(code="COMPONENT_NOT_FOUND", message="Component not found.", status_code=404)
    component = db.get(Component, component_id)
    if component is None or component.workspace_id != workspace_id or component.is_deleted:
        raise ApiError(code="COMPONENT_NOT_FOUND", message="Component not found.", status_code=404)
    return component


def _validate_visual_step_readiness(db: Session, *, workspace_id: int, step) -> None:
    if step.step_type not in {"template_assert", "ocr_assert"}:
        return

    if step.step_type == "template_assert" and step.template_id is None:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="template_assert step requires template_id.",
            status_code=422,
        )

    if step.step_type == "ocr_assert":
        payload = step.payload_json or {}
        selector = payload.get("selector")
        expected_text = payload.get("expected_text")
        if not isinstance(selector, str) or not selector.strip() or not isinstance(expected_text, str) or not expected_text.strip():
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="ocr_assert step requires selector and expected_text.",
                status_code=422,
            )

    if step.template_id is None:
        return

    template = db.get(Template, step.template_id)
    if template is None or template.workspace_id != workspace_id or template.is_deleted:
        raise ApiError(code="TEMPLATE_NOT_FOUND", message="Template not found.", status_code=404)

    if template.current_baseline_revision_id is None:
        raise ApiError(
            code="BASELINE_REVISION_REQUIRED",
            message="Template must have a current baseline revision before execution.",
            status_code=422,
        )

    baseline = db.get(BaselineRevision, template.current_baseline_revision_id)
    if baseline is None or baseline.template_id != template.id:
        raise ApiError(
            code="BASELINE_REVISION_REQUIRED",
            message="Template current baseline revision is invalid.",
            status_code=422,
        )

    expected_strategy = "template" if step.step_type == "template_assert" else "ocr"
    if template.match_strategy != expected_strategy:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message=f"{step.step_type} step requires template match_strategy `{expected_strategy}`.",
            status_code=422,
        )
