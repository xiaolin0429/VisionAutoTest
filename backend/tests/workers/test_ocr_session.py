from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from app.workers.ocr_session import PageOcrSession
from app.workers.browser_branching import select_matching_branch
from app.workers.ocr_assertions import evaluate_ocr_assertion
from app.workers.ocr_contract import normalize_ocr_assert_payload
from app.workers.ocr_targeting import OcrTargetingError
from app.workers.ocr_types import OcrErrorCode, OcrTargetSpec

pytestmark = [pytest.mark.vision, pytest.mark.ocr_fake]


@dataclass(frozen=True, slots=True)
class _PageText:
    text: str
    document_y: float
    x: float = 20.0
    width: float = 80.0
    height: float = 18.0
    confidence: float = 0.98
    fixed: bool = False


class _FakePage:
    def __init__(
        self,
        *,
        viewport_width: int = 200,
        viewport_height: int = 100,
        image_scale: float = 1.0,
        browser_dpr: float = 1.0,
        scroll_height: float = 100.0,
        initial_scroll_x: float = 0.0,
        initial_scroll_y: float = 0.0,
        constant_screenshot: bool = False,
        dynamic_growth_height: float | None = None,
        fail_restore: bool = False,
        outlined_screenshot_calls: frozenset[int] = frozenset(),
    ) -> None:
        self.url = "https://example.test/page"
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.image_scale = image_scale
        self.browser_dpr = browser_dpr
        self.scroll_height = scroll_height
        self.scroll_x = initial_scroll_x
        self.scroll_y = initial_scroll_y
        self.initial_scroll_x = initial_scroll_x
        self.initial_scroll_y = initial_scroll_y
        self.constant_screenshot = constant_screenshot
        self.dynamic_growth_height = dynamic_growth_height
        self.fail_restore = fail_restore
        self.outlined_screenshot_calls = outlined_screenshot_calls
        self.has_left_initial_scroll = False
        self.after_scan_restore = False
        self.grew = False
        self.screenshot_calls: list[dict[str, object]] = []
        self.scroll_history: list[tuple[float, float]] = []
        self.wait_history: list[float] = []

    def screenshot(self, **kwargs: object) -> bytes:
        self.screenshot_calls.append(dict(kwargs))
        screenshot_call = len(self.screenshot_calls)
        image_width = int(round(self.viewport_width * self.image_scale))
        image_height = int(round(self.viewport_height * self.image_scale))
        marker = 127 if self.constant_screenshot else int(self.scroll_y) % 251
        if self.after_scan_restore and not self.constant_screenshot:
            marker = (marker + 1) % 251
        image = np.full(
            (image_height, image_width, 3),
            (marker, 255 - marker, marker // 2),
            dtype=np.uint8,
        )
        if screenshot_call in self.outlined_screenshot_calls:
            image.fill(255)
            scale = self.image_scale
            cv2.rectangle(
                image,
                (int(30 * scale), int(20 * scale)),
                (int(130 * scale), int(60 * scale)),
                (20, 20, 20),
                max(1, int(round(2 * scale))),
            )
        success, encoded = cv2.imencode(".png", image)
        assert success
        return encoded.tobytes()

    def evaluate(self, expression: str, arg: object | None = None) -> object:
        if arg is None:
            return {
                "scroll_x": self.scroll_x,
                "scroll_y": self.scroll_y,
                "scroll_width": float(self.viewport_width),
                "scroll_height": self.scroll_height,
                "viewport_width": self.viewport_width,
                "viewport_height": self.viewport_height,
            }
        assert isinstance(arg, Mapping)
        requested_x = float(arg["x"])
        requested_y = float(arg["y"])
        maximum_y = max(0.0, self.scroll_height - self.viewport_height)
        requested_y = min(max(requested_y, 0.0), maximum_y)
        is_restore = (
            self.has_left_initial_scroll
            and requested_x == pytest.approx(self.initial_scroll_x)
            and requested_y == pytest.approx(self.initial_scroll_y)
        )
        if is_restore and self.fail_restore:
            self.scroll_history.append((self.scroll_x, self.scroll_y))
            return None

        self.scroll_x = requested_x
        self.scroll_y = requested_y
        self.scroll_history.append((self.scroll_x, self.scroll_y))
        if (
            self.scroll_x != self.initial_scroll_x
            or self.scroll_y != self.initial_scroll_y
        ):
            self.has_left_initial_scroll = True
        elif is_restore:
            self.after_scan_restore = True

        if (
            self.dynamic_growth_height is not None
            and not self.grew
            and self.scroll_y
            >= max(0.0, self.scroll_height - self.viewport_height) - 0.5
        ):
            self.scroll_height = self.dynamic_growth_height
            self.grew = True
        return None

    def wait_for_timeout(self, timeout_ms: float) -> None:
        self.wait_history.append(timeout_ms)


class _FakeAnalyzer:
    def __init__(
        self,
        *,
        page: _FakePage,
        texts: Sequence[_PageText] = (),
        change_after_restore: bool = False,
        scenes: Sequence[Sequence[_PageText]] | None = None,
    ) -> None:
        self.page = page
        self.texts = tuple(texts)
        self.change_after_restore = change_after_restore
        self.scenes = (
            tuple(tuple(scene) for scene in scenes)
            if scenes is not None
            else None
        )
        self.calls = 0

    def analyze_ocr(
        self,
        *,
        image_png_bytes: bytes,
        language_profile: str | None = None,
    ) -> Mapping[str, object]:
        self.calls += 1
        texts = self.texts
        if self.scenes is not None:
            texts = self.scenes[min(self.calls - 1, len(self.scenes) - 1)]
        image = cv2.imdecode(
            np.frombuffer(image_png_bytes, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        assert image is not None
        image_height, image_width = image.shape[:2]
        blocks: list[dict[str, object]] = []
        for item in texts:
            viewport_y = (
                item.document_y
                if item.fixed
                else item.document_y - self.page.scroll_y
            )
            if viewport_y + item.height <= 0 or viewport_y >= self.page.viewport_height:
                continue
            text = item.text
            if self.change_after_restore and self.page.after_scan_restore:
                text = f"Changed {text}"
            scale = self.page.image_scale
            blocks.append(
                {
                    "order_no": len(blocks) + 1,
                    "text": text,
                    "confidence": item.confidence,
                    "pixel_rect": {
                        "x": int(round(item.x * scale)),
                        "y": int(round(viewport_y * scale)),
                        "width": int(round(item.width * scale)),
                        "height": int(round(item.height * scale)),
                    },
                    "language": "en",
                    "preprocessing_variant": "original",
                }
            )
        return {
            "image_width": image_width,
            "image_height": image_height,
            "language_profiles": ["en"],
            "preprocessing_variants": ["original"],
            "elapsed_ms": 2.0,
            "blocks": blocks,
        }


class _IncrementingClock:
    def __init__(self, *, increment: float) -> None:
        self.value = 0.0
        self.increment = increment

    def __call__(self) -> float:
        current = self.value
        self.value += self.increment
        return current


class _ManualClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _session(
    page: _FakePage,
    analyzer: _FakeAnalyzer,
    **overrides: object,
) -> PageOcrSession:
    options: dict[str, object] = {
        "page": page,
        "analyzer": analyzer,
        "stability_wait_ms": 0.0,
        "cache_memory_limit_bytes": 2 * 1024 * 1024,
    }
    options.update(overrides)
    return PageOcrSession(**options)


def _target(
    text: str,
    *,
    scope: str = "viewport",
    occurrence: int = 1,
) -> OcrTargetSpec:
    return OcrTargetSpec(
        text=text,
        scope=scope,
        occurrence=occurrence,
        language="en",
        min_confidence=0.5,
        min_score=0.5,
        ambiguity_margin=0.05,
    )


def test_viewport_capture_uses_required_options_and_actual_image_scale() -> None:
    page = _FakePage(image_scale=2.0, browser_dpr=3.0)
    analyzer = _FakeAnalyzer(
        page=page,
        texts=(_PageText(text="Submit", document_y=30),),
    )
    session = _session(page, analyzer)

    snapshot = session.recognize_viewport(language_profile="en")

    assert snapshot.device_scale_factor == 2.0
    assert snapshot.elements[0].coordinates.viewport_css_rect.y == pytest.approx(30)
    assert page.screenshot_calls == [
        {
            "type": "png",
            "full_page": False,
            "scale": "css",
            "animations": "disabled",
            "caret": "hide",
        }
    ]


def test_two_level_cache_hits_and_action_invalidation() -> None:
    page = _FakePage(constant_screenshot=True)
    analyzer = _FakeAnalyzer(
        page=page,
        texts=(_PageText(text="Ready", document_y=20),),
    )
    session = _session(page, analyzer)

    first = session.recognize_viewport(language_profile="en")
    second = session.recognize_viewport(language_profile="en")
    session.invalidate("click")
    third = session.recognize_viewport(language_profile="en")

    assert first is second
    assert third is not first
    assert analyzer.calls == 2
    assert session.cache_stats.snapshot_hits == 1
    assert session.cache_stats.generation == 1
    assert session.cache_stats.last_invalidation_reason == "click"


def test_viewport_action_forces_second_screenshot_and_fresh_ocr() -> None:
    page = _FakePage(constant_screenshot=True)
    analyzer = _FakeAnalyzer(
        page=page,
        texts=(_PageText(text="Submit", document_y=20),),
    )
    session = _session(page, analyzer)

    resolution = session.resolve_for_action(_target("Submit"))

    assert resolution.selected_candidate is not None
    assert len(page.screenshot_calls) == 2
    assert analyzer.calls == 2
    evidence = session.evidence_for(resolution)
    assert evidence is not None
    assert evidence.revalidation_required is True
    assert evidence.revalidation_attempted is True
    assert evidence.revalidation_passed is True


def test_non_action_resolution_does_not_apply_action_revalidation() -> None:
    page = _FakePage(constant_screenshot=True)
    analyzer = _FakeAnalyzer(
        page=page,
        texts=(_PageText(text="Ready", document_y=20),),
    )
    session = _session(page, analyzer)

    resolution = session.resolve(_target("Ready"))

    assert len(page.screenshot_calls) == 1
    assert analyzer.calls == 1
    evidence = session.evidence_for(resolution)
    assert evidence is not None
    assert evidence.revalidation_required is False
    assert evidence.revalidation_attempted is False
    assert evidence.revalidation_passed is None


@pytest.mark.parametrize(
    "second_scene",
    [
        (),
        (_PageText(text="Submit", document_y=70),),
        (_PageText(text="Submit changed", document_y=20),),
    ],
    ids=("disappeared", "moved", "matched-text-changed"),
)
def test_viewport_action_rejects_dynamic_target_changes(
    second_scene: Sequence[_PageText],
) -> None:
    page = _FakePage()
    analyzer = _FakeAnalyzer(
        page=page,
        scenes=(
            (_PageText(text="Submit", document_y=20),),
            second_scene,
        ),
    )
    session = _session(page, analyzer)
    target = _target("Submit")
    if second_scene and second_scene[0].text != "Submit":
        target = target.model_copy(update={"match_mode": "contains"})

    with pytest.raises(OcrTargetingError) as exc_info:
        session.resolve_for_action(target)

    assert exc_info.value.code == OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED
    assert len(page.screenshot_calls) == 2
    assert analyzer.calls == 2


def test_viewport_action_rejects_inferred_role_change() -> None:
    page = _FakePage(outlined_screenshot_calls=frozenset({1}))
    analyzer = _FakeAnalyzer(
        page=page,
        texts=(
            _PageText(
                text="Submit",
                document_y=30,
                x=40,
                width=80,
                height=18,
            ),
        ),
    )
    session = _session(page, analyzer)

    with pytest.raises(OcrTargetingError) as exc_info:
        session.resolve_for_action(_target("Submit"))

    assert exc_info.value.code == OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED
    assert analyzer.calls == 2


def test_cache_ttl_and_memory_limit_force_bounded_reanalysis() -> None:
    page = _FakePage(constant_screenshot=True)
    analyzer = _FakeAnalyzer(page=page)
    clock = _ManualClock()
    session = _session(
        page,
        analyzer,
        cache_ttl_seconds=1.0,
        clock=clock,
    )

    session.recognize_viewport(language_profile="en")
    clock.advance(1.1)
    session.recognize_viewport(language_profile="en")

    assert analyzer.calls == 2

    memory_limited_analyzer = _FakeAnalyzer(page=page)
    memory_limited = _session(
        page,
        memory_limited_analyzer,
        cache_memory_limit_bytes=64,
    )
    memory_limited.recognize_viewport(language_profile="en")
    memory_limited.recognize_viewport(language_profile="en")

    assert memory_limited_analyzer.calls == 2
    assert memory_limited.cache_stats.estimated_bytes <= 64


def test_identical_screenshot_hash_reuses_analysis_across_internal_scrolls() -> None:
    page = _FakePage(scroll_height=260, constant_screenshot=True)
    analyzer = _FakeAnalyzer(page=page)
    session = _session(page, analyzer)

    with pytest.raises(OcrTargetingError) as exc_info:
        session.resolve(_target("Missing", scope="page"))

    assert exc_info.value.code == OcrErrorCode.OCR_TARGET_NOT_FOUND
    assert analyzer.calls == 1
    assert session.cache_stats.analysis_hits >= 2
    assert session.cache_stats.generation == 0
    assert page.scroll_y == pytest.approx(0)


def test_dynamic_long_page_restores_then_revalidates_target_in_viewport() -> None:
    page = _FakePage(
        scroll_height=220,
        initial_scroll_x=7,
        initial_scroll_y=25,
        dynamic_growth_height=300,
    )
    analyzer = _FakeAnalyzer(
        page=page,
        texts=(_PageText(text="Footer action", document_y=250, width=100),),
    )
    session = _session(page, analyzer)

    resolution = session.resolve_for_action(
        _target("Footer action", scope="page")
    )

    assert page.grew is True
    assert resolution.selected_candidate is not None
    assert (
        resolution.selected_candidate.element.coordinates.viewport_css_rect.y
        >= 0
    )
    assert (7.0, 25.0) in page.scroll_history
    assert page.scroll_y > page.initial_scroll_y
    assert resolution.scanned_tile_count >= 3
    evidence = session.evidence_for(resolution)
    assert evidence is session.last_action_evidence
    assert evidence is not None
    assert evidence.resolution is resolution
    assert len(evidence.captures) >= resolution.scanned_tile_count
    assert evidence.captures[-1].image_png_bytes.startswith(b"\x89PNG")
    assert evidence.revalidation_required is True
    assert evidence.revalidation_attempted is True
    assert evidence.revalidation_passed is True


def test_restore_failure_overrides_scan_result_and_blocks_action() -> None:
    page = _FakePage(
        scroll_height=260,
        initial_scroll_y=10,
        fail_restore=True,
    )
    analyzer = _FakeAnalyzer(page=page)
    session = _session(page, analyzer)

    with pytest.raises(OcrTargetingError) as exc_info:
        session.resolve_for_action(_target("Missing", scope="page"))

    assert exc_info.value.code == OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED
    with pytest.raises(OcrTargetingError) as blocked:
        session.resolve_for_action(_target("Anything", scope="page"))
    assert blocked.value.code == OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED


def test_fixed_text_is_deduplicated_across_overlapping_tiles() -> None:
    page = _FakePage(scroll_height=260)
    analyzer = _FakeAnalyzer(
        page=page,
        texts=(_PageText(text="Sticky", document_y=10, fixed=True),),
    )
    session = _session(page, analyzer)

    with pytest.raises(OcrTargetingError) as exc_info:
        session.resolve(_target("Sticky", scope="page", occurrence=2))

    assert exc_info.value.code == OcrErrorCode.OCR_TARGET_NOT_FOUND
    assert len(exc_info.value.candidates) == 1
    assert page.scroll_y == pytest.approx(0)


def test_page_scan_detects_duplicate_targets_in_later_tiles() -> None:
    page = _FakePage(scroll_height=260)
    analyzer = _FakeAnalyzer(
        page=page,
        texts=(
            _PageText(text="Save", document_y=20),
            _PageText(text="Save", document_y=200),
        ),
    )
    session = _session(page, analyzer)

    with pytest.raises(OcrTargetingError) as exc_info:
        session.resolve(_target("Save", scope="page"))

    assert exc_info.value.code == OcrErrorCode.OCR_TARGET_AMBIGUOUS
    assert len(exc_info.value.candidates) == 2


def test_page_scan_limit_reports_range_and_restores_initial_scroll() -> None:
    page = _FakePage(scroll_height=500, initial_scroll_y=15)
    analyzer = _FakeAnalyzer(page=page)
    session = _session(page, analyzer, max_page_tiles=2)

    with pytest.raises(OcrTargetingError) as exc_info:
        session.resolve(_target("Missing", scope="page"))

    assert exc_info.value.code == OcrErrorCode.OCR_PAGE_SCAN_LIMIT
    assert exc_info.value.resolution.scanned_tile_count == 2
    assert "document y=" in str(exc_info.value)
    assert page.scroll_y == pytest.approx(15)


def test_page_scan_total_timeout_uses_scan_limit_error() -> None:
    page = _FakePage(scroll_height=500, initial_scroll_y=12)
    analyzer = _FakeAnalyzer(page=page)
    clock = _IncrementingClock(increment=1.0)
    session = _session(
        page,
        analyzer,
        total_timeout_seconds=0.5,
        clock=clock,
    )

    with pytest.raises(OcrTargetingError) as exc_info:
        session.resolve(_target("Missing", scope="page"))

    assert exc_info.value.code == OcrErrorCode.OCR_PAGE_SCAN_LIMIT
    assert "timeout" in str(exc_info.value)
    assert page.scroll_y == pytest.approx(12)


def test_page_target_change_during_revalidation_is_rejected() -> None:
    page = _FakePage(scroll_height=260)
    analyzer = _FakeAnalyzer(
        page=page,
        texts=(_PageText(text="Pay now", document_y=210),),
        change_after_restore=True,
    )
    session = _session(page, analyzer)

    with pytest.raises(OcrTargetingError) as exc_info:
        session.resolve_for_action(_target("Pay now", scope="page"))

    assert exc_info.value.code == OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED


def test_page_count_assertion_uses_deduplicated_candidates() -> None:
    page = _FakePage(scroll_height=260)
    analyzer = _FakeAnalyzer(
        page=page,
        texts=(_PageText(text="Sticky", document_y=10, fixed=True),),
    )
    session = _session(page, analyzer)
    payload = normalize_ocr_assert_payload(
        {
            "scope": "page",
            "assertion": "count",
            "expected_count": 1,
            "ocr_target": {
                "text": "Sticky",
                "scope": "page",
                "language": "en",
            },
        }
    )

    result = evaluate_ocr_assertion(payload, resolve=session.resolve)

    assert result.status == "passed"
    assert result.matched_count == 1
    assert len(page.screenshot_calls) >= 3
    assert all(call["full_page"] is False for call in page.screenshot_calls)


def test_branch_ocr_conditions_share_session_snapshot_cache() -> None:
    page = _FakePage(constant_screenshot=True)
    analyzer = _FakeAnalyzer(
        page=page,
        texts=(_PageText(text="Ready", document_y=20),),
    )
    session = _session(page, analyzer)
    payload = {
        "branches": [
            {
                "branch_key": "missing",
                "condition": {
                    "type": "ocr_text_visible",
                    "expected_text": "Missing",
                },
            },
            {
                "branch_key": "ready",
                "condition": {
                    "type": "ocr_text_visible",
                    "ocr_target": {
                        "text": "Ready",
                    },
                },
            },
        ]
    }

    selected = select_matching_branch(
        None,
        page,
        payload=payload,
        template_contexts={},
        ocr_session=session,
    )

    assert selected is not None
    assert selected["branch_key"] == "ready"
    assert analyzer.calls == 1
    assert session.cache_stats.snapshot_hits == 1
