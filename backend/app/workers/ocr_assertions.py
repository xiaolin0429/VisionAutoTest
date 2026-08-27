from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.workers.ocr_contract import NormalizedOcrAssertPayload
from app.workers.ocr_targeting import OcrTargetingError
from app.workers.ocr_types import (
    OcrErrorCode,
    OcrTargetCandidate,
    OcrTargetResolution,
    OcrTargetSpec,
)

_COUNT_PROBE_OCCURRENCE = 2_147_483_647


@dataclass(frozen=True, slots=True)
class OcrAssertionEvaluation:
    status: Literal["passed", "failed", "error"]
    score_value: float | None
    error_message: str | None
    resolution: OcrTargetResolution | None = None
    matched_count: int | None = None


def evaluate_ocr_assertion(
    payload: NormalizedOcrAssertPayload,
    *,
    resolve: Callable[[OcrTargetSpec], OcrTargetResolution],
) -> OcrAssertionEvaluation:
    """Evaluate assertion semantics against a shared OCR target resolver."""
    if payload.assertion == "count":
        return _evaluate_count(payload, resolve=resolve)

    try:
        resolution = resolve(payload.target)
    except OcrTargetingError as exc:
        return _evaluate_rejection(payload, exc)

    if payload.assertion == "absent":
        return OcrAssertionEvaluation(
            status="failed",
            score_value=0.0,
            error_message=(
                f"OCR absent assertion failed: found `{payload.target.text}`."
            ),
            resolution=resolution,
        )

    return OcrAssertionEvaluation(
        status="passed",
        score_value=1.0,
        error_message=None,
        resolution=resolution,
    )


def _evaluate_rejection(
    payload: NormalizedOcrAssertPayload,
    exc: OcrTargetingError,
) -> OcrAssertionEvaluation:
    if exc.code == OcrErrorCode.OCR_PAGE_SCAN_LIMIT:
        return OcrAssertionEvaluation(
            status="error",
            score_value=None,
            error_message=str(exc),
            resolution=exc.resolution,
        )
    if (
        payload.assertion == "absent"
        and exc.code == OcrErrorCode.OCR_TARGET_NOT_FOUND
    ):
        return OcrAssertionEvaluation(
            status="passed",
            score_value=1.0,
            error_message=None,
            resolution=exc.resolution,
        )
    return OcrAssertionEvaluation(
        status="failed",
        score_value=0.0,
        error_message=(
            f"OCR {payload.assertion} assertion failed: "
            f"{exc.resolution.error_message}"
        ),
        resolution=exc.resolution,
    )


def _evaluate_count(
    payload: NormalizedOcrAssertPayload,
    *,
    resolve: Callable[[OcrTargetSpec], OcrTargetResolution],
) -> OcrAssertionEvaluation:
    probe = payload.target.model_copy(
        update={
            "occurrence": _COUNT_PROBE_OCCURRENCE,
            "ambiguity_margin": 0.0,
        }
    )
    resolution: OcrTargetResolution
    try:
        resolution = resolve(probe)
        candidates = resolution.candidates
    except OcrTargetingError as exc:
        resolution = exc.resolution
        if exc.code == OcrErrorCode.OCR_PAGE_SCAN_LIMIT:
            return OcrAssertionEvaluation(
                status="error",
                score_value=None,
                error_message=str(exc),
                resolution=resolution,
            )
        if exc.code != OcrErrorCode.OCR_TARGET_NOT_FOUND:
            return OcrAssertionEvaluation(
                status="failed",
                score_value=0.0,
                error_message=(
                    "OCR count assertion could not determine a reliable count: "
                    f"{exc.resolution.error_message}"
                ),
                resolution=resolution,
            )
        candidates = exc.candidates

    matched_candidates = _qualified_candidates(
        candidates,
        min_score=payload.target.min_score,
    )
    matched_count = len(matched_candidates)
    expected_count = payload.expected_count
    if expected_count is None:
        raise ValueError("Normalized count assertion is missing expected_count.")
    if matched_count == expected_count:
        return OcrAssertionEvaluation(
            status="passed",
            score_value=1.0,
            error_message=None,
            resolution=resolution,
            matched_count=matched_count,
        )
    return OcrAssertionEvaluation(
        status="failed",
        score_value=0.0,
        error_message=(
            "OCR count assertion failed: "
            f"expected {expected_count}, found {matched_count}."
        ),
        resolution=resolution,
        matched_count=matched_count,
    )


def _qualified_candidates(
    candidates: tuple[OcrTargetCandidate, ...],
    *,
    min_score: float,
) -> tuple[OcrTargetCandidate, ...]:
    return tuple(
        candidate
        for candidate in candidates
        if candidate.total_score >= min_score
    )
