from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.http import ApiError
from app.services.execution_readiness import (
    inspect_execution_step_issues,
    validate_visual_step_readiness,
)
from app.workers.browser_branching import evaluate_branch_condition
from app.workers.browser_step_handlers import execute_ocr_assert
from app.workers.ocr_assertions import evaluate_ocr_assertion
from app.workers.ocr_contract import normalize_ocr_assert_payload
from app.workers.ocr_engine import OcrEngineError
from app.workers.ocr_targeting import OcrTargetingError, resolve_ocr_target
from app.workers.ocr_types import (
    OcrCoordinateSet,
    OcrElementRelation,
    OcrErrorCode,
    OcrPageSnapshot,
    OcrRatioRect,
    OcrRect,
    OcrTargetResolution,
    OcrTargetSpec,
    OcrTextElement,
)

pytestmark = pytest.mark.ocr_fake


def _element(
    element_id: str,
    text: str,
    *,
    x: float,
    y: float,
    confidence: float = 0.98,
) -> OcrTextElement:
    rect = OcrRect(x=x, y=y, width=100, height=24)
    return OcrTextElement(
        element_id=element_id,
        text=text,
        confidence=confidence,
        line_ids=(),
        coordinates=OcrCoordinateSet(
            pixel_rect=rect,
            ratio_rect=OcrRatioRect(
                x=x / 1000,
                y=y / 1000,
                width=0.1,
                height=0.024,
            ),
            viewport_css_rect=rect,
            document_css_rect=rect,
        ),
        role="text",
        role_confidence=0.9,
    )


def _snapshot(
    *elements: OcrTextElement,
    relations: tuple[OcrElementRelation, ...] = (),
) -> OcrPageSnapshot:
    return OcrPageSnapshot(
        image_width_px=1000,
        image_height_px=1000,
        viewport_width_css=1000,
        viewport_height_css=1000,
        device_scale_factor=1,
        scroll_x_css=0,
        scroll_y_css=0,
        language_profiles=("zh_en",),
        preprocessing_variants=("original",),
        screenshot_checksum_sha256="a" * 64,
        elapsed_ms=1,
        elements=elements,
        relations=relations,
    )


def _rejection(
    target: OcrTargetSpec,
    code: OcrErrorCode,
) -> OcrTargetingError:
    return OcrTargetingError(
        OcrTargetResolution(
            status="rejected",
            target=target,
            error_code=code,
            error_message=f"{code.value} rejection",
        )
    )


def test_present_and_relation_assertions_use_unified_targeting() -> None:
    target = _element("target", "提交成功", x=200, y=100)
    anchor = _element("anchor", "状态", x=20, y=100)
    relation = OcrElementRelation(
        source_element_id="target",
        target_element_id="anchor",
        type="right_of",
        distance_ratio=0.2,
        confidence=0.95,
    )
    snapshot = _snapshot(target, anchor, relations=(relation,))

    present = normalize_ocr_assert_payload(
        {
            "scope": "viewport",
            "assertion": "present",
            "ocr_target": {"text": "提交成功"},
        }
    )
    related = normalize_ocr_assert_payload(
        {
            "scope": "viewport",
            "assertion": "relation",
            "ocr_target": {
                "text": "提交成功",
                "relation": {
                    "type": "right_of",
                    "anchor_text": "状态",
                    "max_distance_ratio": 0.3,
                },
            },
        }
    )

    present_result = evaluate_ocr_assertion(
        present,
        resolve=lambda spec: resolve_ocr_target(snapshot, spec),
    )
    relation_result = evaluate_ocr_assertion(
        related,
        resolve=lambda spec: resolve_ocr_target(snapshot, spec),
    )

    assert present_result.status == "passed"
    assert relation_result.status == "passed"


def test_absent_only_passes_for_target_not_found() -> None:
    payload = normalize_ocr_assert_payload(
        {
            "scope": "viewport",
            "assertion": "absent",
            "ocr_target": {"text": "错误提示"},
        }
    )

    not_found = evaluate_ocr_assertion(
        payload,
        resolve=lambda target: (_ for _ in ()).throw(
            _rejection(target, OcrErrorCode.OCR_TARGET_NOT_FOUND)
        ),
    )
    low_confidence = evaluate_ocr_assertion(
        payload,
        resolve=lambda target: (_ for _ in ()).throw(
            _rejection(target, OcrErrorCode.OCR_CONFIDENCE_LOW)
        ),
    )

    assert not_found.status == "passed"
    assert low_confidence.status == "failed"


def test_page_scan_limit_is_runtime_error_not_assertion_failure() -> None:
    payload = normalize_ocr_assert_payload(
        {
            "scope": "page",
            "assertion": "present",
            "ocr_target": {"text": "页脚", "scope": "page"},
        }
    )

    result = evaluate_ocr_assertion(
        payload,
        resolve=lambda target: (_ for _ in ()).throw(
            _rejection(target, OcrErrorCode.OCR_PAGE_SCAN_LIMIT)
        ),
    )

    assert result.status == "error"
    assert result.score_value is None


def test_count_uses_all_qualified_candidates() -> None:
    snapshot = _snapshot(
        _element("first", "保存", x=20, y=20),
        _element("second", "保存", x=20, y=80),
    )
    payload = normalize_ocr_assert_payload(
        {
            "scope": "page",
            "assertion": "count",
            "expected_count": 2,
            "ocr_target": {"text": "保存", "scope": "page"},
        }
    )

    result = evaluate_ocr_assertion(
        payload,
        resolve=lambda target: resolve_ocr_target(snapshot, target),
    )

    assert result.status == "passed"
    assert result.matched_count == 2


class _FakeLocator:
    def __init__(self) -> None:
        self.screenshot_calls: list[dict[str, object]] = []

    def screenshot(self, **kwargs: object) -> bytes:
        self.screenshot_calls.append(dict(kwargs))
        return b"legacy-png"


class _FakePage:
    def __init__(self) -> None:
        self.locator_value = _FakeLocator()
        self.locator_selectors: list[str] = []
        self.screenshot_calls: list[dict[str, object]] = []

    def locator(self, selector: str) -> _FakeLocator:
        self.locator_selectors.append(selector)
        return self.locator_value

    def screenshot(self, **kwargs: object) -> bytes:
        self.screenshot_calls.append(dict(kwargs))
        return b"viewport-png"


class _FakeSession:
    def __init__(self, snapshot: OcrPageSnapshot) -> None:
        self.snapshot = snapshot
        self.targets: list[OcrTargetSpec] = []

    def resolve(self, target: OcrTargetSpec) -> OcrTargetResolution:
        self.targets.append(target)
        return resolve_ocr_target(self.snapshot, target)


def test_legacy_handler_uses_locator_screenshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _snapshot(_element("target", "成功", x=20, y=20))
    monkeypatch.setitem(
        execute_ocr_assert.__globals__,
        "_build_legacy_ocr_snapshot",
        lambda *_args, **_kwargs: snapshot,
    )
    page = _FakePage()
    adapter = SimpleNamespace(_ocr_analyzer=object())
    step = SimpleNamespace(
        step_no=1,
        payload_json={
            "scope": "element_legacy",
            "assertion": "present",
            "selector": "#result",
            "ocr_target": {"text": "成功"},
        },
    )

    outcome = execute_ocr_assert(
        adapter,
        page,
        step=step,
        case_run_id=7,
        timeout_ms=15000,
    )

    assert outcome.status == "passed"
    assert page.locator_selectors == ["#result"]
    assert page.locator_value.screenshot_calls == [
        {"type": "png", "timeout": 15000}
    ]
    assert page.screenshot_calls == []
    assert outcome.actual_artifact is not None
    assert outcome.actual_artifact.content_bytes == b"legacy-png"


def test_old_legacy_payload_keeps_region_assertion_behavior() -> None:
    class LegacyVisionAdapter:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def assert_ocr(self, **kwargs: object) -> SimpleNamespace:
            self.calls.append(kwargs)
            return SimpleNamespace(
                status="passed",
                score_value=1.0,
                error_message=None,
                actual_artifact=None,
            )

    page = _FakePage()
    vision_adapter = LegacyVisionAdapter()
    step = SimpleNamespace(
        step_no=3,
        payload_json={
            "selector": "#legacy",
            "expected_text": "完整 区域文字",
            "match_mode": "exact",
            "case_sensitive": True,
        },
    )

    outcome = execute_ocr_assert(
        SimpleNamespace(_vision_adapter=vision_adapter),
        page,
        step=step,
        case_run_id=9,
        timeout_ms=5000,
    )

    assert outcome.status == "passed"
    assert vision_adapter.calls[0]["image_png_bytes"] == b"legacy-png"
    assert vision_adapter.calls[0]["expected_text"] == "完整 区域文字"
    assert vision_adapter.calls[0]["match_mode"] == "exact"
    assert vision_adapter.calls[0]["case_sensitive"] is True


def test_legacy_analyzer_failure_uses_typed_ocr_error() -> None:
    class FailingAnalyzer:
        def analyze_ocr(self, **_kwargs: object) -> dict[str, object]:
            raise RuntimeError("decoder failed")

    step = SimpleNamespace(
        step_no=3,
        payload_json={
            "scope": "element_legacy",
            "assertion": "absent",
            "selector": "#legacy",
            "ocr_target": {"text": "错误"},
        },
    )

    with pytest.raises(OcrEngineError) as exc_info:
        execute_ocr_assert(
            SimpleNamespace(_ocr_analyzer=FailingAnalyzer()),
            _FakePage(),
            step=step,
            case_run_id=9,
            timeout_ms=5000,
        )

    assert exc_info.value.code == OcrErrorCode.OCR_ANALYSIS_FAILED


def test_pure_handler_uses_viewport_artifact_and_session() -> None:
    snapshot = _snapshot(_element("target", "成功", x=20, y=20))
    page = _FakePage()
    session = _FakeSession(snapshot)
    step = SimpleNamespace(
        step_no=2,
        payload_json={
            "scope": "viewport",
            "assertion": "present",
            "ocr_target": {"text": "成功"},
        },
    )

    outcome = execute_ocr_assert(
        SimpleNamespace(),
        page,
        step=step,
        case_run_id=8,
        timeout_ms=15000,
        ocr_session=session,
    )

    assert outcome.status == "passed"
    assert page.locator_selectors == []
    assert page.screenshot_calls == [{"type": "png", "full_page": False}]
    assert session.targets[0].scope == "viewport"
    assert outcome.result_metadata_json["ocr"]["assertion"] == "present"


def test_passing_absent_assertion_does_not_expose_not_found_as_error() -> None:
    class NotFoundSession:
        def resolve(self, target: OcrTargetSpec) -> OcrTargetResolution:
            raise _rejection(target, OcrErrorCode.OCR_TARGET_NOT_FOUND)

    outcome = execute_ocr_assert(
        SimpleNamespace(),
        _FakePage(),
        step=SimpleNamespace(
            step_no=2,
            payload_json={
                "scope": "viewport",
                "assertion": "absent",
                "ocr_target": {"text": "错误提示"},
            },
        ),
        case_run_id=8,
        timeout_ms=15000,
        ocr_session=NotFoundSession(),
    )

    assert outcome.status == "passed"
    assert "error_code" not in outcome.result_metadata_json["ocr"]


@pytest.mark.parametrize(
    "condition",
    [
        {
            "type": "ocr_text_visible",
            "expected_text": "旧目标",
            "match_mode": "contains",
        },
        {
            "type": "ocr_text_visible",
            "ocr_target": {"text": "新目标"},
        },
    ],
)
def test_branch_condition_parses_legacy_and_new_targets(
    condition: dict[str, object],
) -> None:
    class ResolvingSession:
        def resolve(self, target: OcrTargetSpec) -> OcrTargetResolution:
            assert target.text in {"旧目标", "新目标"}
            return OcrTargetResolution(status="resolved", target=target)

    assert (
        evaluate_branch_condition(
            None,
            object(),
            condition=condition,
            template_contexts={},
            ocr_session=ResolvingSession(),
        )
        is True
    )


def test_branch_condition_only_converts_not_found_to_false() -> None:
    class RejectingSession:
        def __init__(self, code: OcrErrorCode) -> None:
            self.code = code

        def resolve(self, target: OcrTargetSpec) -> OcrTargetResolution:
            raise _rejection(target, self.code)

    condition = {
        "type": "ocr_text_visible",
        "ocr_target": {"text": "目标"},
    }
    assert (
        evaluate_branch_condition(
            None,
            object(),
            condition=condition,
            template_contexts={},
            ocr_session=RejectingSession(OcrErrorCode.OCR_TARGET_NOT_FOUND),
        )
        is False
    )
    with pytest.raises(OcrTargetingError) as exc_info:
        evaluate_branch_condition(
            None,
            object(),
            condition=condition,
            template_contexts={},
            ocr_session=RejectingSession(OcrErrorCode.OCR_CONFIDENCE_LOW),
        )
    assert exc_info.value.code == OcrErrorCode.OCR_CONFIDENCE_LOW


def test_branch_condition_propagates_engine_errors() -> None:
    class FailingSession:
        def resolve(self, _target: OcrTargetSpec) -> OcrTargetResolution:
            raise OcrEngineError(
                OcrErrorCode.OCR_MODEL_UNAVAILABLE,
                "model unavailable",
            )

    with pytest.raises(OcrEngineError) as exc_info:
        evaluate_branch_condition(
            None,
            object(),
            condition={
                "type": "ocr_text_visible",
                "ocr_target": {"text": "目标"},
            },
            template_contexts={},
            ocr_session=FailingSession(),
        )
    assert exc_info.value.code == OcrErrorCode.OCR_MODEL_UNAVAILABLE


def test_readiness_accepts_pure_ocr_and_recurses_into_branch_steps() -> None:
    branch_step = SimpleNamespace(
        step_type="conditional_branch",
        step_name="OCR Branch",
        template_id=None,
        payload_json={
            "branches": [
                {
                    "branch_key": "visible",
                    "condition": {
                        "type": "ocr_text_visible",
                        "ocr_target": {"text": "Ready"},
                    },
                    "steps": [
                        {
                            "step_type": "ocr_assert",
                            "step_name": "Nested OCR",
                            "payload_json": {
                                "scope": "viewport",
                                "assertion": "relation",
                                "ocr_target": {
                                    "text": "Ready",
                                    "relation": {
                                        "type": "right_of",
                                        "anchor_text": "Status",
                                    },
                                },
                            },
                        }
                    ],
                }
            ]
        },
    )

    validate_visual_step_readiness(None, workspace_id=1, step=branch_step)
    issues = inspect_execution_step_issues(
        None,
        workspace_id=1,
        step=branch_step,
        route_path="/cases",
    )

    assert issues == []


def test_readiness_rejects_invalid_count_assertion() -> None:
    step = SimpleNamespace(
        step_type="ocr_assert",
        step_name="Invalid Count",
        template_id=None,
        payload_json={
            "scope": "viewport",
            "assertion": "count",
            "ocr_target": {"text": "Ready"},
        },
    )

    with pytest.raises(ApiError) as exc_info:
        validate_visual_step_readiness(None, workspace_id=1, step=step)
    issues = inspect_execution_step_issues(
        None,
        workspace_id=1,
        step=step,
        route_path="/components",
    )

    assert exc_info.value.code == "STEP_CONFIGURATION_INVALID"
    assert [issue["code"] for issue in issues] == ["STEP_CONFIGURATION_INVALID"]


def test_readiness_revalidates_selector_branch_condition() -> None:
    step = SimpleNamespace(
        step_type="conditional_branch",
        step_name="Invalid selector branch",
        template_id=None,
        payload_json={
            "branches": [
                {
                    "branch_key": "selector",
                    "condition": {
                        "type": "selector_exists",
                        "selector": "",
                    },
                    "steps": [
                        {
                            "step_type": "wait",
                            "step_name": "Wait",
                            "payload_json": {"ms": 1},
                        }
                    ],
                }
            ]
        },
    )

    with pytest.raises(ApiError) as exc_info:
        validate_visual_step_readiness(None, workspace_id=1, step=step)
    issues = inspect_execution_step_issues(
        None,
        workspace_id=1,
        step=step,
        route_path="/cases",
    )

    assert exc_info.value.code == "STEP_CONFIGURATION_INVALID"
    assert [issue["code"] for issue in issues] == ["STEP_CONFIGURATION_INVALID"]


def test_hard_readiness_revalidates_template_branch_condition() -> None:
    class MissingTemplateSession:
        def get(self, _model: object, _resource_id: int) -> None:
            return None

    step = SimpleNamespace(
        step_type="conditional_branch",
        step_name="Missing template branch",
        template_id=None,
        payload_json={
            "branches": [
                {
                    "branch_key": "template",
                    "condition": {
                        "type": "template_visible",
                        "template_id": 99,
                    },
                    "steps": [
                        {
                            "step_type": "wait",
                            "step_name": "Wait",
                            "payload_json": {"ms": 1},
                        }
                    ],
                }
            ]
        },
    )

    with pytest.raises(ApiError) as exc_info:
        validate_visual_step_readiness(
            MissingTemplateSession(),
            workspace_id=1,
            step=step,
        )

    assert exc_info.value.code == "TEMPLATE_NOT_FOUND"
