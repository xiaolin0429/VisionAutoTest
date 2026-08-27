from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.workers.ocr_targeting import OcrTargetingError, resolve_ocr_target
from app.workers.ocr_types import (
    OcrCoordinateSet,
    OcrElementRelation,
    OcrErrorCode,
    OcrPageSnapshot,
    OcrRatioRect,
    OcrRect,
    OcrTargetRelationSpec,
    OcrTargetSpec,
    OcrTextElement,
)

pytestmark = pytest.mark.ocr_fake


def _coordinates(x: float, y: float, width: float, height: float) -> OcrCoordinateSet:
    rect = OcrRect(x=x, y=y, width=width, height=height)
    return OcrCoordinateSet(
        pixel_rect=rect,
        ratio_rect=OcrRatioRect(
            x=x / 1000.0,
            y=y / 1000.0,
            width=width / 1000.0,
            height=height / 1000.0,
        ),
        viewport_css_rect=rect,
        document_css_rect=rect,
    )


def _element(
    element_id: str,
    text: str,
    *,
    x: float,
    y: float,
    confidence: float = 0.95,
    role: str = "text",
) -> OcrTextElement:
    return OcrTextElement(
        element_id=element_id,
        text=text,
        confidence=confidence,
        line_ids=(),
        coordinates=_coordinates(x, y, 80, 20),
        role=role,
        role_confidence=0.95,
    )


def _snapshot(
    elements: Sequence[OcrTextElement],
    *,
    relations: Sequence[OcrElementRelation] = (),
) -> OcrPageSnapshot:
    return OcrPageSnapshot(
        image_width_px=1000,
        image_height_px=1000,
        viewport_width_css=1000,
        viewport_height_css=1000,
        device_scale_factor=1.0,
        scroll_x_css=0,
        scroll_y_css=0,
        language_profiles=("en",),
        preprocessing_variants=("original",),
        screenshot_checksum_sha256="a" * 64,
        elapsed_ms=1.0,
        elements=tuple(elements),
        relations=tuple(relations),
    )


@pytest.mark.parametrize(
    ("actual", "expected", "match_mode"),
    [
        ("ＦＯＯ   Bar", "foo bar", "exact"),
        ("prefix Submit suffix", "submit", "contains"),
        ("Order 12345 ready", r"order\s+\d+\s+ready", "regex"),
        ("Submti", "Submit", "fuzzy"),
    ],
)
def test_match_modes_apply_nfkc_whitespace_and_case_normalization(
    actual: str,
    expected: str,
    match_mode: str,
) -> None:
    target = OcrTargetSpec(
        text=expected,
        match_mode=match_mode,
        language="en",
        min_confidence=0.5,
        min_score=0.5,
        ambiguity_margin=0.0,
    )

    resolution = resolve_ocr_target(
        _snapshot((_element("target", actual, x=20, y=30),)),
        target,
    )

    assert resolution.selected_candidate is not None
    assert resolution.selected_candidate.element.element_id == "target"
    assert resolution.selected_candidate.text_score >= 0.75


def test_scoring_uses_role_relation_distance_and_stable_reading_order() -> None:
    anchor = _element("anchor", "Username", x=20, y=20, role="label")
    near = _element("near", "Value", x=150, y=20, role="input")
    far = _element("far", "Value", x=700, y=20, role="input")
    relations = (
        OcrElementRelation(
            source_element_id="near",
            target_element_id="anchor",
            type="right_of",
            distance_ratio=0.12,
            confidence=0.9,
        ),
        OcrElementRelation(
            source_element_id="far",
            target_element_id="anchor",
            type="right_of",
            distance_ratio=0.65,
            confidence=0.35,
        ),
    )
    target = OcrTargetSpec(
        text="value",
        language="en",
        role="input",
        min_confidence=0.5,
        min_score=0.5,
        ambiguity_margin=0.05,
        relation=OcrTargetRelationSpec(
            type="right_of",
            anchor_text="username",
            max_distance_ratio=0.7,
        ),
    )

    resolution = resolve_ocr_target(
        _snapshot((anchor, far, near), relations=relations),
        target,
    )

    assert resolution.selected_candidate is not None
    assert resolution.selected_candidate.element.element_id == "near"
    assert [candidate.element.element_id for candidate in resolution.candidates] == [
        "near",
        "far",
    ]
    assert resolution.candidates[0].distance_score > resolution.candidates[1].distance_score


@pytest.mark.parametrize(
    ("target", "snapshot", "expected_code"),
    [
        (
            OcrTargetSpec(text="Missing", language="en"),
            _snapshot((_element("one", "Present", x=0, y=0),)),
            OcrErrorCode.OCR_TARGET_NOT_FOUND,
        ),
        (
            OcrTargetSpec(text="Save", language="en", min_confidence=0.9),
            _snapshot(
                (_element("one", "Save", x=0, y=0, confidence=0.6),)
            ),
            OcrErrorCode.OCR_CONFIDENCE_LOW,
        ),
        (
            OcrTargetSpec(
                text="Save",
                language="en",
                role="button",
                min_confidence=0.5,
            ),
            _snapshot((_element("one", "Save", x=0, y=0, role="text"),)),
            OcrErrorCode.OCR_ROLE_NOT_SATISFIED,
        ),
        (
            OcrTargetSpec(
                text="Save",
                language="en",
                min_confidence=0.5,
                relation=OcrTargetRelationSpec(
                    type="below",
                    anchor_text="Toolbar",
                    max_distance_ratio=0.5,
                ),
            ),
            _snapshot((_element("one", "Save", x=0, y=0),)),
            OcrErrorCode.OCR_RELATION_NOT_SATISFIED,
        ),
    ],
)
def test_rejections_keep_not_found_confidence_role_and_relation_distinct(
    target: OcrTargetSpec,
    snapshot: OcrPageSnapshot,
    expected_code: OcrErrorCode,
) -> None:
    with pytest.raises(OcrTargetingError) as exc_info:
        resolve_ocr_target(snapshot, target)

    assert exc_info.value.code == expected_code
    assert exc_info.value.resolution.status == "rejected"


def test_ambiguity_margin_rejects_equally_scored_candidates() -> None:
    target = OcrTargetSpec(
        text="Save",
        language="en",
        min_confidence=0.5,
        min_score=0.5,
        ambiguity_margin=0.1,
    )
    snapshot = _snapshot(
        (
            _element("first", "Save", x=20, y=20),
            _element("second", "Save", x=20, y=80),
        )
    )

    with pytest.raises(OcrTargetingError) as exc_info:
        resolve_ocr_target(snapshot, target)

    assert exc_info.value.code == OcrErrorCode.OCR_TARGET_AMBIGUOUS
    assert len(exc_info.value.candidates) == 2


def test_occurrence_selects_repeated_candidate_in_stable_reading_order() -> None:
    target = OcrTargetSpec(
        text="Save",
        language="en",
        occurrence=2,
        min_confidence=0.5,
        min_score=0.5,
    )
    snapshot = _snapshot(
        (
            _element("bottom", "Save", x=20, y=200),
            _element("top", "Save", x=20, y=20),
        )
    )

    resolution = resolve_ocr_target(snapshot, target)

    assert resolution.selected_candidate is not None
    assert resolution.selected_candidate.element.element_id == "bottom"
    assert [candidate.element.element_id for candidate in resolution.candidates] == [
        "top",
        "bottom",
    ]


def test_min_score_rejects_a_text_match_that_lacks_supporting_score() -> None:
    target = OcrTargetSpec(
        text="Submit",
        match_mode="fuzzy",
        language="en",
        min_confidence=0.1,
        min_score=0.95,
        ambiguity_margin=0.0,
    )
    snapshot = _snapshot(
        (_element("candidate", "Submti", x=20, y=20, confidence=0.4),)
    )

    with pytest.raises(OcrTargetingError) as exc_info:
        resolve_ocr_target(snapshot, target)

    assert exc_info.value.code == OcrErrorCode.OCR_CONFIDENCE_LOW
    assert exc_info.value.candidates[0].total_score < target.min_score
