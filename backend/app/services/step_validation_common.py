from __future__ import annotations

from collections.abc import Mapping

from app.core.http import ApiError
from app.models import Template
from app.services.assets import SUPPORTED_TEMPLATE_MATCH_STRATEGIES
from app.workers.ocr_contract import (
    NormalizedSelectOptionPayload,
    OcrContractError,
    normalize_select_option_payload,
)

SUPPORTED_STEP_TYPES = {
    "wait",
    "click",
    "input",
    "select_option",
    "template_assert",
    "ocr_assert",
    "component_call",
    "navigate",
    "scroll",
    "long_press",
    "conditional_branch",
}
SUPPORTED_NAVIGATE_WAIT_UNTIL = {"load", "domcontentloaded", "networkidle"}
SUPPORTED_SCROLL_TARGETS = {"page", "element"}
SUPPORTED_SCROLL_DIRECTIONS = {"up", "down", "left", "right"}
SUPPORTED_SCROLL_BEHAVIORS = {"auto", "smooth"}
SUPPORTED_LONG_PRESS_BUTTONS = {"left"}
SUPPORTED_LOCATOR_TYPES = {"selector", "ocr", "visual"}
SUPPORTED_OCR_MATCH_MODES = {"exact", "contains"}
SUPPORTED_INPUT_MODES = {"fill", "type", "otp"}


def validate_select_option_payload(
    payload: object,
) -> NormalizedSelectOptionPayload:
    if not isinstance(payload, Mapping):
        raise OcrContractError("select_option payload must be an object.")
    return normalize_select_option_payload(payload)


def assert_template(db, workspace_id: int, template_id: int) -> None:
    template = db.get(Template, template_id)
    if template is None or template.workspace_id != workspace_id or template.is_deleted:
        raise ApiError(
            code="TEMPLATE_NOT_FOUND", message="Template not found.", status_code=404
        )
