from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.models import (
    BaselineRevision,
    ComponentStep,
    DeviceProfile,
    EnvironmentProfile,
    Template,
    TestCase,
    TestCaseStep,
    TestSuite,
    SuiteCase,
    User,
)
from app.services.branch_validator import validate_conditional_branch_payload
from app.services.execution_steps import get_component_in_workspace
from app.services.helpers import count_total, require_workspace_access
from app.services.workspace import (
    validate_device_profile_dimensions,
    validate_environment_base_url,
)
from app.services.step_validation_common import validate_select_option_payload
from app.workers.ocr_contract import (
    OcrContractError,
    normalize_ocr_assert_payload,
    normalize_ocr_branch_condition,
)

EXECUTABLE_TEMPLATE_STATUS = "published"


def get_workspace_execution_readiness(
    db: Session,
    *,
    user: User,
    workspace_id: int,
) -> dict[str, Any]:
    require_workspace_access(db, user, workspace_id)
    active_environment_count = count_active_environment_profiles(
        db, workspace_id=workspace_id
    )
    active_suites = db.scalars(
        select(TestSuite).where(
            TestSuite.workspace_id == workspace_id,
            TestSuite.is_deleted.is_(False),
            TestSuite.status == "active",
        )
    ).all()

    issues: list[dict[str, Any]] = []
    if active_environment_count == 0:
        issues.append(
            build_readiness_issue(
                code="ENVIRONMENT_PROFILE_REQUIRED",
                message="当前工作空间缺少可用环境，无法触发执行。",
                resource_type="environment_profile",
                route_path="/environments",
            )
        )
    if not active_suites:
        issues.append(
            build_readiness_issue(
                code="TEST_SUITE_REQUIRED",
                message="当前工作空间缺少活跃套件，至少需要一个 active 套件。",
                resource_type="test_suite",
                route_path="/suites",
            )
        )

    for suite in active_suites:
        issues.extend(inspect_test_suite_execution_issues(db, suite=suite))

    normalized_issues = dedupe_readiness_issues(issues)
    return {
        "scope": "workspace",
        "status": "ready" if not normalized_issues else "blocked",
        "workspace_id": workspace_id,
        "test_suite_id": None,
        "active_environment_count": active_environment_count,
        "active_test_suite_count": len(active_suites),
        "blocking_issue_count": len(normalized_issues),
        "issues": normalized_issues,
    }


def get_test_suite_execution_readiness(
    db: Session,
    *,
    user: User,
    test_suite: TestSuite,
    environment_profile_id: int | None = None,
    device_profile_id: int | None = None,
) -> dict[str, Any]:
    require_workspace_access(db, user, test_suite.workspace_id)
    active_environment_count = count_active_environment_profiles(
        db, workspace_id=test_suite.workspace_id
    )
    active_suite_stmt = select(TestSuite).where(
        TestSuite.workspace_id == test_suite.workspace_id,
        TestSuite.is_deleted.is_(False),
        TestSuite.status == "active",
    )
    active_test_suite_count: int = count_total(db, active_suite_stmt)
    issues: list[dict[str, Any]] = []
    if environment_profile_id is None and active_environment_count == 0:
        issues.append(
            build_readiness_issue(
                code="ENVIRONMENT_PROFILE_REQUIRED",
                message="当前工作空间缺少可用环境，无法触发执行。",
                resource_type="environment_profile",
                route_path="/environments",
            )
        )
    if environment_profile_id is not None:
        issues.extend(
            inspect_execution_environment_issues(
                db,
                workspace_id=test_suite.workspace_id,
                environment_profile_id=environment_profile_id,
            )
        )
        if device_profile_id is not None:
            issues.extend(
                inspect_execution_device_issues(
                    db,
                    workspace_id=test_suite.workspace_id,
                    device_profile_id=device_profile_id,
                )
            )
    issues.extend(inspect_test_suite_execution_issues(db, suite=test_suite))
    normalized_issues = dedupe_readiness_issues(issues)
    return {
        "scope": "execution_selection"
        if environment_profile_id is not None
        else "test_suite",
        "status": "ready" if not normalized_issues else "blocked",
        "workspace_id": test_suite.workspace_id,
        "test_suite_id": test_suite.id,
        "environment_profile_id": environment_profile_id,
        "device_profile_id": device_profile_id
        if environment_profile_id is not None
        else None,
        "active_environment_count": active_environment_count,
        "active_test_suite_count": int(active_test_suite_count or 0),
        "blocking_issue_count": len(normalized_issues),
        "issues": normalized_issues,
    }


def inspect_execution_environment_issues(
    db: Session, *, workspace_id: int, environment_profile_id: int
) -> list[dict[str, Any]]:
    """Collect selection-level blockers for one explicitly selected environment."""
    profile = db.get(EnvironmentProfile, environment_profile_id)
    if profile is None or profile.workspace_id != workspace_id or profile.is_deleted:
        return [
            build_readiness_issue(
                code="ENVIRONMENT_PROFILE_NOT_FOUND",
                message="所选执行环境不存在或不属于当前工作空间。",
                resource_type="environment_profile",
                resource_id=environment_profile_id,
                route_path="/environments",
            )
        ]
    if profile.status != "active":
        return [
            build_readiness_issue(
                code="ENVIRONMENT_PROFILE_NOT_ACTIVE",
                message="所选执行环境未启用，无法触发执行。",
                resource_type="environment_profile",
                resource_id=profile.id,
                resource_name=profile.profile_name,
                route_path="/environments",
            )
        ]
    try:
        validate_environment_base_url(profile.base_url)
    except ApiError:
        return [
            build_readiness_issue(
                code="ENVIRONMENT_BASE_URL_INVALID",
                message="执行环境地址无效，请填写包含 http:// 或 https:// 的完整地址。",
                resource_type="environment_profile",
                resource_id=profile.id,
                resource_name=profile.profile_name,
                route_path="/environments",
            )
        ]
    return []


def inspect_execution_device_issues(
    db: Session, *, workspace_id: int, device_profile_id: int
) -> list[dict[str, Any]]:
    """Collect selection-level blockers for one explicitly selected device profile."""
    profile = db.get(DeviceProfile, device_profile_id)
    if profile is None or profile.workspace_id != workspace_id or profile.is_deleted:
        return [
            build_readiness_issue(
                code="DEVICE_PROFILE_INVALID",
                message="所选设备档案不存在或不属于当前工作空间。",
                resource_type="device_profile",
                resource_id=device_profile_id,
                route_path="/environments",
            )
        ]
    try:
        validate_device_profile_dimensions(
            viewport_width=profile.viewport_width,
            viewport_height=profile.viewport_height,
            device_scale_factor=float(profile.device_scale_factor),
        )
    except ApiError:
        return [
            build_readiness_issue(
                code="DEVICE_PROFILE_INVALID",
                message="所选设备档案参数无效，视口宽高和缩放因子必须为正数。",
                resource_type="device_profile",
                resource_id=profile.id,
                resource_name=profile.profile_name,
                route_path="/environments",
            )
        ]
    return []


def validate_case_execution_readiness(
    db: Session, *, workspace_id: int, test_case_id: int
) -> None:
    test_case = db.get(TestCase, test_case_id)
    if (
        test_case is None
        or test_case.workspace_id != workspace_id
        or test_case.is_deleted
    ):
        raise ApiError(
            code="TEST_CASE_NOT_FOUND", message="Test case not found.", status_code=404
        )
    if test_case.status != "published":
        raise ApiError(
            code="PUBLISHED_VERSION_REQUIRED",
            message="Test case must be published before execution.",
            status_code=422,
        )

    case_steps = db.scalars(
        select(TestCaseStep)
        .where(TestCaseStep.test_case_id == test_case_id)
        .order_by(TestCaseStep.step_no.asc())
    ).all()
    for case_step in case_steps:
        validate_visual_step_readiness(db, workspace_id=workspace_id, step=case_step)
        if case_step.component_id is None:
            continue
        component = get_component_in_workspace(
            db, workspace_id=workspace_id, component_id=case_step.component_id
        )
        if component.status != "published":
            raise ApiError(
                code="PUBLISHED_VERSION_REQUIRED",
                message="Component must be published before execution.",
                status_code=422,
            )
        component_steps = db.scalars(
            select(ComponentStep)
            .where(ComponentStep.component_id == component.id)
            .order_by(ComponentStep.step_no.asc())
        ).all()
        for component_step in component_steps:
            validate_visual_step_readiness(
                db, workspace_id=workspace_id, step=component_step
            )


def validate_visual_step_readiness(db: Session, *, workspace_id: int, step) -> None:
    if step.step_type == "conditional_branch":
        payload = step.payload_json or {}
        validate_conditional_branch_payload(
            db,
            workspace_id=workspace_id,
            payload=payload,
        )
        branches = payload["branches"]
        for branch in branches:
            _validate_branch_step_readiness(
                db,
                workspace_id=workspace_id,
                branch=branch,
            )
        else_branch = payload.get("else_branch")
        if isinstance(else_branch, dict) and else_branch.get("enabled") is True:
            _validate_branch_step_readiness(
                db,
                workspace_id=workspace_id,
                branch={"condition": None, "steps": else_branch.get("steps")},
            )
        return

    if step.step_type == "select_option":
        if step.template_id is not None:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="select_option does not allow template_id fallback.",
                status_code=422,
            )
        try:
            validate_select_option_payload(step.payload_json or {})
        except OcrContractError as exc:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message=f"Invalid select_option payload: {exc}",
                status_code=422,
            ) from exc
        return

    if step.step_type not in {"template_assert", "ocr_assert"}:
        return

    if step.step_type == "template_assert" and step.template_id is None:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="template_assert step requires template_id.",
            status_code=422,
        )

    if step.step_type == "ocr_assert":
        try:
            normalize_ocr_assert_payload(step.payload_json or {})
        except OcrContractError as exc:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message=f"Invalid ocr_assert payload: {exc}",
                status_code=422,
            ) from exc

    if step.template_id is None:
        return

    template = db.get(Template, step.template_id)
    if template is None or template.workspace_id != workspace_id or template.is_deleted:
        raise ApiError(
            code="TEMPLATE_NOT_FOUND", message="Template not found.", status_code=404
        )
    if template.status != EXECUTABLE_TEMPLATE_STATUS:
        raise ApiError(
            code="PUBLISHED_VERSION_REQUIRED",
            message="Template must be published before execution.",
            status_code=422,
        )

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


def inspect_test_suite_execution_issues(
    db: Session, *, suite: TestSuite
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if suite.status != "active":
        issues.append(
            build_readiness_issue(
                code="TEST_SUITE_NOT_ACTIVE",
                message="当前套件状态不是 active，不能直接触发执行。",
                resource_type="test_suite",
                resource_id=suite.id,
                resource_name=suite.suite_name,
                route_path="/suites",
            )
        )

    suite_cases = db.scalars(
        select(SuiteCase)
        .where(SuiteCase.test_suite_id == suite.id)
        .order_by(SuiteCase.sort_order.asc())
    ).all()
    if not suite_cases:
        issues.append(
            build_readiness_issue(
                code="TEST_SUITE_EMPTY",
                message="当前套件为空，至少需要一个可执行用例。",
                resource_type="test_suite",
                resource_id=suite.id,
                resource_name=suite.suite_name,
                route_path="/suites",
            )
        )
        return issues

    for suite_case in suite_cases:
        test_case = db.get(TestCase, suite_case.test_case_id)
        if (
            test_case is None
            or test_case.workspace_id != suite.workspace_id
            or test_case.is_deleted
        ):
            issues.append(
                build_readiness_issue(
                    code="TEST_CASE_NOT_FOUND",
                    message=f"套件引用了不存在的测试用例 #{suite_case.test_case_id}。",
                    resource_type="test_case",
                    resource_id=suite_case.test_case_id,
                    route_path="/cases",
                )
            )
            continue
        if test_case.status != "published":
            issues.append(
                build_readiness_issue(
                    code="PUBLISHED_VERSION_REQUIRED",
                    message=f"测试用例 {test_case.case_name} 尚未发布，无法执行。",
                    resource_type="test_case",
                    resource_id=test_case.id,
                    resource_name=test_case.case_name,
                    route_path="/cases",
                )
            )
        issues.extend(
            inspect_test_case_execution_issues(
                db,
                workspace_id=suite.workspace_id,
                test_case=test_case,
            )
        )
    return issues


def inspect_test_case_execution_issues(
    db: Session,
    *,
    workspace_id: int,
    test_case: TestCase,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    case_steps = db.scalars(
        select(TestCaseStep)
        .where(TestCaseStep.test_case_id == test_case.id)
        .order_by(TestCaseStep.step_no.asc())
    ).all()
    for case_step in case_steps:
        issues.extend(
            inspect_execution_step_issues(
                db,
                workspace_id=workspace_id,
                step=case_step,
                route_path="/cases",
            )
        )
        if case_step.component_id is None:
            continue
        component = get_component_in_workspace(
            db,
            workspace_id=workspace_id,
            component_id=case_step.component_id,
        )
        if component.status != "published":
            issues.append(
                build_readiness_issue(
                    code="PUBLISHED_VERSION_REQUIRED",
                    message=f"组件 {component.component_name} 尚未发布，无法执行。",
                    resource_type="component",
                    resource_id=component.id,
                    resource_name=component.component_name,
                    route_path="/components",
                )
            )
        component_steps = db.scalars(
            select(ComponentStep)
            .where(ComponentStep.component_id == component.id)
            .order_by(ComponentStep.step_no.asc())
        ).all()
        for component_step in component_steps:
            issues.extend(
                inspect_execution_step_issues(
                    db,
                    workspace_id=workspace_id,
                    step=component_step,
                    route_path="/components",
                )
            )
    return issues


def inspect_execution_step_issues(
    db: Session,
    *,
    workspace_id: int,
    step,
    route_path: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if step.step_type == "conditional_branch":
        payload = step.payload_json or {}
        try:
            validate_conditional_branch_payload(
                db,
                workspace_id=workspace_id,
                payload=payload,
            )
        except ApiError as exc:
            if exc.code == "STEP_CONFIGURATION_INVALID":
                issues.append(
                    build_readiness_issue(
                        code=exc.code,
                        message=f"步骤 {step.step_name} 的条件分支配置无效：{exc.message}",
                        resource_type="step",
                        route_path=route_path,
                    )
                )
                return issues
        branches = payload.get("branches")
        if not isinstance(branches, list) or not branches:
            issues.append(
                build_readiness_issue(
                    code="STEP_CONFIGURATION_INVALID",
                    message=f"步骤 {step.step_name} 缺少有效的条件分支配置。",
                    resource_type="step",
                    route_path=route_path,
                )
            )
            return issues
        for branch in branches:
            issues.extend(
                inspect_branch_payload_issues(
                    db,
                    workspace_id=workspace_id,
                    branch=branch,
                    step_name=step.step_name,
                    route_path=route_path,
                )
            )
        else_branch = payload.get("else_branch")
        if isinstance(else_branch, dict) and else_branch.get("enabled") is True:
            issues.extend(
                inspect_branch_payload_issues(
                    db,
                    workspace_id=workspace_id,
                    branch={"condition": None, "steps": else_branch.get("steps")},
                    step_name=step.step_name,
                    route_path=route_path,
                )
            )
        return issues
    if step.step_type == "select_option":
        try:
            if step.template_id is not None:
                raise OcrContractError(
                    "select_option does not allow template_id fallback."
                )
            validate_select_option_payload(step.payload_json or {})
        except OcrContractError as exc:
            issues.append(
                build_readiness_issue(
                    code="STEP_CONFIGURATION_INVALID",
                    message=f"步骤 {step.step_name} 的 OCR 选择配置无效：{exc}",
                    resource_type="step",
                    route_path=route_path,
                )
            )
        return issues
    if step.step_type == "template_assert" and step.template_id is None:
        issues.append(
            build_readiness_issue(
                code="STEP_CONFIGURATION_INVALID",
                message=f"步骤 {step.step_name} 缺少 template_id 配置。",
                resource_type="step",
                route_path=route_path,
            )
        )
        return issues

    if step.step_type == "ocr_assert":
        try:
            normalize_ocr_assert_payload(step.payload_json or {})
        except OcrContractError as exc:
            issues.append(
                build_readiness_issue(
                    code="STEP_CONFIGURATION_INVALID",
                    message=f"步骤 {step.step_name} 的 OCR 断言配置无效：{exc}",
                    resource_type="step",
                    route_path=route_path,
                )
            )
    if step.template_id is None:
        return issues

    template = db.get(Template, step.template_id)
    if template is None or template.workspace_id != workspace_id or template.is_deleted:
        issues.append(
            build_readiness_issue(
                code="TEMPLATE_NOT_FOUND",
                message=f"步骤 {step.step_name} 引用了不存在的模板 #{step.template_id}。",
                resource_type="template",
                resource_id=step.template_id,
                route_path="/templates",
            )
        )
        return issues
    if template.status != EXECUTABLE_TEMPLATE_STATUS:
        issues.append(
            build_readiness_issue(
                code="PUBLISHED_VERSION_REQUIRED",
                message=f"模板 {template.template_name} 尚未发布，无法执行。",
                resource_type="template",
                resource_id=template.id,
                resource_name=template.template_name,
                route_path="/templates",
            )
        )
    if template.current_baseline_revision_id is None:
        issues.append(
            build_readiness_issue(
                code="BASELINE_REVISION_REQUIRED",
                message=f"模板 {template.template_name} 缺少当前基准版本。",
                resource_type="template",
                resource_id=template.id,
                resource_name=template.template_name,
                route_path="/templates",
            )
        )
    else:
        baseline = db.get(BaselineRevision, template.current_baseline_revision_id)
        if baseline is None or baseline.template_id != template.id:
            issues.append(
                build_readiness_issue(
                    code="BASELINE_REVISION_REQUIRED",
                    message=f"模板 {template.template_name} 的当前基准版本无效。",
                    resource_type="template",
                    resource_id=template.id,
                    resource_name=template.template_name,
                    route_path="/templates",
                )
            )
    expected_strategy = "template" if step.step_type == "template_assert" else "ocr"
    if (
        step.step_type in {"template_assert", "ocr_assert"}
        and template.match_strategy != expected_strategy
    ):
        issues.append(
            build_readiness_issue(
                code="STEP_CONFIGURATION_INVALID",
                message=f"模板 {template.template_name} 与步骤 {step.step_name} 的断言策略不兼容。",
                resource_type="template",
                resource_id=template.id,
                resource_name=template.template_name,
                route_path="/templates",
            )
        )
    return issues


def inspect_branch_payload_issues(
    db: Session,
    *,
    workspace_id: int,
    branch: Any,
    step_name: str,
    route_path: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not isinstance(branch, dict):
        issues.append(
            build_readiness_issue(
                code="STEP_CONFIGURATION_INVALID",
                message=f"步骤 {step_name} 存在非法分支配置。",
                resource_type="step",
                route_path=route_path,
            )
        )
        return issues
    condition = branch.get("condition")
    if condition is not None and isinstance(condition, dict):
        condition_type = condition.get("type")
        if condition_type == "ocr_text_visible":
            try:
                normalize_ocr_branch_condition(condition)
            except OcrContractError as exc:
                issues.append(
                    build_readiness_issue(
                        code="STEP_CONFIGURATION_INVALID",
                        message=f"步骤 {step_name} 的 OCR 条件配置无效：{exc}",
                        resource_type="step",
                        route_path=route_path,
                    )
                )
        elif condition_type == "template_visible":
            template_id = condition.get("template_id")
            template = (
                db.get(Template, template_id) if isinstance(template_id, int) else None
            )
            if (
                template is None
                or template.workspace_id != workspace_id
                or template.is_deleted
            ):
                issues.append(
                    build_readiness_issue(
                        code="TEMPLATE_NOT_FOUND",
                        message=f"步骤 {step_name} 的条件分支引用了不存在的模板 #{template_id}。",
                        resource_type="template",
                        resource_id=template_id
                        if isinstance(template_id, int)
                        else None,
                        route_path="/templates",
                    )
                )
            elif template.current_baseline_revision_id is None:
                issues.append(
                    build_readiness_issue(
                        code="BASELINE_REVISION_REQUIRED",
                        message=f"步骤 {step_name} 的条件模板 {template.template_name} 缺少当前基准版本。",
                        resource_type="template",
                        resource_id=template.id,
                        resource_name=template.template_name,
                        route_path="/templates",
                    )
                )
    steps = branch.get("steps")
    if not isinstance(steps, list) or not steps:
        issues.append(
            build_readiness_issue(
                code="STEP_CONFIGURATION_INVALID",
                message=f"步骤 {step_name} 的分支缺少可执行子步骤。",
                resource_type="step",
                route_path=route_path,
            )
        )
        return issues
    for sub_step in steps:
        if not isinstance(sub_step, dict):
            issues.append(
                build_readiness_issue(
                    code="STEP_CONFIGURATION_INVALID",
                    message=f"步骤 {step_name} 的分支子步骤配置非法。",
                    resource_type="step",
                    route_path=route_path,
                )
            )
            continue
        sub_type = sub_step.get("step_type")
        if sub_type in {"component_call", "conditional_branch"}:
            issues.append(
                build_readiness_issue(
                    code="STEP_CONFIGURATION_INVALID",
                    message=f"步骤 {step_name} 的分支子步骤不支持 {sub_type}。",
                    resource_type="step",
                    route_path=route_path,
                )
            )
            continue
        pseudo_step = type(
            "BranchStep",
            (),
            sub_step
            | {
                "step_type": sub_type,
                "payload_json": sub_step.get("payload_json") or {},
                "template_id": sub_step.get("template_id"),
            },
        )
        issues.extend(
            inspect_execution_step_issues(
                db,
                workspace_id=workspace_id,
                step=pseudo_step,
                route_path=route_path,
            )
        )
    return issues


def _validate_branch_step_readiness(
    db: Session,
    *,
    workspace_id: int,
    branch: object,
) -> None:
    if not isinstance(branch, dict):
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="conditional_branch branches must be objects.",
            status_code=422,
        )
    steps = branch.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="conditional_branch branch requires non-empty steps.",
            status_code=422,
        )
    for raw_step in steps:
        if not isinstance(raw_step, dict):
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="conditional_branch branch steps must be objects.",
                status_code=422,
            )
        pseudo_step = type(
            "BranchStep",
            (),
            {
                "step_type": raw_step.get("step_type"),
                "payload_json": raw_step.get("payload_json") or {},
                "template_id": raw_step.get("template_id"),
            },
        )
        validate_visual_step_readiness(
            db,
            workspace_id=workspace_id,
            step=pseudo_step,
        )


def count_active_environment_profiles(db: Session, *, workspace_id: int) -> int:
    stmt = select(EnvironmentProfile).where(
        EnvironmentProfile.workspace_id == workspace_id,
        EnvironmentProfile.is_deleted.is_(False),
        EnvironmentProfile.status == "active",
    )
    return count_total(db, stmt)


def build_readiness_issue(
    *,
    code: str,
    message: str,
    resource_type: str,
    resource_id: int | None = None,
    resource_name: str | None = None,
    route_path: str | None = None,
    step_no: int | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_name": resource_name,
        "route_path": route_path,
        "step_no": step_no,
    }


def dedupe_readiness_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    normalized: list[dict[str, Any]] = []
    for issue in issues:
        identity = (
            issue["code"],
            issue["resource_type"],
            issue.get("resource_id"),
            issue.get("route_path"),
            issue.get("step_no"),
        )
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(issue)
    return normalized
