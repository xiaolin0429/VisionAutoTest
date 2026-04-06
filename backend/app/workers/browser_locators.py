from __future__ import annotations

from typing import TYPE_CHECKING

from app.workers.browser_payloads import optional_ratio, payload_float
from app.workers.vision import OcrLocateResult, TemplateLocateResult

if TYPE_CHECKING:
    from app.workers.vision import TemplateAssertionContext


def uses_visual_locator(payload: dict) -> bool:
    return payload.get("locator") in {"ocr", "visual"}


def is_ocr_locator(payload: dict) -> bool:
    return payload.get("locator") == "ocr"


def is_visual_template_locator(payload: dict) -> bool:
    return payload.get("locator") == "visual"


def resolve_interaction_target(
    adapter,
    page,
    payload: dict,
    *,
    template_contexts: dict[int, TemplateAssertionContext],
):
    if is_ocr_locator(payload):
        return resolve_ocr_target(adapter, page, payload)
    if is_visual_template_locator(payload):
        return resolve_visual_target(
            adapter,
            page,
            payload,
            template_contexts=template_contexts,
        )
    raise ValueError("Unsupported interaction locator.")


def resolve_ocr_target(adapter, page, payload: dict) -> OcrLocateResult:
    ocr_text = payload.get("ocr_text")
    if not isinstance(ocr_text, str) or not ocr_text.strip():
        raise ValueError("OCR locator requires `ocr_text` in payload.")
    match_mode = payload.get("ocr_match_mode", "contains")
    case_sensitive = payload.get("ocr_case_sensitive", False)
    occurrence = payload.get("ocr_occurrence", 1)
    screenshot_bytes = page.screenshot(type="png", full_page=False)
    return adapter._vision_adapter.locate_by_ocr(
        image_png_bytes=screenshot_bytes,
        target_text=ocr_text.strip(),
        match_mode=match_mode,
        case_sensitive=bool(case_sensitive),
        occurrence=int(occurrence),
    )


def resolve_visual_target(
    adapter,
    page,
    payload: dict,
    *,
    template_contexts: dict[int, TemplateAssertionContext],
) -> TemplateLocateResult:
    template_id = payload.get("template_id")
    if isinstance(template_id, bool) or not isinstance(template_id, int):
        raise ValueError("visual locator requires `template_id` in payload.")
    if template_id not in template_contexts:
        raise ValueError("Visual locator template context is missing.")

    threshold_override = payload.get("threshold")
    if threshold_override is not None:
        threshold_override = payload_float(payload, "threshold")

    screenshot_bytes = page.screenshot(type="png", full_page=True)
    return adapter._vision_adapter.locate_by_template(
        context=template_contexts[template_id],
        actual_png_bytes=screenshot_bytes,
        threshold_override=threshold_override,
    )


def resolve_visual_anchor_point(adapter, payload: dict, target):
    if isinstance(target, OcrLocateResult):
        return adapter._interaction_point_cls(x=target.center_x, y=target.center_y)

    anchor_x_ratio = optional_ratio(payload, "anchor_x_ratio", default=0.5)
    anchor_y_ratio = optional_ratio(payload, "anchor_y_ratio", default=0.5)
    return adapter._interaction_point_cls(
        x=target.rect_x + (target.rect_width * anchor_x_ratio),
        y=target.rect_y + (target.rect_height * anchor_y_ratio),
    )
