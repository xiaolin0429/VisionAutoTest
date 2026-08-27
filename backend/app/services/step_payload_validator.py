from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.models import Template
from app.services.assets import SUPPORTED_TEMPLATE_MATCH_STRATEGIES
from app.services.branch_validator import validate_conditional_branch_payload
from app.services.step_validation_common import (
    SUPPORTED_INPUT_MODES,
    SUPPORTED_LOCATOR_TYPES,
    SUPPORTED_LONG_PRESS_BUTTONS,
    SUPPORTED_NAVIGATE_WAIT_UNTIL,
    SUPPORTED_SCROLL_BEHAVIORS,
    SUPPORTED_SCROLL_DIRECTIONS,
    SUPPORTED_SCROLL_TARGETS,
    SUPPORTED_STEP_TYPES,
    assert_template,
    validate_select_option_payload,
)
from app.workers.ocr_contract import (
    OcrContractError,
    normalize_ocr_assert_payload,
    normalize_ocr_target_payload,
)


def validate_step_payload(
    db: Session, *, workspace_id: int, item: dict, allow_component_call: bool
) -> None:
    step_type = item.get("step_type")
    payload = item.get("payload_json") or {}
    template_id = item.get("template_id")

    if step_type not in SUPPORTED_STEP_TYPES:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message=f"Unsupported step_type: {step_type}.",
            status_code=422,
        )

    if step_type == "conditional_branch":
        if not allow_component_call:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="conditional_branch is not supported inside component steps.",
                status_code=422,
            )
        validate_conditional_branch_payload(
            db, workspace_id=workspace_id, payload=payload
        )
        return

    if step_type == "component_call":
        if not allow_component_call:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="component_call is not supported inside component steps.",
                status_code=422,
            )
        if item.get("component_id") is None:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="component_call step requires component_id.",
                status_code=422,
            )
        return

    if step_type == "select_option":
        if template_id is not None:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="select_option does not allow template_id fallback.",
                status_code=422,
            )
        try:
            validate_select_option_payload(payload)
        except OcrContractError as exc:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message=f"Invalid select_option payload: {exc}",
                status_code=422,
            ) from exc
        return

    if template_id is not None:
        assert_template(db, workspace_id, template_id)
        template = db.get(Template, template_id)
        assert template is not None
        if template.match_strategy not in SUPPORTED_TEMPLATE_MATCH_STRATEGIES:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="Referenced template match_strategy is not supported in the current version.",
                status_code=422,
            )

    if payload.get("locator") == "visual":
        visual_template_id = payload.get("template_id")
        if isinstance(visual_template_id, bool) or not isinstance(
            visual_template_id, int
        ):
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="visual locator requires payload_json.template_id.",
                status_code=422,
            )
        assert_template(db, workspace_id, visual_template_id)
        visual_template = db.get(Template, visual_template_id)
        assert visual_template is not None
        if visual_template.current_baseline_revision_id is None:
            raise ApiError(
                code="BASELINE_REVISION_REQUIRED",
                message="visual locator requires template current baseline revision.",
                status_code=422,
            )

    if step_type == "template_assert":
        if template_id is None:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="template_assert step requires template_id.",
                status_code=422,
            )
        template = db.get(Template, template_id)
        assert template is not None
        if template.match_strategy != "template":
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="template_assert step requires template match_strategy `template`.",
                status_code=422,
            )
        threshold = payload.get("threshold")
        if threshold is not None and (
            isinstance(threshold, bool) or not isinstance(threshold, (int, float))
        ):
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="template_assert threshold must be numeric.",
                status_code=422,
            )
        if isinstance(threshold, (int, float)) and not (0 <= float(threshold) <= 1):
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="template_assert threshold must be between 0 and 1.",
                status_code=422,
            )
        return

    if step_type == "ocr_assert":
        try:
            normalize_ocr_assert_payload(payload)
        except OcrContractError as exc:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message=f"Invalid ocr_assert payload: {exc}",
                status_code=422,
            ) from exc
        if template_id is not None:
            template = db.get(Template, template_id)
            assert template is not None
            if template.match_strategy != "ocr":
                raise ApiError(
                    code="STEP_CONFIGURATION_INVALID",
                    message="ocr_assert step requires template match_strategy `ocr`.",
                    status_code=422,
                )
        return

    if step_type == "click":
        validate_interaction_locator(payload, step_type, require_selector=True)
        return

    if step_type == "input":
        validate_interaction_locator(payload, step_type, require_selector=True)
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="input step requires payload_json.text.",
                status_code=422,
            )
        input_mode = payload.get("input_mode")
        if input_mode is not None and input_mode not in SUPPORTED_INPUT_MODES:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="input input_mode must be `fill`, `type`, or `otp`.",
                status_code=422,
            )

        otp_length = payload.get("otp_length")
        if otp_length is not None:
            if (
                isinstance(otp_length, bool)
                or not isinstance(otp_length, int)
                or otp_length < 1
            ):
                raise ApiError(
                    code="STEP_CONFIGURATION_INVALID",
                    message="input otp_length must be a positive integer.",
                    status_code=422,
                )

        per_char_delay_ms = payload.get("per_char_delay_ms")
        if per_char_delay_ms is not None:
            if (
                isinstance(per_char_delay_ms, bool)
                or not isinstance(per_char_delay_ms, (int, float))
                or float(per_char_delay_ms) < 0
            ):
                raise ApiError(
                    code="STEP_CONFIGURATION_INVALID",
                    message="input per_char_delay_ms must be a numeric value greater than or equal to 0.",
                    status_code=422,
                )
        return

    if step_type == "navigate":
        validate_navigate_payload(payload)
        return

    if step_type == "scroll":
        validate_scroll_payload(payload)
        return

    if step_type == "long_press":
        validate_long_press_payload(payload)


def validate_navigate_payload(payload: dict) -> None:
    url = payload.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="navigate step requires payload_json.url.",
            status_code=422,
        )
    parsed_url = urlparse(url)
    if parsed_url.scheme:
        if parsed_url.scheme not in {"http", "https"}:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="navigate url must be an absolute http/https URL or a path starting with `/`.",
                status_code=422,
            )
    elif not url.startswith("/"):
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="navigate url must be an absolute http/https URL or a path starting with `/`.",
            status_code=422,
        )

    wait_until = payload.get("wait_until")
    if wait_until is not None and wait_until not in SUPPORTED_NAVIGATE_WAIT_UNTIL:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="navigate wait_until must be `load`, `domcontentloaded`, or `networkidle`.",
            status_code=422,
        )


def validate_scroll_payload(payload: dict) -> None:
    target = payload.get("target")
    if target not in SUPPORTED_SCROLL_TARGETS:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="scroll target must be `page` or `element`.",
            status_code=422,
        )

    if target == "element":
        validate_interaction_locator(payload, "scroll", require_selector=True)

    direction = payload.get("direction")
    if direction not in SUPPORTED_SCROLL_DIRECTIONS:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="scroll direction must be `up`, `down`, `left`, or `right`.",
            status_code=422,
        )

    distance = payload.get("distance")
    if (
        isinstance(distance, bool)
        or not isinstance(distance, (int, float))
        or float(distance) <= 0
    ):
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="scroll distance must be a numeric value greater than 0.",
            status_code=422,
        )

    behavior = payload.get("behavior")
    if behavior is not None and behavior not in SUPPORTED_SCROLL_BEHAVIORS:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="scroll behavior must be `auto` or `smooth`.",
            status_code=422,
        )


def validate_long_press_payload(payload: dict) -> None:
    validate_interaction_locator(payload, "long_press", require_selector=True)

    duration_ms = payload.get("duration_ms")
    if (
        isinstance(duration_ms, bool)
        or not isinstance(duration_ms, (int, float))
        or float(duration_ms) <= 0
    ):
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="long_press duration_ms must be a numeric value greater than 0.",
            status_code=422,
        )

    button = payload.get("button")
    if button is not None and button not in SUPPORTED_LONG_PRESS_BUTTONS:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="long_press button currently only supports `left`.",
            status_code=422,
        )


def validate_interaction_locator(
    payload: dict, step_type: str, *, require_selector: bool
) -> None:
    locator_type = payload.get("locator", "selector")
    if locator_type not in SUPPORTED_LOCATOR_TYPES:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message=f"{step_type} locator must be `selector`, `ocr`, or `visual`.",
            status_code=422,
        )

    if locator_type == "ocr":
        validate_ocr_locator_fields(payload, step_type)
    elif locator_type == "visual":
        validate_visual_locator_fields(payload, step_type)
    elif require_selector:
        selector = payload.get("selector")
        if not isinstance(selector, str) or not selector.strip():
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message=f"{step_type} step requires payload_json.selector.",
                status_code=422,
            )


def validate_ocr_locator_fields(payload: dict, step_type: str) -> None:
    try:
        normalize_ocr_target_payload(payload)
    except OcrContractError as exc:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message=f"Invalid {step_type} OCR locator payload: {exc}",
            status_code=422,
        ) from exc


def validate_visual_locator_fields(payload: dict, step_type: str) -> None:
    template_id = payload.get("template_id")
    if (
        isinstance(template_id, bool)
        or not isinstance(template_id, int)
        or template_id < 1
    ):
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message=f"{step_type} step with visual locator requires payload_json.template_id.",
            status_code=422,
        )

    threshold = payload.get("threshold")
    if threshold is not None and (
        isinstance(threshold, bool) or not isinstance(threshold, (int, float))
    ):
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message=f"{step_type} visual locator threshold must be numeric.",
            status_code=422,
        )

    if isinstance(threshold, (int, float)) and not (0 <= float(threshold) <= 1):
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message=f"{step_type} visual locator threshold must be between 0 and 1.",
            status_code=422,
        )

    for key in ("anchor_x_ratio", "anchor_y_ratio"):
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message=f"{step_type} visual locator {key} must be numeric.",
                status_code=422,
            )
        if not (0 <= float(value) <= 1):
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message=f"{step_type} visual locator {key} must be between 0 and 1.",
                status_code=422,
            )
