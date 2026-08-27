from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.workers.ocr_types import (
    OcrErrorCode,
    OcrPageSnapshot,
    OcrPoint,
    OcrRect,
    OcrTargetResolution,
    OcrTargetSpec,
)

DEFAULT_MAX_CANDIDATE_SUMMARIES = 5
DEFAULT_MAX_TEXT_LENGTH = 160
HARD_MAX_CANDIDATE_SUMMARIES = 20
HARD_MAX_TEXT_LENGTH = 512
_MAX_PREPROCESS_VARIANTS = 16
_MAX_VARIANT_NAME_LENGTH = 64


@dataclass(frozen=True, slots=True)
class OcrEvidenceCacheSnapshot:
    analysis_hits: int
    analysis_misses: int
    snapshot_hits: int
    snapshot_misses: int
    generation: int
    last_invalidation_reason: str | None


@dataclass(frozen=True, slots=True)
class OcrEvidenceCapture:
    image_png_bytes: bytes
    snapshot: OcrPageSnapshot
    snapshot_cache_hit: bool
    analysis_cache_hit: bool | None


@dataclass(frozen=True, slots=True)
class OcrResolutionEvidence:
    target: OcrTargetSpec
    resolution: OcrTargetResolution | None
    captures: tuple[OcrEvidenceCapture, ...]
    cache_before: OcrEvidenceCacheSnapshot
    cache_after: OcrEvidenceCacheSnapshot
    revalidation_required: bool
    revalidation_attempted: bool
    revalidation_passed: bool | None
    locate_duration_ms: float
    error_code: OcrErrorCode | None = None
    max_candidate_summaries: int = DEFAULT_MAX_CANDIDATE_SUMMARIES
    max_text_length: int = DEFAULT_MAX_TEXT_LENGTH


def build_ocr_result_metadata(
    resolution: OcrTargetResolution | None,
    *,
    evidence: OcrResolutionEvidence | None = None,
    action_point: OcrPoint | None = None,
    error_code: OcrErrorCode | str | None = None,
    sensitive_values: Iterable[str] = (),
    redact_text: bool = False,
    max_candidate_summaries: int | None = None,
    max_text_length: int | None = None,
) -> dict[str, object]:
    """Build the bounded metadata contract used by all OCR step results."""
    target = resolution.target if resolution is not None else None
    if target is None and evidence is not None:
        target = evidence.target
    if target is None:
        if error_code is None:
            return {}
        return {"ocr": {"error_code": _error_code_value(error_code)}}

    candidate_limit = _bounded_candidate_limit(
        max_candidate_summaries
        if max_candidate_summaries is not None
        else (
            evidence.max_candidate_summaries
            if evidence is not None
            else DEFAULT_MAX_CANDIDATE_SUMMARIES
        )
    )
    text_limit = _bounded_text_limit(
        max_text_length
        if max_text_length is not None
        else (
            evidence.max_text_length
            if evidence is not None
            else DEFAULT_MAX_TEXT_LENGTH
        )
    )
    secrets = tuple(value for value in sensitive_values if value)
    candidates = resolution.candidates if resolution is not None else ()
    selected = resolution.selected_candidate if resolution is not None else None

    metadata: dict[str, object] = {
        "scope": target.scope,
        "language": target.language,
        "candidate_count": len(candidates),
        "candidates": [
            _candidate_summary(
                candidate,
                rank=index,
                text_limit=text_limit,
                sensitive_values=secrets,
                redact_text=redact_text,
            )
            for index, candidate in enumerate(candidates[:candidate_limit], start=1)
        ],
        "preprocess_variants": _preprocess_variants(evidence),
        "tiles": {
            "scanned": resolution.scanned_tile_count if resolution is not None else 0,
            "captured": len(evidence.captures) if evidence is not None else 0,
        },
        "cache": _cache_metadata(evidence),
        "revalidation": _revalidation_metadata(evidence, target=target),
        "duration_ms": {
            "ocr": _round_number(_ocr_duration_ms(evidence)),
            "locate": _round_number(
                evidence.locate_duration_ms
                if evidence is not None
                else (resolution.elapsed_ms if resolution is not None else 0.0)
            ),
        },
    }

    if selected is not None:
        coordinates = selected.element.coordinates
        metadata.update(
            {
                "matched_text": _bounded_text(
                    selected.element.text,
                    limit=text_limit,
                    sensitive_values=secrets,
                )
                if not redact_text
                else "[redacted]",
                "role": selected.element.role,
                "confidence": _round_number(selected.element.confidence),
                "score": _round_number(selected.total_score),
                "pixel_rect": _rect_dict(coordinates.pixel_rect),
                "ratio_rect": _rect_dict(coordinates.ratio_rect),
                "viewport_css_rect": _rect_dict(coordinates.viewport_css_rect),
                "document_css_rect": _rect_dict(coordinates.document_css_rect),
            }
        )
    if action_point is not None:
        metadata["action_point"] = {
            "x": _round_number(action_point.x),
            "y": _round_number(action_point.y),
        }
        metadata["action_point_mode"] = target.action_point

    resolved_error_code = error_code
    if resolved_error_code is None and resolution is not None:
        resolved_error_code = resolution.error_code
    if resolved_error_code is None and evidence is not None:
        resolved_error_code = evidence.error_code
    if resolved_error_code is not None:
        metadata["error_code"] = _error_code_value(resolved_error_code)
    return {"ocr": metadata}


def build_ocr_annotation_png(
    evidence: OcrResolutionEvidence,
    *,
    action_point: OcrPoint | None = None,
    sensitive_values: Iterable[str] = (),
    redact_text: bool = False,
) -> bytes:
    """Render candidate boxes, the selected target, and the action point."""
    capture = select_evidence_capture(evidence)
    if capture is None:
        raise ValueError("OCR evidence has no captured screenshot.")

    try:
        import cv2
        import numpy as np
    except ImportError as exc:  # pragma: no cover - runtime dependency validation
        raise RuntimeError("OpenCV and NumPy are required for OCR annotations.") from exc

    image = cv2.imdecode(
        np.frombuffer(capture.image_png_bytes, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )
    if image is None:
        raise ValueError("OCR evidence screenshot could not be decoded.")

    resolution = evidence.resolution
    candidates = resolution.candidates if resolution is not None else ()
    selected = resolution.selected_candidate if resolution is not None else None
    secrets = tuple(value for value in sensitive_values if value)
    drawn_count = 0
    for rank, candidate in enumerate(
        candidates[: evidence.max_candidate_summaries],
        start=1,
    ):
        pixel_rect = _document_rect_to_capture(
            candidate.element.coordinates.document_css_rect,
            capture=capture,
            image_width=image.shape[1],
            image_height=image.shape[0],
        )
        if pixel_rect is None:
            continue
        is_selected = (
            selected is not None
            and candidate.element.element_id == selected.element.element_id
        )
        color = (70, 190, 70) if is_selected else (0, 180, 255)
        thickness = 3 if is_selected else 2
        left, top, right, bottom = pixel_rect
        candidate_is_sensitive = redact_text or any(
            sensitive_value in candidate.element.text
            for sensitive_value in secrets
        )
        if candidate_is_sensitive:
            cv2.rectangle(
                image,
                (left, top),
                (right, bottom),
                (32, 32, 32),
                cv2.FILLED,
            )
        cv2.rectangle(image, (left, top), (right, bottom), color, thickness)
        label_text = _bounded_text(
            candidate.element.text,
            limit=min(evidence.max_text_length, 40),
            sensitive_values=secrets,
        ) if not candidate_is_sensitive else "[redacted]"
        ascii_text = label_text.encode("ascii", "backslashreplace").decode("ascii")
        label = (
            f"#{rank} {ascii_text} "
            f"c={candidate.element.confidence:.2f} s={candidate.total_score:.2f}"
        )
        cv2.putText(
            image,
            label[:120],
            (left, max(16, top - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            color,
            1,
            cv2.LINE_AA,
        )
        drawn_count += 1

    if action_point is not None:
        point = _viewport_point_to_capture(
            action_point,
            capture=capture,
            image_width=image.shape[1],
            image_height=image.shape[0],
        )
        if point is not None:
            cv2.drawMarker(
                image,
                point,
                (40, 40, 230),
                markerType=cv2.MARKER_CROSS,
                markerSize=22,
                thickness=3,
            )
            cv2.circle(image, point, 8, (40, 40, 230), 2)

    status = (
        resolution.status.upper()
        if resolution is not None
        else (evidence.error_code.value if evidence.error_code is not None else "OCR")
    )
    cv2.putText(
        image,
        f"{status} candidates={len(candidates)} annotated={drawn_count}"[:120],
        (12, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        image,
        f"{status} candidates={len(candidates)} annotated={drawn_count}"[:120],
        (12, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (30, 64, 175),
        1,
        cv2.LINE_AA,
    )

    encoded, output = cv2.imencode(".png", image)
    if not encoded:
        raise RuntimeError("OCR annotation PNG encoding failed.")
    return output.tobytes()


def select_evidence_capture(
    evidence: OcrResolutionEvidence,
) -> OcrEvidenceCapture | None:
    if not evidence.captures:
        return None
    resolution = evidence.resolution
    if resolution is None:
        return evidence.captures[-1]
    candidate = resolution.selected_candidate
    if candidate is None and resolution.candidates:
        candidate = resolution.candidates[0]
    if candidate is None:
        return evidence.captures[-1]

    rect = candidate.element.coordinates.document_css_rect
    center_x = rect.x + rect.width / 2.0
    center_y = rect.y + rect.height / 2.0
    for capture in reversed(evidence.captures):
        snapshot = capture.snapshot
        if (
            snapshot.scroll_x_css <= center_x
            <= snapshot.scroll_x_css + snapshot.viewport_width_css
            and snapshot.scroll_y_css <= center_y
            <= snapshot.scroll_y_css + snapshot.viewport_height_css
        ):
            return capture
    return evidence.captures[-1]


def _candidate_summary(
    candidate,
    *,
    rank: int,
    text_limit: int,
    sensitive_values: tuple[str, ...],
    redact_text: bool,
) -> dict[str, object]:
    return {
        "rank": rank,
        "matched_text": _bounded_text(
            candidate.element.text,
            limit=text_limit,
            sensitive_values=sensitive_values,
        )
        if not redact_text
        else "[redacted]",
        "role": candidate.element.role,
        "confidence": _round_number(candidate.element.confidence),
        "score": _round_number(candidate.total_score),
        "viewport_css_rect": _rect_dict(
            candidate.element.coordinates.viewport_css_rect
        ),
        "document_css_rect": _rect_dict(
            candidate.element.coordinates.document_css_rect
        ),
    }


def _preprocess_variants(
    evidence: OcrResolutionEvidence | None,
) -> list[str]:
    if evidence is None:
        return []
    variants: list[str] = []
    for capture in evidence.captures:
        for variant in capture.snapshot.preprocessing_variants:
            normalized = _bounded_text(
                variant,
                limit=_MAX_VARIANT_NAME_LENGTH,
                sensitive_values=(),
            )
            if normalized not in variants:
                variants.append(normalized)
            if len(variants) >= _MAX_PREPROCESS_VARIANTS:
                return variants
    return variants


def _cache_metadata(
    evidence: OcrResolutionEvidence | None,
) -> dict[str, object]:
    if evidence is None:
        return {
            "analysis_hits": 0,
            "analysis_misses": 0,
            "snapshot_hits": 0,
            "snapshot_misses": 0,
        }
    before = evidence.cache_before
    after = evidence.cache_after
    metadata: dict[str, object] = {
        "analysis_hits": max(0, after.analysis_hits - before.analysis_hits),
        "analysis_misses": max(0, after.analysis_misses - before.analysis_misses),
        "snapshot_hits": max(0, after.snapshot_hits - before.snapshot_hits),
        "snapshot_misses": max(0, after.snapshot_misses - before.snapshot_misses),
        "generation": after.generation,
    }
    if after.last_invalidation_reason:
        metadata["last_invalidation_reason"] = _bounded_text(
            after.last_invalidation_reason,
            limit=64,
            sensitive_values=(),
        )
    return metadata


def _revalidation_metadata(
    evidence: OcrResolutionEvidence | None,
    *,
    target: OcrTargetSpec,
) -> dict[str, object]:
    if evidence is None:
        return {
            "required": target.scope == "page",
            "attempted": False,
            "passed": None,
        }
    return {
        "required": evidence.revalidation_required,
        "attempted": evidence.revalidation_attempted,
        "passed": evidence.revalidation_passed,
    }


def _ocr_duration_ms(evidence: OcrResolutionEvidence | None) -> float:
    if evidence is None:
        return 0.0
    return sum(
        capture.snapshot.elapsed_ms
        for capture in evidence.captures
        if capture.analysis_cache_hit is False
    )


def _document_rect_to_capture(
    rect: OcrRect,
    *,
    capture: OcrEvidenceCapture,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int] | None:
    snapshot = capture.snapshot
    scale_x = image_width / snapshot.viewport_width_css
    scale_y = image_height / snapshot.viewport_height_css
    left = (rect.x - snapshot.scroll_x_css) * scale_x
    top = (rect.y - snapshot.scroll_y_css) * scale_y
    right = left + rect.width * scale_x
    bottom = top + rect.height * scale_y
    if right < 0 or bottom < 0 or left >= image_width or top >= image_height:
        return None
    return (
        max(0, min(image_width - 1, int(round(left)))),
        max(0, min(image_height - 1, int(round(top)))),
        max(0, min(image_width - 1, int(round(right)))),
        max(0, min(image_height - 1, int(round(bottom)))),
    )


def _viewport_point_to_capture(
    point: OcrPoint,
    *,
    capture: OcrEvidenceCapture,
    image_width: int,
    image_height: int,
) -> tuple[int, int] | None:
    snapshot = capture.snapshot
    x = point.x * image_width / snapshot.viewport_width_css
    y = point.y * image_height / snapshot.viewport_height_css
    if x < 0 or y < 0 or x >= image_width or y >= image_height:
        return None
    return int(round(x)), int(round(y))


def _rect_dict(rect) -> dict[str, float]:
    return {
        "x": _round_number(rect.x),
        "y": _round_number(rect.y),
        "width": _round_number(rect.width),
        "height": _round_number(rect.height),
    }


def _bounded_text(
    value: str,
    *,
    limit: int,
    sensitive_values: tuple[str, ...],
) -> str:
    bounded_limit = _bounded_text_limit(limit)
    sanitized = value
    for sensitive_value in sorted(sensitive_values, key=len, reverse=True):
        sanitized = sanitized.replace(sensitive_value, "[redacted]")
    if len(sanitized) <= bounded_limit:
        return sanitized
    if bounded_limit <= 3:
        return sanitized[:bounded_limit]
    return f"{sanitized[: bounded_limit - 3]}..."


def _bounded_candidate_limit(value: int) -> int:
    return min(max(int(value), 1), HARD_MAX_CANDIDATE_SUMMARIES)


def _bounded_text_limit(value: int) -> int:
    return min(max(int(value), 1), HARD_MAX_TEXT_LENGTH)


def _round_number(value: float) -> float:
    return round(float(value), 4)


def _error_code_value(value: OcrErrorCode | str) -> str:
    return value.value if isinstance(value, OcrErrorCode) else str(value)
