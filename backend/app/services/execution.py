from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
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
from app.services.execution_report import (
    build_report_summary,
    create_report_artifact,
    media_content_url,
    refresh_report_artifact_summary,
)
from app.services.execution_readiness import (
    build_readiness_issue,
    count_active_environment_profiles,
    dedupe_readiness_issues,
    get_test_suite_execution_readiness,
    get_workspace_execution_readiness,
    inspect_branch_payload_issues,
    inspect_execution_step_issues,
    inspect_test_case_execution_issues,
    inspect_test_suite_execution_issues,
    validate_case_execution_readiness,
    validate_visual_step_readiness,
)
from app.services.execution_steps import (
    ResolvedExecutionStep,
    build_conditional_branch_steps,
    build_execution_steps,
    get_component_in_workspace,
)
from app.services.execution_status import (
    finalize_cancelled_test_run,
    finalize_completed_test_run,
    finalize_errored_test_run,
    normalize_failure_payload,
    resolve_run_failure,
    truncate_failure_summary,
)
from app.services.helpers import count_total, require_workspace_access

FINAL_TEST_RUN_STATUSES = {
    "queued",
    "running",
    "cancelling",
    "cancelled",
    "passed",
    "failed",
    "partial_failed",
    "error",
}
FINAL_CASE_RUN_STATUSES = {
    "pending",
    "running",
    "passed",
    "failed",
    "error",
    "cancelled",
}
FINAL_STEP_RESULT_STATUSES = {"passed", "failed", "error"}
EXECUTABLE_TEMPLATE_STATUS = "published"
settings = get_settings()


def create_test_run(
    db: Session,
    *,
    user: User,
    workspace_id: int,
    test_suite_id: int | None,
    environment_profile_id: int | None,
    device_profile_id: int | None,
    trigger_source: str,
    idempotency_key: str | None,
    description: str | None = None,
    rerun_from_run_id: int | None = None,
    rerun_filter: str | None = None,
) -> TestRun:
    require_workspace_access(db, user, workspace_id)

    # ── 重跑模式：从原批次继承配置并提取失败用例 ──────────────────────────
    case_items: list[tuple[int, int]] | None = None  # [(test_case_id, sort_order)]
    if rerun_from_run_id is not None:
        original_run = db.get(TestRun, rerun_from_run_id)
        if original_run is None or original_run.workspace_id != workspace_id:
            raise ApiError(
                code="TEST_RUN_NOT_FOUND",
                message="Original test run not found.",
                status_code=404,
            )
        # 继承原批次配置（调用方显式传入时优先）
        if test_suite_id is None:
            test_suite_id = original_run.test_suite_id
        if environment_profile_id is None:
            environment_profile_id = original_run.environment_profile_id
        if device_profile_id is None:
            device_profile_id = original_run.device_profile_id
        if description is None:
            description = f"重跑自 #{rerun_from_run_id}"

        failed_case_runs = db.scalars(
            select(TestCaseRun)
            .where(
                TestCaseRun.test_run_id == rerun_from_run_id,
                TestCaseRun.status.in_(["failed", "error"]),
            )
            .order_by(TestCaseRun.sort_order.asc())
        ).all()
        if not failed_case_runs:
            raise ApiError(
                code="NO_FAILED_CASES_TO_RERUN",
                message="No failed or errored cases found in the original test run.",
                status_code=422,
            )
        case_items = [(cr.test_case_id, cr.sort_order) for cr in failed_case_runs]

    # ── 幂等键检查 ────────────────────────────────────────────────────────
    if idempotency_key:
        existing = db.scalar(
            select(TestRun).where(
                TestRun.workspace_id == workspace_id,
                TestRun.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            raise ApiError(
                code="IDEMPOTENCY_KEY_CONFLICT",
                message="Idempotency key already exists.",
                status_code=409,
            )

    # ── 套件 & 环境 & 设备校验 ────────────────────────────────────────────
    assert test_suite_id is not None  # schema validator guarantees this path
    assert environment_profile_id is not None

    suite = db.get(TestSuite, test_suite_id)
    if suite is None or suite.workspace_id != workspace_id or suite.is_deleted:
        raise ApiError(
            code="TEST_SUITE_NOT_FOUND",
            message="Test suite not found.",
            status_code=404,
        )
    if suite.status != "active":
        raise ApiError(
            code="TEST_SUITE_NOT_ACTIVE",
            message="Test suite must be active before execution.",
            status_code=422,
        )
    environment = db.get(EnvironmentProfile, environment_profile_id)
    if (
        environment is None
        or environment.workspace_id != workspace_id
        or environment.is_deleted
    ):
        raise ApiError(
            code="ENVIRONMENT_PROFILE_NOT_FOUND",
            message="Environment profile not found.",
            status_code=404,
        )
    if device_profile_id is not None:
        device = db.get(DeviceProfile, device_profile_id)
        if device is None or device.workspace_id != workspace_id or device.is_deleted:
            raise ApiError(
                code="DEVICE_PROFILE_NOT_FOUND",
                message="Device profile not found.",
                status_code=404,
            )

    # ── 普通模式：从套件加载用例 ──────────────────────────────────────────
    if case_items is None:
        suite_cases = db.scalars(
            select(SuiteCase)
            .where(SuiteCase.test_suite_id == test_suite_id)
            .order_by(SuiteCase.sort_order.asc())
        ).all()
        if not suite_cases:
            raise ApiError(
                code="TEST_SUITE_EMPTY",
                message="Test suite must contain at least one test case before execution.",
                status_code=422,
            )
        for suite_case in suite_cases:
            validate_case_execution_readiness(
                db, workspace_id=workspace_id, test_case_id=suite_case.test_case_id
            )
        case_items = [(sc.test_case_id, sc.sort_order) for sc in suite_cases]
    else:
        # 重跑模式同样校验就绪状态
        for test_case_id, _ in case_items:
            validate_case_execution_readiness(
                db, workspace_id=workspace_id, test_case_id=test_case_id
            )

    # ── 创建执行批次 ──────────────────────────────────────────────────────
    test_run = TestRun(
        workspace_id=workspace_id,
        test_suite_id=test_suite_id,
        environment_profile_id=environment_profile_id,
        device_profile_id=device_profile_id,
        trigger_source=trigger_source,
        triggered_by=user.id,
        idempotency_key=idempotency_key,
        description=description,
        status="queued",
        total_case_count=len(case_items),
    )
    db.add(test_run)
    db.flush()
    for test_case_id, sort_order in case_items:
        db.add(
            TestCaseRun(
                test_run_id=test_run.id,
                test_case_id=test_case_id,
                sort_order=sort_order,
                status="pending",
            )
        )
    db.commit()
    db.refresh(test_run)
    return test_run


def list_test_runs(
    db: Session,
    *,
    user: User,
    workspace_id: int,
    page: int,
    page_size: int,
    status: str | None,
):
    require_workspace_access(db, user, workspace_id)
    stmt = select(TestRun).where(TestRun.workspace_id == workspace_id)
    if status:
        stmt = stmt.where(TestRun.status == status)
    total = count_total(db, stmt)
    items = db.scalars(
        stmt.order_by(TestRun.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return items, total


def get_test_run(db: Session, test_run_id: int) -> TestRun:
    test_run = db.get(TestRun, test_run_id)
    if test_run is None:
        raise ApiError(
            code="TEST_RUN_NOT_FOUND", message="Test run not found.", status_code=404
        )
    return test_run


def update_test_run_status(
    db: Session, *, user: User, test_run: TestRun, status: str
) -> TestRun:
    require_workspace_access(db, user, test_run.workspace_id)
    if status != "cancelling" or test_run.status not in {"queued", "running"}:
        raise ApiError(
            code="TEST_RUN_STATUS_CONFLICT",
            message="Invalid test run status transition.",
            status_code=409,
        )
    test_run.status = "cancelling"
    db.commit()
    db.refresh(test_run)
    return test_run


def list_case_runs(db: Session, *, user: User, test_run: TestRun):
    require_workspace_access(db, user, test_run.workspace_id)
    return db.scalars(
        select(TestCaseRun)
        .where(TestCaseRun.test_run_id == test_run.id)
        .order_by(TestCaseRun.sort_order.asc())
    ).all()


def get_case_run(db: Session, case_run_id: int) -> TestCaseRun:
    case_run = db.get(TestCaseRun, case_run_id)
    if case_run is None:
        raise ApiError(
            code="CASE_RUN_NOT_FOUND", message="Case run not found.", status_code=404
        )
    return case_run


def list_step_results(db: Session, case_run_id: int):
    case_run = get_case_run(db, case_run_id)
    test_case = db.get(TestCase, case_run.test_case_id)
    steps = db.scalars(
        select(StepResult)
        .where(StepResult.case_run_id == case_run_id)
        .order_by(StepResult.step_no.asc())
    ).all()

    enriched_items = []
    for step in steps:
        repair_resource_type = "test_case"
        repair_resource_id = case_run.test_case_id
        repair_route_path = "/cases"

        source_case_step = None
        if test_case is not None:
            source_case_step = db.scalar(
                select(TestCaseStep).where(
                    TestCaseStep.test_case_id == test_case.id,
                    TestCaseStep.step_no == (step.parent_step_no or step.step_no),
                )
            )

        if source_case_step is not None and source_case_step.template_id is not None:
            repair_resource_type = "template"
            repair_resource_id = source_case_step.template_id
            repair_route_path = "/templates"
        elif source_case_step is not None and source_case_step.component_id is not None:
            repair_resource_type = "component"
            repair_resource_id = source_case_step.component_id
            repair_route_path = "/components"

        enriched_items.append(
            {
                "id": step.id,
                "case_run_id": step.case_run_id,
                "step_no": step.step_no,
                "step_type": step.step_type,
                "status": step.status,
                "score_value": float(step.score_value)
                if step.score_value is not None
                else None,
                "expected_media_object_id": step.expected_media_object_id,
                "actual_media_object_id": step.actual_media_object_id,
                "diff_media_object_id": step.diff_media_object_id,
                "error_message": step.error_message,
                "started_at": step.started_at,
                "finished_at": step.finished_at,
                "duration_ms": step.duration_ms,
                "parent_step_no": step.parent_step_no,
                "branch_key": step.branch_key,
                "branch_name": step.branch_name,
                "branch_step_index": step.branch_step_index,
                "repair_resource_type": repair_resource_type,
                "repair_resource_id": repair_resource_id,
                "repair_route_path": repair_route_path,
                "repair_step_no": step.parent_step_no or step.step_no,
                "created_at": step.created_at,
            }
        )
    return enriched_items


def get_report(db: Session, report_id: int) -> RunReport:
    report = db.get(RunReport, report_id)
    if report is None:
        raise ApiError(
            code="REPORT_NOT_FOUND", message="Report not found.", status_code=404
        )
    return report


def get_report_by_test_run(db: Session, test_run_id: int) -> RunReport | None:
    return db.scalar(select(RunReport).where(RunReport.test_run_id == test_run_id))


def list_report_artifacts(db: Session, report_id: int):
    return db.scalars(
        select(ReportArtifact)
        .where(ReportArtifact.report_id == report_id)
        .order_by(ReportArtifact.id.asc())
    ).all()


def _truncate_failure_summary(message: str | None, *, limit: int = 500) -> str | None:
    return truncate_failure_summary(message, limit=limit)


def _resolve_run_failure(
    *, case_runs: list[TestCaseRun], final_status: str
) -> tuple[str | None, str | None]:
    return resolve_run_failure(case_runs=case_runs, final_status=final_status)


def _normalize_failure_payload(
    *,
    status: str,
    failure_code: str | None,
    failure_summary: str | None,
) -> tuple[str, str]:
    return normalize_failure_payload(
        status=status,
        failure_code=failure_code,
        failure_summary=failure_summary,
    )


def _media_content_url(media_object_id: int) -> str:
    return media_content_url(media_object_id)


def _validate_case_execution_readiness(
    db: Session, *, workspace_id: int, test_case_id: int
) -> None:
    validate_case_execution_readiness(
        db, workspace_id=workspace_id, test_case_id=test_case_id
    )


def _get_component_in_workspace(
    db: Session, *, workspace_id: int, component_id: int | None
) -> Component:
    return get_component_in_workspace(
        db, workspace_id=workspace_id, component_id=component_id
    )


def _validate_visual_step_readiness(db: Session, *, workspace_id: int, step) -> None:
    validate_visual_step_readiness(db, workspace_id=workspace_id, step=step)


def _inspect_test_suite_execution_issues(
    db: Session, *, suite: TestSuite
) -> list[dict[str, Any]]:
    return inspect_test_suite_execution_issues(db, suite=suite)


def _inspect_test_case_execution_issues(
    db: Session,
    *,
    workspace_id: int,
    test_case: TestCase,
) -> list[dict[str, Any]]:
    return inspect_test_case_execution_issues(
        db, workspace_id=workspace_id, test_case=test_case
    )


def _inspect_execution_step_issues(
    db: Session,
    *,
    workspace_id: int,
    step,
    route_path: str,
) -> list[dict[str, Any]]:
    return inspect_execution_step_issues(
        db, workspace_id=workspace_id, step=step, route_path=route_path
    )


def _inspect_branch_payload_issues(
    db: Session,
    *,
    workspace_id: int,
    branch: Any,
    step_name: str,
    route_path: str,
) -> list[dict[str, Any]]:
    return inspect_branch_payload_issues(
        db,
        workspace_id=workspace_id,
        branch=branch,
        step_name=step_name,
        route_path=route_path,
    )


def _count_active_environment_profiles(db: Session, *, workspace_id: int) -> int:
    return count_active_environment_profiles(db, workspace_id=workspace_id)


def _build_readiness_issue(
    *,
    code: str,
    message: str,
    resource_type: str,
    resource_id: int | None = None,
    resource_name: str | None = None,
    route_path: str | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    return build_readiness_issue(
        code=code,
        message=message,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        route_path=route_path,
    )


def _dedupe_readiness_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return dedupe_readiness_issues(issues)
