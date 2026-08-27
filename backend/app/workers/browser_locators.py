from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.workers.browser_payloads import optional_ratio, payload_float
from app.workers.ocr_contract import normalize_ocr_target_payload
from app.workers.ocr_engine import OcrEngineError
from app.workers.ocr_evidence import (
    OcrResolutionEvidence,
    build_ocr_result_metadata,
)
from app.workers.ocr_session import PageOcrSession
from app.workers.ocr_targeting import OcrTargetingError
from app.workers.ocr_types import (
    OcrErrorCode,
    OcrPoint,
    OcrTargetResolution,
    OcrTargetSpec,
)
from app.workers.vision import OcrLocateResult, TemplateLocateResult

if TYPE_CHECKING:
    from app.workers.vision import TemplateAssertionContext


@dataclass(frozen=True, slots=True)
class OcrActionTarget:
    point: OcrPoint
    resolution: OcrTargetResolution
    evidence: OcrResolutionEvidence | None = None


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
    ocr_session: PageOcrSession | None,
):
    if is_ocr_locator(payload):
        return resolve_ocr_target(ocr_session, payload)
    if is_visual_template_locator(payload):
        return resolve_visual_target(
            adapter,
            page,
            payload,
            template_contexts=template_contexts,
        )
    raise ValueError("Unsupported interaction locator.")


def resolve_ocr_target(
    ocr_session: PageOcrSession | None,
    payload: dict,
) -> OcrActionTarget:
    if ocr_session is None:
        raise OcrEngineError(
            OcrErrorCode.OCR_ENGINE_UNAVAILABLE,
            "Pure OCR interaction requires a case-local PageOcrSession.",
        )

    target = normalize_ocr_target_payload(payload)
    resolution = ocr_session.resolve_for_action(target)
    candidate = resolution.selected_candidate
    if candidate is None:
        raise OcrEngineError(
            OcrErrorCode.OCR_ANALYSIS_FAILED,
            "OCR target resolution completed without a selected candidate.",
        )

    if target.action_point == "associated_control":
        rect = candidate.element.associated_control_rect
        if rect is None:
            raise OcrEngineError(
                OcrErrorCode.OCR_RELATION_NOT_SATISFIED,
                "Resolved OCR target has no associated visual control.",
            )
    else:
        rect = candidate.element.coordinates.viewport_css_rect

    evidence_getter = getattr(ocr_session, "evidence_for", None)
    evidence = evidence_getter(resolution) if callable(evidence_getter) else None
    return OcrActionTarget(
        point=OcrPoint(
            x=rect.x + rect.width / 2.0,
            y=rect.y + rect.height / 2.0,
        ),
        resolution=resolution,
        evidence=evidence,
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
    if isinstance(target, OcrActionTarget):
        return adapter._interaction_point_cls(x=target.point.x, y=target.point.y)
    if isinstance(target, OcrLocateResult):
        return adapter._interaction_point_cls(x=target.center_x, y=target.center_y)

    anchor_x_ratio = optional_ratio(payload, "anchor_x_ratio", default=0.5)
    anchor_y_ratio = optional_ratio(payload, "anchor_y_ratio", default=0.5)
    return adapter._interaction_point_cls(
        x=target.rect_x + (target.rect_width * anchor_x_ratio),
        y=target.rect_y + (target.rect_height * anchor_y_ratio),
    )


def build_ocr_error_metadata(
    exc: OcrTargetingError | OcrEngineError,
    *,
    redact_text: bool,
    evidence: OcrResolutionEvidence | None = None,
    sensitive_values: tuple[str, ...] = (),
) -> dict[str, object]:
    resolution = exc.resolution if isinstance(exc, OcrTargetingError) else None
    return build_ocr_result_metadata(
        resolution,
        evidence=evidence,
        error_code=exc.code,
        sensitive_values=sensitive_values,
        redact_text=redact_text,
    )


def build_input_verification_target(
    payload: dict,
    *,
    action_target: OcrTargetSpec,
) -> OcrTargetSpec | None:
    raw_verification_target = payload.get("ocr_verification_target")
    verify_ocr = payload.get("verify_ocr", False)
    if not isinstance(verify_ocr, bool):
        raise ValueError("input `verify_ocr` must be boolean.")
    if raw_verification_target is not None:
        return normalize_ocr_target_payload(
            {"ocr_target": raw_verification_target}
        ).model_copy(update={"scope": "viewport"})
    if not verify_ocr:
        return None

    text = payload.get("text")
    if not isinstance(text, str) or not text:
        raise ValueError("input OCR verification requires non-empty `text`.")
    return action_target.model_copy(
        update={
            "text": text,
            "match_mode": "exact",
            "case_sensitive": True,
            "occurrence": 1,
            "scope": "viewport",
            "role": "any",
            "action_point": "text_center",
            "relation": None,
        }
    )


def raise_input_verification_error(
    target: OcrTargetSpec,
    exc: OcrTargetingError,
) -> None:
    raise OcrTargetingError(
        OcrTargetResolution(
            status="rejected",
            target=target,
            candidates=exc.candidates,
            error_code=OcrErrorCode.OCR_ACTION_VERIFICATION_FAILED,
            error_message=(
                "OCR input verification did not find a unique visible value "
                "that satisfies the configured target."
            ),
            scanned_tile_count=exc.resolution.scanned_tile_count,
            elapsed_ms=exc.resolution.elapsed_ms,
        )
    ) from exc
