from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from app.workers.browser import BrowserStep
    from app.workers.vision import TemplateAssertionContext


def should_execute_branch_step(
    adapter,
    page,
    *,
    step: BrowserStep,
    steps: Sequence[BrowserStep],
    template_contexts: dict[int, TemplateAssertionContext],
) -> bool:
    parent_step_no = step.parent_step_no
    if parent_step_no is None:
        return True
    parent_step = next((item for item in steps if item.step_no == parent_step_no), None)
    if parent_step is None or parent_step.step_type != "conditional_branch":
        return False
    selected = select_matching_branch(
        adapter,
        page,
        payload=parent_step.payload_json or {},
        template_contexts=template_contexts,
    )
    if selected is None:
        return False
    selected_key = selected.get("branch_key")
    if selected_key is None and selected.get("condition") is None:
        selected_key = "else"
    return step.branch_key == selected_key


def select_matching_branch(
    adapter,
    page,
    *,
    payload: dict,
    template_contexts: dict[int, TemplateAssertionContext],
) -> dict | None:
    branches = (
        payload.get("branches") if isinstance(payload.get("branches"), list) else []
    )
    for branch in branches:
        if not isinstance(branch, dict):
            continue
        if evaluate_branch_condition(
            adapter,
            page,
            condition=branch.get("condition"),
            template_contexts=template_contexts,
        ):
            return branch
    else_branch = payload.get("else_branch")
    if isinstance(else_branch, dict) and else_branch.get("enabled") is True:
        return {
            "branch_key": "else",
            "branch_name": else_branch.get("branch_name") or "默认分支",
            "condition": None,
        }
    return None


def evaluate_branch_condition(
    adapter,
    page,
    *,
    condition: object,
    template_contexts: dict[int, TemplateAssertionContext],
) -> bool:
    if not isinstance(condition, dict):
        raise ValueError("conditional_branch requires condition object.")
    condition_type = condition.get("type")
    if condition_type == "selector_exists":
        selector = condition.get("selector")
        if not isinstance(selector, str) or not selector.strip():
            raise ValueError("selector_exists requires selector.")
        return page.locator(selector).count() > 0
    if condition_type == "ocr_text_visible":
        expected_text = condition.get("expected_text")
        if not isinstance(expected_text, str) or not expected_text.strip():
            raise ValueError("ocr_text_visible requires expected_text.")
        screenshot_bytes = page.screenshot(type="png", full_page=False)
        try:
            adapter._vision_adapter.locate_by_ocr(
                image_png_bytes=screenshot_bytes,
                target_text=expected_text.strip(),
                match_mode=condition.get("match_mode", "contains"),
                case_sensitive=bool(condition.get("case_sensitive", False)),
                occurrence=1,
            )
            return True
        except RuntimeError:
            return False
    if condition_type == "template_visible":
        template_id = condition.get("template_id")
        if isinstance(template_id, bool) or not isinstance(template_id, int):
            raise ValueError("template_visible requires template_id.")
        if template_id not in template_contexts:
            raise ValueError("Template condition context is missing.")
        screenshot_bytes = page.screenshot(type="png", full_page=True)
        threshold_override = condition.get("threshold")
        try:
            adapter._vision_adapter.locate_by_template(
                context=template_contexts[template_id],
                actual_png_bytes=screenshot_bytes,
                threshold_override=float(threshold_override)
                if isinstance(threshold_override, (int, float, Decimal))
                else None,
            )
            return True
        except RuntimeError:
            return False
    raise ValueError("conditional_branch condition type is not supported.")
