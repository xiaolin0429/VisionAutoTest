from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.models import Template
from app.services.step_validation_common import assert_template


def validate_conditional_branch_payload(
    db: Session, *, workspace_id: int, payload: dict
) -> None:
    branches = payload.get("branches")
    if not isinstance(branches, list) or not branches:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="conditional_branch step requires payload_json.branches.",
            status_code=422,
        )
    if len(branches) > 3:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="conditional_branch step supports at most 3 branches.",
            status_code=422,
        )

    seen_branch_keys: set[str] = set()
    for branch in branches:
        if not isinstance(branch, dict):
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="conditional_branch branches must be objects.",
                status_code=422,
            )
        branch_key = branch.get("branch_key")
        if not isinstance(branch_key, str) or not branch_key.strip():
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="conditional_branch branch requires branch_key.",
                status_code=422,
            )
        if branch_key in seen_branch_keys:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="conditional_branch branch_key must be unique.",
                status_code=422,
            )
        seen_branch_keys.add(branch_key)
        validate_branch_condition(
            db, workspace_id=workspace_id, condition=branch.get("condition")
        )
        validate_branch_steps(db, workspace_id=workspace_id, steps=branch.get("steps"))

    else_branch = payload.get("else_branch")
    if else_branch is None:
        return
    if not isinstance(else_branch, dict):
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="conditional_branch else_branch must be an object.",
            status_code=422,
        )
    if else_branch.get("enabled") is True:
        validate_branch_steps(
            db,
            workspace_id=workspace_id,
            steps=else_branch.get("steps"),
        )


def validate_branch_condition(
    db: Session, *, workspace_id: int, condition: object
) -> None:
    if not isinstance(condition, dict):
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="conditional_branch branch requires condition object.",
            status_code=422,
        )

    condition_type = condition.get("type")
    if condition_type == "ocr_text_visible":
        expected_text = condition.get("expected_text")
        if not isinstance(expected_text, str) or not expected_text.strip():
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="ocr_text_visible requires expected_text.",
                status_code=422,
            )
        match_mode = condition.get("match_mode")
        if match_mode is not None and match_mode not in {"exact", "contains"}:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="ocr_text_visible match_mode must be `exact` or `contains`.",
                status_code=422,
            )
        case_sensitive = condition.get("case_sensitive")
        if case_sensitive is not None and not isinstance(case_sensitive, bool):
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="ocr_text_visible case_sensitive must be boolean.",
                status_code=422,
            )
        return

    if condition_type == "template_visible":
        template_id = condition.get("template_id")
        if isinstance(template_id, bool) or not isinstance(template_id, int):
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="template_visible requires template_id.",
                status_code=422,
            )
        assert_template(db, workspace_id, template_id)
        template = db.get(Template, template_id)
        assert template is not None
        if template.current_baseline_revision_id is None:
            raise ApiError(
                code="BASELINE_REVISION_REQUIRED",
                message="template_visible requires template current baseline revision.",
                status_code=422,
            )
        threshold = condition.get("threshold")
        if threshold is not None and (
            isinstance(threshold, bool) or not isinstance(threshold, (int, float))
        ):
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="template_visible threshold must be numeric.",
                status_code=422,
            )
        if isinstance(threshold, (int, float)) and not (0 <= float(threshold) <= 1):
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="template_visible threshold must be between 0 and 1.",
                status_code=422,
            )
        return

    if condition_type == "selector_exists":
        selector = condition.get("selector")
        if not isinstance(selector, str) or not selector.strip():
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="selector_exists requires selector.",
                status_code=422,
            )
        return

    raise ApiError(
        code="STEP_CONFIGURATION_INVALID",
        message="conditional_branch condition type is not supported.",
        status_code=422,
    )


def validate_branch_steps(db: Session, *, workspace_id: int, steps: object) -> None:
    if not isinstance(steps, list) or not steps:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="conditional_branch branch requires non-empty steps.",
            status_code=422,
        )

    from app.services.step_payload_validator import validate_step_payload

    for index, raw_step in enumerate(steps, start=1):
        if not isinstance(raw_step, dict):
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="conditional_branch branch step must be an object.",
                status_code=422,
            )
        step_type = raw_step.get("step_type")
        if step_type in {"component_call", "conditional_branch"}:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message=f"conditional_branch branch step {index} does not support {step_type}.",
                status_code=422,
            )
        if (
            not isinstance(raw_step.get("step_name"), str)
            or not raw_step.get("step_name", "").strip()
        ):
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message=f"conditional_branch branch step {index} requires step_name.",
                status_code=422,
            )
        validate_step_payload(
            db,
            workspace_id=workspace_id,
            item={
                "step_type": step_type,
                "step_name": raw_step.get("step_name"),
                "template_id": raw_step.get("template_id"),
                "component_id": raw_step.get("component_id"),
                "payload_json": raw_step.get("payload_json") or {},
                "timeout_ms": raw_step.get("timeout_ms", 15000),
                "retry_times": raw_step.get("retry_times", 0),
            },
            allow_component_call=False,
        )
