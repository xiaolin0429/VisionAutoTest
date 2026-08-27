from __future__ import annotations

import pytest

from app.workers.ocr_evidence import (
    OcrEvidenceCacheSnapshot,
    OcrEvidenceCapture,
    OcrResolutionEvidence,
    build_ocr_annotation_png,
    build_ocr_result_metadata,
)
from app.workers.ocr_types import (
    OcrCoordinateSet,
    OcrPageSnapshot,
    OcrPoint,
    OcrRatioRect,
    OcrRect,
    OcrTargetCandidate,
    OcrTargetResolution,
    OcrTargetSpec,
    OcrTextElement,
)

pytestmark = pytest.mark.ocr_fake


def _candidate(index: int, text: str) -> OcrTargetCandidate:
    rect = OcrRect(x=10 + index * 20, y=30, width=60, height=24)
    element = OcrTextElement(
        element_id=f"element-{index}",
        text=text,
        confidence=0.98 - index * 0.01,
        line_ids=(),
        coordinates=OcrCoordinateSet(
            pixel_rect=rect,
            ratio_rect=OcrRatioRect(
                x=rect.x / 400,
                y=rect.y / 200,
                width=rect.width / 400,
                height=rect.height / 200,
            ),
            viewport_css_rect=rect,
            document_css_rect=rect,
        ),
        role="button",
        role_confidence=0.95,
    )
    return OcrTargetCandidate(
        element=element,
        text_score=1,
        confidence_score=element.confidence,
        role_score=0.95,
        relation_score=1,
        distance_score=1,
        variant_consistency_score=1,
        total_score=0.97 - index * 0.01,
    )


def _png_bytes() -> bytes:
    import cv2
    import numpy as np

    image = np.full((200, 400, 3), 245, dtype=np.uint8)
    encoded, output = cv2.imencode(".png", image)
    assert encoded
    return output.tobytes()


def _evidence(
    *,
    sensitive_text: str,
) -> tuple[OcrTargetResolution, OcrResolutionEvidence, bytes]:
    candidates = tuple(
        _candidate(index, f"candidate-{index}-{sensitive_text}-long-value")
        for index in range(8)
    )
    target = OcrTargetSpec(text="candidate", match_mode="contains")
    resolution = OcrTargetResolution(
        status="resolved",
        target=target,
        selected_candidate=candidates[0],
        candidates=candidates,
        scanned_tile_count=2,
        elapsed_ms=3.4,
    )
    image_bytes = _png_bytes()
    snapshot = OcrPageSnapshot(
        image_width_px=400,
        image_height_px=200,
        viewport_width_css=400,
        viewport_height_css=200,
        device_scale_factor=1,
        scroll_x_css=0,
        scroll_y_css=0,
        language_profiles=("zh_en",),
        preprocessing_variants=tuple(f"variant-{index}" for index in range(20)),
        screenshot_checksum_sha256="a" * 64,
        elapsed_ms=7.5,
        elements=tuple(candidate.element for candidate in candidates),
    )
    before = OcrEvidenceCacheSnapshot(
        analysis_hits=1,
        analysis_misses=2,
        snapshot_hits=3,
        snapshot_misses=4,
        generation=5,
        last_invalidation_reason=None,
    )
    after = OcrEvidenceCacheSnapshot(
        analysis_hits=2,
        analysis_misses=3,
        snapshot_hits=3,
        snapshot_misses=5,
        generation=5,
        last_invalidation_reason="click",
    )
    evidence = OcrResolutionEvidence(
        target=target,
        resolution=resolution,
        captures=(
            OcrEvidenceCapture(
                image_png_bytes=image_bytes,
                snapshot=snapshot,
                snapshot_cache_hit=False,
                analysis_cache_hit=False,
            ),
        ),
        cache_before=before,
        cache_after=after,
        revalidation_required=True,
        revalidation_attempted=True,
        revalidation_passed=True,
        locate_duration_ms=12.34567,
        max_candidate_summaries=3,
        max_text_length=24,
    )
    return resolution, evidence, image_bytes


def test_metadata_builder_bounds_candidates_text_and_sensitive_values() -> None:
    secret = "sensitive-input-value"
    resolution, evidence, _ = _evidence(sensitive_text=secret)

    metadata = build_ocr_result_metadata(
        resolution,
        evidence=evidence,
        action_point=OcrPoint(x=40, y=42),
        sensitive_values=(secret,),
    )
    ocr = metadata["ocr"]
    assert isinstance(ocr, dict)

    assert ocr["candidate_count"] == 8
    assert len(ocr["candidates"]) == 3
    assert len(ocr["preprocess_variants"]) == 16
    assert all(
        len(candidate["matched_text"]) <= 24
        for candidate in ocr["candidates"]
    )
    assert secret not in repr(metadata)
    assert ocr["matched_text"].startswith("candidate-0-[redacted")
    assert ocr["scope"] == "viewport"
    assert ocr["language"] == "zh_en"
    assert ocr["tiles"] == {"scanned": 2, "captured": 1}
    assert ocr["cache"]["analysis_hits"] == 1
    assert ocr["cache"]["snapshot_misses"] == 1
    assert ocr["revalidation"]["passed"] is True
    assert ocr["duration_ms"] == {"ocr": 7.5, "locate": 12.3457}
    assert ocr["action_point"] == {"x": 40.0, "y": 42.0}


def test_metadata_builder_returns_empty_object_without_ocr_context() -> None:
    assert build_ocr_result_metadata(None) == {}


def test_annotation_png_draws_candidates_target_and_action_point() -> None:
    cv2 = __import__("cv2")
    np = __import__("numpy")
    resolution, evidence, source_bytes = _evidence(sensitive_text="secret")

    annotation = build_ocr_annotation_png(
        evidence,
        action_point=OcrPoint(x=40, y=42),
        sensitive_values=("secret",),
    )

    source = cv2.imdecode(
        np.frombuffer(source_bytes, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )
    rendered = cv2.imdecode(
        np.frombuffer(annotation, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )
    assert annotation.startswith(b"\x89PNG\r\n\x1a\n")
    assert rendered.shape == source.shape
    assert not np.array_equal(rendered, source)
    assert int(rendered[42, 20].max()) < 60
    assert resolution.selected_candidate is not None
