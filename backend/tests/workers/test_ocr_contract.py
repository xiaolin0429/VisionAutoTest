from __future__ import annotations

from typing import Any

import pytest

from app.workers.ocr_contract import (
    OcrContractError,
    normalize_ocr_assert_payload,
    normalize_ocr_target_payload,
)
from app.workers.ocr_types import (
    OcrCoordinateSet,
    OcrElementRelation,
    OcrErrorCode,
    OcrPageSnapshot,
    OcrRatioRect,
    OcrRect,
    OcrTargetCandidate,
    OcrTargetResolution,
    OcrTextElement,
)

pytestmark = pytest.mark.ocr_fake


@pytest.mark.parametrize("match_mode", ["exact", "contains", "regex", "fuzzy"])
def test_nested_ocr_target_supports_all_match_modes(match_mode: str) -> None:
    text = "^提交成功$" if match_mode == "regex" else "提交成功"
    target = normalize_ocr_target_payload(
        {
            "ocr_target": {
                "text": text,
                "match_mode": match_mode,
                "case_sensitive": True,
                "occurrence": 2,
                "scope": "page",
                "language": "zh_en",
                "role": "button",
                "min_confidence": 0.8,
                "min_score": 0.85,
                "ambiguity_margin": 0.15,
                "action_point": "associated_control",
                "relation": {
                    "type": "right_of",
                    "anchor_text": "操作",
                    "max_distance_ratio": 0.3,
                },
            }
        }
    )

    assert target.match_mode == match_mode
    assert target.scope == "page"
    assert target.language == "zh_en"
    assert target.role == "button"
    assert target.relation is not None
    assert target.relation.type == "right_of"


def test_nested_ocr_target_is_authoritative_over_legacy_fields() -> None:
    target = normalize_ocr_target_payload(
        {
            "ocr_text": "",
            "ocr_occurrence": 0,
            "ocr_target": {
                "text": "嵌套目标",
                "match_mode": "exact",
            },
        }
    )

    assert target.text == "嵌套目标"
    assert target.occurrence == 1


def test_legacy_ocr_locator_is_normalized_without_changing_defaults() -> None:
    target = normalize_ocr_target_payload(
        {
            "ocr_text": " 登录 ",
            "ocr_match_mode": "contains",
            "ocr_case_sensitive": False,
            "ocr_occurrence": 3,
        }
    )

    assert target.text == "登录"
    assert target.match_mode == "contains"
    assert target.occurrence == 3
    assert target.scope == "viewport"
    assert target.language == "zh_en"


def test_selector_ocr_assert_without_scope_maps_to_element_legacy() -> None:
    normalized = normalize_ocr_assert_payload(
        {
            "selector": " #main ",
            "expected_text": "成功",
            "match_mode": "exact",
            "case_sensitive": True,
        }
    )

    assert normalized.scope == "element_legacy"
    assert normalized.selector == "#main"
    assert normalized.is_legacy is True
    assert normalized.target.text == "成功"
    assert normalized.target.case_sensitive is True


def test_pure_ocr_assert_uses_outer_page_scope() -> None:
    normalized = normalize_ocr_assert_payload(
        {
            "scope": "page",
            "ocr_target": {
                "text": "提交成功",
                "match_mode": "fuzzy",
                "language": "auto",
            },
        }
    )

    assert normalized.scope == "page"
    assert normalized.target.scope == "page"
    assert normalized.selector is None
    assert normalized.is_legacy is False


def test_pure_ocr_assert_uses_nested_scope_when_outer_scope_is_omitted() -> None:
    normalized = normalize_ocr_assert_payload(
        {
            "ocr_target": {
                "text": "提交成功",
                "scope": "page",
            },
        }
    )

    assert normalized.scope == "page"
    assert normalized.target.scope == "page"


@pytest.mark.parametrize("assertion", ["present", "absent", "relation"])
def test_ocr_assertion_modes_are_normalized(assertion: str) -> None:
    target: dict[str, object] = {"text": "提交成功"}
    if assertion == "relation":
        target["relation"] = {
            "type": "right_of",
            "anchor_text": "状态",
        }

    normalized = normalize_ocr_assert_payload(
        {
            "scope": "viewport",
            "assertion": assertion,
            "ocr_target": target,
        }
    )

    assert normalized.assertion == assertion
    assert normalized.expected_count is None


def test_count_assertion_requires_non_negative_expected_count() -> None:
    normalized = normalize_ocr_assert_payload(
        {
            "scope": "page",
            "assertion": "count",
            "expected_count": 0,
            "ocr_target": {"text": "错误", "scope": "page"},
        }
    )

    assert normalized.assertion == "count"
    assert normalized.expected_count == 0

    for invalid_count in (None, True, -1, 1.5):
        with pytest.raises(OcrContractError, match="expected_count"):
            normalize_ocr_assert_payload(
                {
                    "scope": "viewport",
                    "assertion": "count",
                    "expected_count": invalid_count,
                    "ocr_target": {"text": "错误"},
                }
            )


def test_relation_assertion_requires_relation_target() -> None:
    with pytest.raises(OcrContractError, match="ocr_target.relation"):
        normalize_ocr_assert_payload(
            {
                "scope": "viewport",
                "assertion": "relation",
                "ocr_target": {"text": "提交成功"},
            }
        )


@pytest.mark.parametrize(
    "target",
    [
        {"text": "", "match_mode": "exact"},
        {"text": "(", "match_mode": "regex"},
        {"text": "目标", "occurrence": True},
        {"text": "目标", "min_confidence": -0.1},
        {"text": "目标", "min_score": 1.1},
        {"text": "目标", "role": "link"},
        {
            "text": "目标",
            "relation": {
                "type": "diagonal",
                "anchor_text": "锚点",
            },
        },
        {
            "text": "目标",
            "relation": {
                "type": "nearest",
                "anchor_text": "",
            },
        },
    ],
)
def test_invalid_nested_ocr_target_is_rejected(
    target: dict[str, Any],
) -> None:
    with pytest.raises(OcrContractError):
        normalize_ocr_target_payload({"ocr_target": target})


def test_assertion_scope_conflict_is_rejected() -> None:
    with pytest.raises(OcrContractError, match="conflicts"):
        normalize_ocr_assert_payload(
            {
                "scope": "page",
                "ocr_target": {
                    "text": "目标",
                    "scope": "viewport",
                },
            }
        )


def test_snapshot_candidate_resolution_and_error_code_contracts() -> None:
    coordinates = OcrCoordinateSet(
        pixel_rect=OcrRect(x=10, y=20, width=80, height=24),
        ratio_rect=OcrRatioRect(x=0.1, y=0.2, width=0.2, height=0.1),
        viewport_css_rect=OcrRect(x=5, y=10, width=40, height=12),
        document_css_rect=OcrRect(x=5, y=110, width=40, height=12),
    )
    element = OcrTextElement(
        element_id="element-1",
        text="提交",
        confidence=0.96,
        line_ids=("line-1",),
        coordinates=coordinates,
        role="button",
        role_confidence=0.9,
        role_evidence=("enclosed_rect",),
    )
    relation = OcrElementRelation(
        source_element_id="element-1",
        target_element_id="element-2",
        type="right_of",
        distance_ratio=0.1,
        confidence=0.92,
    )
    candidate = OcrTargetCandidate(
        element=element,
        text_score=1.0,
        confidence_score=0.96,
        role_score=0.9,
        relation_score=0.92,
        distance_score=0.9,
        variant_consistency_score=1.0,
        total_score=0.95,
        matched_relations=(relation,),
    )
    snapshot = OcrPageSnapshot(
        image_width_px=200,
        image_height_px=100,
        viewport_width_css=100,
        viewport_height_css=50,
        device_scale_factor=2.0,
        scroll_x_css=0,
        scroll_y_css=100,
        language_profiles=("zh_en",),
        preprocessing_variants=("original",),
        screenshot_checksum_sha256="a" * 64,
        elapsed_ms=12.5,
        elements=(element,),
        relations=(relation,),
    )
    target = normalize_ocr_target_payload({"ocr_target": {"text": "提交"}})
    resolution = OcrTargetResolution(
        status="resolved",
        target=target,
        selected_candidate=candidate,
        candidates=(candidate,),
        scanned_tile_count=1,
        elapsed_ms=20,
    )

    assert snapshot.elements[0].coordinates.document_css_rect.y == 110
    assert resolution.selected_candidate is not None
    assert (
        OcrErrorCode.OCR_TARGET_AMBIGUOUS.value
        == "OCR_TARGET_AMBIGUOUS"
    )
