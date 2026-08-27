from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from app.workers.ocr_contract import (
    NormalizedSelectOptionPayload,
    normalize_select_option_payload,
)
from app.workers.ocr_engine import OcrEngineError
from app.workers.ocr_targeting import OcrTargetingError
from app.workers.ocr_types import (
    OcrErrorCode,
    OcrRect,
    OcrTargetResolution,
    OcrTargetSpec,
)


class OcrActionVerificationError(OcrEngineError):
    def __init__(self, message: str) -> None:
        super().__init__(OcrErrorCode.OCR_ACTION_VERIFICATION_FAILED, message)


class OcrActionSession(Protocol):
    def resolve(self, target: OcrTargetSpec) -> OcrTargetResolution: ...

    def resolve_for_action(self, target: OcrTargetSpec) -> OcrTargetResolution: ...

    def invalidate(self, reason: str) -> None: ...


class MouseLike(Protocol):
    def click(self, x: float, y: float) -> None: ...


class SelectPageLike(Protocol):
    mouse: MouseLike

    def wait_for_timeout(self, timeout_ms: float) -> None: ...


@dataclass(frozen=True, slots=True)
class SelectOptionActionResult:
    field_resolution: OcrTargetResolution
    option_resolution: OcrTargetResolution
    verification_resolution: OcrTargetResolution | None
    field_verification_rect: OcrRect


def execute_ocr_select_option(
    page: SelectPageLike,
    *,
    ocr_session: OcrActionSession,
    payload: Mapping[str, object],
    timeout_ms: int,
) -> SelectOptionActionResult:
    normalized = normalize_select_option_payload(payload)

    field_resolution = ocr_session.resolve_for_action(normalized.field_target)
    field_rect = _action_rect(field_resolution)
    field_verification_rect = _field_verification_rect(field_resolution)
    _click_rect(page, field_rect)

    ocr_session.invalidate("select_option_field_click")
    _wait_for_menu(page, timeout_ms=timeout_ms)

    option_resolution = ocr_session.resolve_for_action(normalized.option_target)
    option_rect = _action_rect(option_resolution)
    _click_rect(page, option_rect)

    ocr_session.invalidate("select_option_option_click")
    _wait_for_menu(page, timeout_ms=timeout_ms)

    verification_resolution = _verify_selected_option(
        ocr_session,
        normalized=normalized,
        option_resolution=option_resolution,
        field_rect=field_verification_rect,
    )
    return SelectOptionActionResult(
        field_resolution=field_resolution,
        option_resolution=option_resolution,
        verification_resolution=verification_resolution,
        field_verification_rect=field_verification_rect,
    )


def _action_rect(resolution: OcrTargetResolution) -> OcrRect:
    candidate = resolution.selected_candidate
    if candidate is None:
        raise OcrTargetingError(
            resolution.model_copy(
                update={
                    "status": "rejected",
                    "error_code": OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED,
                    "error_message": "OCR action resolution has no selected candidate.",
                }
            )
        )

    element = candidate.element
    if resolution.target.action_point == "associated_control":
        rect = element.associated_control_rect
        if rect is None or element.association_ambiguous:
            raise OcrTargetingError(
                resolution.model_copy(
                    update={
                        "status": "rejected",
                        "error_code": OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED,
                        "error_message": (
                            "OCR action target has no unique associated control."
                        ),
                    }
                )
            )
    else:
        rect = element.coordinates.viewport_css_rect

    if rect.width <= 0 or rect.height <= 0 or rect.x < 0 or rect.y < 0:
        raise OcrTargetingError(
            resolution.model_copy(
                update={
                    "status": "rejected",
                    "error_code": OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED,
                    "error_message": "OCR action target has invalid viewport geometry.",
                }
            )
        )
    return rect


def _click_rect(page: SelectPageLike, rect: OcrRect) -> None:
    page.mouse.click(
        rect.x + rect.width / 2.0,
        rect.y + rect.height / 2.0,
    )


def _wait_for_menu(page: SelectPageLike, *, timeout_ms: int) -> None:
    wait_ms = min(250, max(0, timeout_ms // 20))
    if wait_ms > 0:
        page.wait_for_timeout(wait_ms)


def _field_verification_rect(resolution: OcrTargetResolution) -> OcrRect:
    candidate = resolution.selected_candidate
    if candidate is None:
        raise OcrActionVerificationError(
            "The confirmed OCR field has no selected candidate."
        )
    element = candidate.element
    if (
        element.associated_control_rect is not None
        and not element.association_ambiguous
    ):
        return element.associated_control_rect
    return _action_rect(resolution)


def _verify_selected_option(
    ocr_session: OcrActionSession,
    *,
    normalized: NormalizedSelectOptionPayload,
    option_resolution: OcrTargetResolution,
    field_rect: OcrRect,
) -> OcrTargetResolution | None:
    if not normalized.verify_selected:
        return None

    selected_candidate = option_resolution.selected_candidate
    if selected_candidate is None:
        raise OcrActionVerificationError(
            "The selected option has no confirmed OCR candidate."
        )

    verification_target = normalized.option_target.model_copy(
        update={
            "text": selected_candidate.element.text,
            "match_mode": "exact",
            "occurrence": 1,
            "scope": "viewport",
            "role": "any",
            "action_point": "text_center",
            "relation": None,
        }
    )
    resolution: OcrTargetResolution
    try:
        resolution = ocr_session.resolve(verification_target)
    except OcrTargetingError as exc:
        if exc.code != OcrErrorCode.OCR_TARGET_AMBIGUOUS:
            raise OcrActionVerificationError(
                f"Selected option text `{verification_target.text}` was not confirmed."
            ) from exc
        resolution = exc.resolution

    allowed_rect = _expanded_field_rect(field_rect)
    regional_candidates = tuple(
        candidate
        for candidate in resolution.candidates
        if _rect_contains_center(allowed_rect, candidate.element.coordinates.viewport_css_rect)
    )
    if len(regional_candidates) != 1:
        raise OcrActionVerificationError(
            (
                f"Selected option text `{verification_target.text}` was not uniquely "
                "confirmed inside the OCR field region."
            )
        )
    return OcrTargetResolution(
        status="resolved",
        target=verification_target,
        selected_candidate=regional_candidates[0],
        candidates=regional_candidates,
        scanned_tile_count=resolution.scanned_tile_count,
        elapsed_ms=resolution.elapsed_ms,
    )


def _expanded_field_rect(rect: OcrRect) -> OcrRect:
    horizontal_padding = max(6.0, rect.width * 0.08)
    vertical_padding = max(4.0, rect.height * 0.20)
    return OcrRect(
        x=rect.x - horizontal_padding,
        y=rect.y - vertical_padding,
        width=rect.width + horizontal_padding * 2.0,
        height=rect.height + vertical_padding * 2.0,
    )


def _rect_contains_center(container: OcrRect, candidate: OcrRect) -> bool:
    center_x = candidate.x + candidate.width / 2.0
    center_y = candidate.y + candidate.height / 2.0
    return (
        container.x <= center_x <= container.x + container.width
        and container.y <= center_y <= container.y + container.height
    )
