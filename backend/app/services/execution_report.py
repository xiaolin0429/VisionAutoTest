from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.http import ApiError
from app.models import (
    Component,
    DeviceProfile,
    EnvironmentProfile,
    MediaObject,
    ReportArtifact,
    RunReport,
    StepResult,
    Template,
    TestCase,
    TestCaseRun,
    TestRun,
    TestSuite,
)
from app.services.execution_steps import build_execution_steps
from app.services.workspace import validate_environment_base_url

settings = get_settings()


def build_report_summary(
    *,
    status: str,
    total_case_count: int,
    passed_count: int,
    failed_count: int,
    error_count: int,
    cancelled_count: int,
    started_at,
    finished_at,
    failure_code: str | None,
    failure_summary: str | None,
    repair_target: dict[str, Any] | None = None,
    artifact_totals: dict[str, int] | None = None,
) -> dict[str, Any]:
    artifacts_by_type = artifact_totals or {}
    duration_ms = None
    if started_at is not None and finished_at is not None:
        duration_ms = max(1, int((finished_at - started_at).total_seconds() * 1000))

    return {
        "status": status,
        "counts": {
            "total": total_case_count,
            "passed": passed_count,
            "failed": failed_count,
            "error": error_count,
            "cancelled": cancelled_count,
        },
        "failure": None
        if failure_code is None and failure_summary is None
        else {
            "code": failure_code,
            "summary": failure_summary,
            "repair_target": repair_target,
        },
        "timing": {
            "started_at": started_at.isoformat() if started_at is not None else None,
            "finished_at": finished_at.isoformat() if finished_at is not None else None,
            "duration_ms": duration_ms,
        },
        "artifacts": {
            "total": sum(artifacts_by_type.values()),
            "by_type": artifacts_by_type,
        },
        "total_case_count": total_case_count,
        "passed_case_count": passed_count,
        "failed_case_count": failed_count,
        "error_case_count": error_count,
        "cancelled_case_count": cancelled_count,
        "message": failure_summary,
    }


def resolve_report_repair_target(
    db: Session,
    *,
    test_run: TestRun,
    failure_code: str | None,
    case_runs: list[TestCaseRun] | None = None,
) -> dict[str, Any] | None:
    """Resolve one deterministic repair target from stable error codes and run relations."""
    if not failure_code or failure_code == "TEST_RUN_CANCELLED":
        return None

    if failure_code in {
        "ENVIRONMENT_PROFILE_REQUIRED",
        "ENVIRONMENT_PROFILE_NOT_FOUND",
        "ENVIRONMENT_PROFILE_NOT_ACTIVE",
        "ENVIRONMENT_BASE_URL_INVALID",
    }:
        environment = db.get(EnvironmentProfile, test_run.environment_profile_id)
        return _repair_target(
            resource_type="environment_profile",
            resource_id=test_run.environment_profile_id,
            resource_name=environment.profile_name if environment else "执行环境",
            route_path="/environments",
        )

    if failure_code in {"DEVICE_PROFILE_NOT_FOUND", "DEVICE_PROFILE_INVALID"}:
        device = (
            db.get(DeviceProfile, test_run.device_profile_id)
            if test_run.device_profile_id is not None
            else None
        )
        return _repair_target(
            resource_type="device_profile",
            resource_id=test_run.device_profile_id,
            resource_name=device.profile_name if device else "设备档案",
            route_path="/environments",
        )

    if failure_code in {
        "TEST_SUITE_REQUIRED",
        "TEST_SUITE_NOT_FOUND",
        "TEST_SUITE_NOT_ACTIVE",
        "TEST_SUITE_EMPTY",
    }:
        suite = db.get(TestSuite, test_run.test_suite_id)
        return _repair_target(
            resource_type="test_suite",
            resource_id=test_run.test_suite_id,
            resource_name=suite.suite_name if suite else "测试套件",
            route_path="/suites",
        )

    if failure_code in {
        "SCREENSHOT_CAPTURE_FAILED",
        "TEST_RUN_EXECUTION_ERROR",
        "TEST_RUN_PARTIAL_FAILED",
        "TEST_RUN_FAILED",
    }:
        return _system_repair_target()

    if failure_code == "BROWSER_EXECUTION_ERROR":
        environment = db.get(EnvironmentProfile, test_run.environment_profile_id)
        if (
            environment is not None
            and environment.workspace_id == test_run.workspace_id
            and not environment.is_deleted
        ):
            try:
                validate_environment_base_url(environment.base_url)
            except ApiError:
                return _repair_target(
                    resource_type="environment_profile",
                    resource_id=environment.id,
                    resource_name=environment.profile_name,
                    route_path="/environments",
                )
        return _system_repair_target()

    target_case_run, target_step_result = _failure_context(
        db,
        test_run=test_run,
        case_runs=case_runs,
    )
    if target_case_run is None:
        return _system_repair_target()

    test_case = db.get(TestCase, target_case_run.test_case_id)
    resolved_step = None
    if target_step_result is not None:
        try:
            resolved_steps = build_execution_steps(
                db,
                workspace_id=test_run.workspace_id,
                test_case_id=target_case_run.test_case_id,
            )
            resolved_step = next(
                (
                    item
                    for item in resolved_steps
                    if item.step_no == target_step_result.step_no
                ),
                None,
            )
        except ApiError:
            resolved_step = None

    repair_step_no = (
        target_step_result.parent_step_no or target_step_result.step_no
        if target_step_result is not None
        else None
    )
    if failure_code in {"TEMPLATE_ASSERTION_FAILED", "BASELINE_REVISION_REQUIRED"}:
        template_id = resolved_step.template_id if resolved_step is not None else None
        template = db.get(Template, template_id) if template_id is not None else None
        if template_id is not None:
            return _repair_target(
                resource_type="template",
                resource_id=template_id,
                resource_name=template.template_name if template else "视觉模板",
                route_path="/templates",
                step_no=repair_step_no,
            )

    if resolved_step is not None and resolved_step.component_id is not None:
        component = db.get(Component, resolved_step.component_id)
        return _repair_target(
            resource_type="component",
            resource_id=resolved_step.component_id,
            resource_name=component.component_name if component else "公共组件",
            route_path="/components",
            step_no=repair_step_no,
        )

    return _repair_target(
        resource_type="test_case",
        resource_id=target_case_run.test_case_id,
        resource_name=test_case.case_name if test_case else "测试用例",
        route_path="/cases",
        step_no=repair_step_no,
    )


def build_report_read_view(
    db: Session,
    *,
    report: RunReport,
    test_run: TestRun | None = None,
) -> dict[str, Any]:
    """Build an API-only report view without mutating historical summary JSON."""
    linked_test_run = test_run or db.get(TestRun, report.test_run_id)
    if linked_test_run is None:
        raise ApiError(
            code="TEST_RUN_NOT_FOUND",
            message="Test run not found.",
            status_code=404,
        )

    summary_json = deepcopy(report.summary_json or {})
    failure = summary_json.get("failure")
    if isinstance(failure, dict) and "repair_target" not in failure:
        enriched_failure = dict(failure)
        failure_code = enriched_failure.get("code")
        enriched_failure["repair_target"] = resolve_report_repair_target(
            db,
            test_run=linked_test_run,
            failure_code=failure_code if isinstance(failure_code, str) else None,
        )
        summary_json["failure"] = enriched_failure

    return {
        "id": report.id,
        "test_run_id": report.test_run_id,
        "summary_status": report.summary_status,
        "summary_json": summary_json,
        "generated_at": report.generated_at,
        "created_at": report.created_at,
    }


def _failure_context(
    db: Session,
    *,
    test_run: TestRun,
    case_runs: list[TestCaseRun] | None,
) -> tuple[TestCaseRun | None, StepResult | None]:
    candidates = case_runs
    if candidates is None:
        candidates = list(
            db.scalars(
                select(TestCaseRun)
                .where(TestCaseRun.test_run_id == test_run.id)
                .order_by(TestCaseRun.sort_order.asc())
            ).all()
        )
    target_case_run = next(
        (
            item
            for item in candidates
            if item.status in {"failed", "error", "cancelled"}
        ),
        None,
    )
    if target_case_run is None:
        return None, None
    target_step_result = db.scalar(
        select(StepResult)
        .where(
            StepResult.case_run_id == target_case_run.id,
            StepResult.status.in_(["failed", "error"]),
        )
        .order_by(StepResult.step_no.asc())
    )
    return target_case_run, target_step_result


def _repair_target(
    *,
    resource_type: str,
    resource_id: int | None,
    resource_name: str,
    route_path: str | None,
    step_no: int | None = None,
) -> dict[str, Any]:
    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_name": resource_name,
        "route_path": route_path,
        "step_no": step_no,
    }


def _system_repair_target() -> dict[str, Any]:
    return _repair_target(
        resource_type="system",
        resource_id=None,
        resource_name="平台运行环境",
        route_path=None,
        step_no=None,
    )


def create_report_artifact(
    db: Session,
    *,
    report: RunReport,
    media: MediaObject,
    artifact_type: str,
    case_run_id: int | None = None,
    step_result_id: int | None = None,
) -> ReportArtifact:
    artifact = ReportArtifact(
        report_id=report.id,
        artifact_type=artifact_type,
        media_object_id=media.id,
        case_run_id=case_run_id,
        step_result_id=step_result_id,
        artifact_url=_media_content_url(media.id),
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


def refresh_report_artifact_summary(db: Session, report: RunReport) -> None:
    artifact_rows = db.scalars(
        select(ReportArtifact).where(ReportArtifact.report_id == report.id)
    ).all()
    by_type: dict[str, int] = {}
    for artifact in artifact_rows:
        by_type[artifact.artifact_type] = by_type.get(artifact.artifact_type, 0) + 1
    summary_json = dict(report.summary_json or {})
    summary_json["artifacts"] = {
        "total": len(artifact_rows),
        "by_type": by_type,
    }
    report.summary_json = summary_json
    db.commit()
    db.refresh(report)


def media_content_url(media_object_id: int) -> str:
    return _media_content_url(media_object_id)


def _media_content_url(media_object_id: int) -> str:
    return f"{settings.api_v1_prefix}/media-objects/{media_object_id}/content"
