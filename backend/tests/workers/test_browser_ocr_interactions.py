from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.workers import browser_locators
from app.workers.browser import PlaywrightBrowserExecutionAdapter
from app.workers.ocr_targeting import OcrTargetingError
from app.workers.ocr_types import (
    OcrCoordinateSet,
    OcrErrorCode,
    OcrPoint,
    OcrRatioRect,
    OcrRect,
    OcrTargetCandidate,
    OcrTargetResolution,
    OcrTargetSpec,
    OcrTextElement,
)

pytestmark = pytest.mark.ocr_fake


def _resolution(
    target: OcrTargetSpec,
    *,
    matched_text: str | None = None,
    viewport_rect: OcrRect | None = None,
    associated_control_rect: OcrRect | None = None,
) -> OcrTargetResolution:
    rect = viewport_rect or OcrRect(x=40, y=30, width=80, height=20)
    element = OcrTextElement(
        element_id="element-0001",
        text=matched_text or target.text,
        confidence=0.98,
        line_ids=("line-0001",),
        coordinates=OcrCoordinateSet(
            pixel_rect=rect,
            ratio_rect=OcrRatioRect(
                x=rect.x / 800,
                y=rect.y / 600,
                width=rect.width / 800,
                height=rect.height / 600,
            ),
            viewport_css_rect=rect,
            document_css_rect=rect,
        ),
        role="input" if associated_control_rect is not None else "button",
        role_confidence=0.95,
        associated_control_rect=associated_control_rect,
        associated_control_candidates=(
            (associated_control_rect,) if associated_control_rect is not None else ()
        ),
        association_confidence=0.93 if associated_control_rect is not None else 0,
    )
    candidate = OcrTargetCandidate(
        element=element,
        text_score=1,
        confidence_score=0.98,
        role_score=0.95,
        relation_score=1,
        distance_score=1,
        variant_consistency_score=1,
        total_score=0.97,
    )
    return OcrTargetResolution(
        status="resolved",
        target=target,
        selected_candidate=candidate,
        candidates=(candidate,),
        scanned_tile_count=1,
        elapsed_ms=2,
    )


class _RecordingSession:
    def __init__(self) -> None:
        self.events: list[str] = []

    def resolve_for_action(self, target: OcrTargetSpec) -> OcrTargetResolution:
        self.events.append(f"resolve_for_action:{target.text}")
        associated_rect = (
            OcrRect(x=180, y=120, width=240, height=48)
            if target.action_point == "associated_control"
            else None
        )
        return _resolution(target, associated_control_rect=associated_rect)

    def resolve(self, target: OcrTargetSpec) -> OcrTargetResolution:
        self.events.append(f"resolve:{target.text}")
        return _resolution(target)

    def invalidate(self, reason: str) -> None:
        self.events.append(f"invalidate:{reason}")


class _RecordingMouse:
    def __init__(self) -> None:
        self.clicks: list[tuple[float, float]] = []
        self.events: list[tuple[object, ...]] = []

    def click(self, x: float, y: float) -> None:
        self.clicks.append((x, y))
        self.events.append(("click", x, y))

    def move(self, x: float, y: float) -> None:
        self.events.append(("move", x, y))

    def wheel(self, delta_x: float, delta_y: float) -> None:
        self.events.append(("wheel", delta_x, delta_y))

    def down(self, *, button: str) -> None:
        self.events.append(("down", button))

    def up(self, *, button: str) -> None:
        self.events.append(("up", button))


class _RecordingKeyboard:
    def __init__(self) -> None:
        self.typed: list[tuple[str, int | None]] = []
        self.pressed: list[str] = []

    def type(self, text: str, delay: int | None = None) -> None:
        self.typed.append((text, delay))

    def insert_text(self, text: str) -> None:
        self.typed.append((text, None))

    def press(self, key: str) -> None:
        self.pressed.append(key)


class _NoDomPage:
    def __init__(self) -> None:
        self.mouse = _RecordingMouse()
        self.keyboard = _RecordingKeyboard()
        self.navigations: list[str] = []

    def wait_for_timeout(self, timeout_ms: float) -> None:
        _ = timeout_ms

    def goto(self, url: str, **_kwargs: object) -> None:
        self.navigations.append(url)


@pytest.mark.parametrize(
    ("payload", "expected_match_mode"),
    [
        (
            {
                "locator": "ocr",
                "ocr_target": {
                    "text": "Account",
                    "action_point": "associated_control",
                },
            },
            "exact",
        ),
        (
            {
                "locator": "ocr",
                "ocr_text": "Account",
                "ocr_match_mode": "contains",
            },
            "contains",
        ),
    ],
)
def test_ocr_locator_uses_case_session_and_returns_css_viewport_point(
    payload: dict[str, object],
    expected_match_mode: str,
) -> None:
    session = _RecordingSession()

    target = browser_locators.resolve_ocr_target(session, payload)

    assert target.resolution.target.match_mode == expected_match_mode
    if payload.get("ocr_target") is not None:
        assert target.point == OcrPoint(x=300, y=144)
    else:
        assert target.point == OcrPoint(x=80, y=40)


def test_pure_ocr_input_uses_mouse_and_keyboard_without_dom_value_checks() -> None:
    adapter = PlaywrightBrowserExecutionAdapter(
        headless=True,
        navigation_timeout_ms=1000,
    )
    page = _NoDomPage()
    session = _RecordingSession()
    secret = "not-for-metadata"
    step = SimpleNamespace(
        step_no=1,
        step_type="input",
        payload_json={
            "locator": "ocr",
            "ocr_target": {
                "text": "Account",
                "role": "label",
                "action_point": "associated_control",
            },
            "text": secret,
            "input_mode": "fill",
            "verify_ocr": True,
            "input_is_sensitive": True,
        },
        timeout_ms=1000,
        template_id=None,
    )

    outcome = adapter._execute_step(
        page,
        base_url="https://example.test",
        step=step,
        case_run_id=1,
        template_contexts={},
        ocr_session=session,
    )

    assert outcome.status == "passed"
    assert page.mouse.clicks == [(300, 144)]
    assert page.keyboard.pressed == ["ControlOrMeta+A", "Backspace"]
    assert page.keyboard.typed == [(secret, None)]
    assert session.events == [
        "resolve_for_action:Account",
        "invalidate:input",
        f"resolve:{secret}",
    ]
    assert secret not in repr(outcome.result_metadata_json)


class _RevalidationFailingSession:
    def resolve_for_action(
        self,
        target: OcrTargetSpec,
    ) -> OcrTargetResolution:
        raise OcrTargetingError(
            OcrTargetResolution(
                status="rejected",
                target=target,
                error_code=OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED,
                error_message="The second OCR action capture changed.",
            )
        )


@pytest.mark.parametrize(
    ("step_type", "payload"),
    [
        (
            "click",
            {"locator": "ocr", "ocr_target": {"text": "Run"}},
        ),
        (
            "input",
            {
                "locator": "ocr",
                "ocr_target": {"text": "Account"},
                "text": "blocked",
                "input_mode": "fill",
            },
        ),
        (
            "long_press",
            {
                "locator": "ocr",
                "ocr_target": {"text": "Hold"},
                "duration_ms": 100,
            },
        ),
        (
            "scroll",
            {
                "target": "element",
                "locator": "ocr",
                "ocr_target": {"text": "Panel"},
                "direction": "down",
                "distance": 100,
            },
        ),
    ],
)
def test_ocr_action_revalidation_failure_performs_no_mouse_or_keyboard_call(
    step_type: str,
    payload: dict[str, object],
) -> None:
    adapter = PlaywrightBrowserExecutionAdapter(
        headless=True,
        navigation_timeout_ms=1000,
    )
    page = _NoDomPage()

    with pytest.raises(OcrTargetingError) as exc_info:
        adapter._execute_step(
            page,
            base_url="https://example.test",
            step=SimpleNamespace(
                step_no=1,
                step_type=step_type,
                payload_json=payload,
                timeout_ms=1000,
                template_id=None,
            ),
            case_run_id=1,
            template_contexts={},
            ocr_session=_RevalidationFailingSession(),
        )

    assert exc_info.value.code == OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED
    assert page.mouse.events == []
    assert page.keyboard.pressed == []
    assert page.keyboard.typed == []


def test_wait_and_navigate_invalidate_the_case_ocr_session() -> None:
    adapter = PlaywrightBrowserExecutionAdapter(
        headless=True,
        navigation_timeout_ms=1000,
    )
    page = _NoDomPage()
    session = _RecordingSession()

    adapter._execute_step(
        page,
        base_url="https://example.test",
        step=SimpleNamespace(
            step_no=1,
            step_type="wait",
            payload_json={"ms": 1},
            timeout_ms=1000,
            template_id=None,
        ),
        case_run_id=1,
        template_contexts={},
        ocr_session=session,
    )
    adapter._execute_step(
        page,
        base_url="https://example.test",
        step=SimpleNamespace(
            step_no=2,
            step_type="navigate",
            payload_json={
                "url": "https://example.test/next",
                "wait_until": "load",
            },
            timeout_ms=1000,
            template_id=None,
        ),
        case_run_id=1,
        template_contexts={},
        ocr_session=session,
    )

    assert session.events == ["invalidate:wait", "invalidate:navigate"]
    assert page.navigations == ["https://example.test/next"]


class _RejectingSession:
    def resolve_for_action(self, target: OcrTargetSpec) -> OcrTargetResolution:
        raise OcrTargetingError(
            OcrTargetResolution(
                status="rejected",
                target=target,
                error_code=OcrErrorCode.OCR_TARGET_NOT_FOUND,
                error_message="No OCR candidate matched.",
            )
        )


class _FakePage:
    url = "https://example.test"

    def goto(self, *_args: object, **_kwargs: object) -> None:
        return None

    def screenshot(self, **_kwargs: object) -> bytes:
        return b"case-screenshot"


class _FakeBrowser:
    def __init__(self) -> None:
        self.page = _FakePage()

    def new_context(self, **_kwargs: object) -> "_FakeBrowser":
        return self

    def new_page(self) -> _FakePage:
        return self.page

    def close(self) -> None:
        return None


class _FakePlaywrightContext:
    def __init__(self) -> None:
        self.chromium = self

    def __enter__(self) -> "_FakePlaywrightContext":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def launch(self, **_kwargs: object) -> _FakeBrowser:
        return _FakeBrowser()


class _FakePlaywrightTimeout(Exception):
    pass


def test_execute_case_creates_isolated_sessions_and_preserves_ocr_failure_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = PlaywrightBrowserExecutionAdapter(
        headless=True,
        navigation_timeout_ms=1000,
    )
    sessions: list[_RejectingSession] = []

    def build_session(_page: _FakePage) -> _RejectingSession:
        session = _RejectingSession()
        sessions.append(session)
        return session

    monkeypatch.setattr(
        adapter,
        "_load_playwright",
        lambda: (lambda: _FakePlaywrightContext(), _FakePlaywrightTimeout),
    )
    monkeypatch.setattr(adapter, "_build_ocr_session", build_session)
    step = SimpleNamespace(
        step_no=1,
        step_type="click",
        payload_json={
            "locator": "ocr",
            "ocr_target": {"text": "Missing"},
        },
        timeout_ms=1000,
        template_id=None,
        parent_step_no=None,
        branch_key=None,
        branch_name=None,
        branch_step_index=None,
    )

    first = adapter.execute_case(
        base_url="https://example.test",
        case_run_id=1,
        device_profile=None,
        steps=[step],
        template_contexts={},
    )
    second = adapter.execute_case(
        base_url="https://example.test",
        case_run_id=2,
        device_profile=None,
        steps=[step],
        template_contexts={},
    )

    assert len(sessions) == 2
    assert sessions[0] is not sessions[1]
    assert first.failure_reason_code == OcrErrorCode.OCR_TARGET_NOT_FOUND.value
    assert second.failure_reason_code == OcrErrorCode.OCR_TARGET_NOT_FOUND.value
    assert first.step_results[0].result_metadata_json["ocr"]["error_code"] == (
        OcrErrorCode.OCR_TARGET_NOT_FOUND.value
    )
    assert "BROWSER_EXECUTION_ERROR" not in {
        first.failure_reason_code,
        second.failure_reason_code,
    }


def test_evidence_failure_does_not_replace_primary_ocr_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenEvidenceSession(_RejectingSession):
        last_action_evidence = object()

    adapter = PlaywrightBrowserExecutionAdapter(
        headless=True,
        navigation_timeout_ms=1000,
    )
    monkeypatch.setattr(
        adapter,
        "_load_playwright",
        lambda: (lambda: _FakePlaywrightContext(), _FakePlaywrightTimeout),
    )
    monkeypatch.setattr(
        adapter,
        "_build_ocr_session",
        lambda _page: BrokenEvidenceSession(),
    )
    monkeypatch.setattr(
        "app.workers.browser.build_ocr_annotation_png",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("annotation failed")
        ),
    )
    step = SimpleNamespace(
        step_no=1,
        step_type="click",
        payload_json={
            "locator": "ocr",
            "ocr_target": {"text": "Missing"},
        },
        timeout_ms=1000,
        template_id=None,
        parent_step_no=None,
        branch_key=None,
        branch_name=None,
        branch_step_index=None,
    )

    result = adapter.execute_case(
        base_url="https://example.test",
        case_run_id=4,
        device_profile=None,
        steps=[step],
        template_contexts={},
    )

    assert result.failure_reason_code == OcrErrorCode.OCR_TARGET_NOT_FOUND.value
    assert result.step_results[0].error_message is not None
    assert "annotation failed" not in result.step_results[0].error_message
    assert result.step_results[0].result_metadata_json == {
        "ocr": {"error_code": OcrErrorCode.OCR_TARGET_NOT_FOUND.value}
    }


def test_execute_case_preserves_typed_ocr_assert_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ScanLimitedSession:
        def resolve(self, target: OcrTargetSpec) -> OcrTargetResolution:
            raise OcrTargetingError(
                OcrTargetResolution(
                    status="rejected",
                    target=target,
                    error_code=OcrErrorCode.OCR_PAGE_SCAN_LIMIT,
                    error_message="OCR page scan limit reached.",
                )
            )

    adapter = PlaywrightBrowserExecutionAdapter(
        headless=True,
        navigation_timeout_ms=1000,
    )
    monkeypatch.setattr(
        adapter,
        "_load_playwright",
        lambda: (lambda: _FakePlaywrightContext(), _FakePlaywrightTimeout),
    )
    monkeypatch.setattr(
        adapter,
        "_build_ocr_session",
        lambda _page: ScanLimitedSession(),
    )
    step = SimpleNamespace(
        step_no=1,
        step_type="ocr_assert",
        payload_json={
            "scope": "page",
            "assertion": "present",
            "ocr_target": {"text": "Missing", "scope": "page"},
        },
        timeout_ms=1000,
        template_id=None,
        parent_step_no=None,
        branch_key=None,
        branch_name=None,
        branch_step_index=None,
    )

    result = adapter.execute_case(
        base_url="https://example.test",
        case_run_id=3,
        device_profile=None,
        steps=[step],
        template_contexts={},
    )

    assert result.status == "error"
    assert result.failure_reason_code == OcrErrorCode.OCR_PAGE_SCAN_LIMIT.value
    assert result.step_results[0].result_metadata_json["ocr"]["error_code"] == (
        OcrErrorCode.OCR_PAGE_SCAN_LIMIT.value
    )
