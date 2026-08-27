from __future__ import annotations

import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("cv2")
pytestmark = [pytest.mark.playwright, pytest.mark.ocr_fake]

from tests.support.fakes import _make_browser_step


_PURE_OCR_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <style>
      * { box-sizing: border-box; }
      body { margin: 0; font: 18px Arial, sans-serif; background: #fff; color: #111827; }
      button, input { position: absolute; height: 52px; border: 2px solid #1f2937; background: #fff; }
      #click-target { left: 40px; top: 36px; width: 180px; }
      #placeholder-input { left: 40px; top: 126px; width: 300px; padding: 0 16px; font-size: 18px; }
      #field-label { position: absolute; left: 40px; top: 232px; line-height: 24px; }
      #label-input { left: 220px; top: 216px; width: 300px; padding: 0 16px; font-size: 18px; }
      #long-press-target { left: 40px; top: 302px; width: 200px; }
      #scroll-box {
        position: absolute; left: 40px; top: 398px; width: 320px; height: 140px;
        overflow: auto; border: 2px solid #1f2937;
      }
      #scroll-content { height: 520px; padding: 18px; background: #f8fafc; }
      #status { position: absolute; left: 420px; top: 40px; }
    </style>
  </head>
  <body>
    <button id="click-target" type="button">Run OCR Click</button>
    <input id="placeholder-input" placeholder="Type account" />
    <label id="field-label" for="label-input">Account label</label>
    <input id="label-input" value="existing-value" />
    <button id="long-press-target" type="button">Hold Here</button>
    <div id="scroll-box"><div id="scroll-content">Scroll Region</div></div>
    <div id="status">Idle</div>
    <script>
      const status = document.querySelector('#status');
      document.querySelector('#click-target').addEventListener('click', () => {
        status.textContent = 'Clicked';
      });
      const longPressTarget = document.querySelector('#long-press-target');
      let pressTimer = null;
      longPressTarget.addEventListener('mousedown', () => {
        pressTimer = window.setTimeout(() => { status.textContent = 'Long Pressed'; }, 100);
      });
      longPressTarget.addEventListener('mouseup', () => window.clearTimeout(pressTimer));
      document.querySelector('#scroll-box').addEventListener('scroll', (event) => {
        if (event.currentTarget.scrollTop > 0) status.textContent = 'Element Scrolled';
      });
    </script>
  </body>
</html>
"""


class _StubOcrAnalyzer:
    def __init__(self) -> None:
        self.calls = 0

    def analyze_ocr(
        self,
        *,
        image_png_bytes: bytes,
        language_profile: str | None = None,
    ) -> Mapping[str, object]:
        self.calls += 1
        width, height = struct.unpack(">II", image_png_bytes[16:24])
        blocks = [
            _block(1, "Run OCR Click", x=70, y=52, width=120, height=20),
            _block(2, "Type account", x=58, y=142, width=118, height=20),
            _block(3, "Account label", x=40, y=234, width=120, height=22),
            _block(4, "verified-value", x=238, y=232, width=120, height=20),
            _block(5, "Hold Here", x=94, y=318, width=96, height=20),
            _block(6, "Scroll Region", x=60, y=418, width=116, height=20),
        ]
        return {
            "image_width": width,
            "image_height": height,
            "language_profiles": [language_profile or "en"],
            "preprocessing_variants": ["original"],
            "elapsed_ms": 1.0,
            "blocks": blocks,
        }


def _block(
    order_no: int,
    text: str,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
) -> dict[str, object]:
    return {
        "order_no": order_no,
        "text": text,
        "confidence": 0.99,
        "pixel_rect": {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        },
        "language": "en",
        "preprocessing_variant": "original",
    }


def _target(
    text: str,
    *,
    action_point: str = "text_center",
) -> dict[str, object]:
    return {
        "text": text,
        "language": "en",
        "action_point": action_point,
        "min_confidence": 0.5,
        "min_score": 0.5,
        "ambiguity_margin": 0.05,
    }


def _launch_browser(playwright: Any) -> Any:
    from playwright.sync_api import Error as PlaywrightError

    try:
        return playwright.chromium.launch(headless=True)
    except PlaywrightError as exc:
        if "Executable doesn't exist" not in str(exc):
            raise
        for executable in (
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        ):
            if executable.is_file():
                return playwright.chromium.launch(
                    headless=True,
                    executable_path=str(executable),
                )
        raise


def test_real_playwright_pure_ocr_interactions_use_css_points_at_dpr2(
    tmp_path: Path,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover
        pytest.skip("Playwright is not installed in the current environment.")

    from app.workers.browser import PlaywrightBrowserExecutionAdapter

    html_path = tmp_path / "pure-ocr-interactions.html"
    html_path.write_text(_PURE_OCR_HTML, encoding="utf-8")
    analyzer = _StubOcrAnalyzer()
    adapter = PlaywrightBrowserExecutionAdapter(
        headless=True,
        navigation_timeout_ms=15000,
        ocr_analyzer=analyzer,
    )
    payloads = [
        {"locator": "ocr", "ocr_target": _target("Run OCR Click")},
        {
            "locator": "ocr",
            "ocr_target": _target("Type account"),
            "text": "placeholder-value",
            "input_mode": "fill",
        },
        {
            "locator": "ocr",
            "ocr_target": _target(
                "Account label",
                action_point="associated_control",
            ),
            "text": "verified-value",
            "input_mode": "fill",
            "verify_ocr": True,
            "input_is_sensitive": True,
        },
        {
            "locator": "ocr",
            "ocr_target": _target("Hold Here"),
            "duration_ms": 180,
        },
        {
            "target": "element",
            "locator": "ocr",
            "ocr_target": _target("Scroll Region"),
            "direction": "down",
            "distance": 180,
        },
    ]
    assert all("selector" not in payload for payload in payloads)

    with sync_playwright() as playwright:
        browser = _launch_browser(playwright)
        context = browser.new_context(
            viewport={"width": 800, "height": 600},
            device_scale_factor=2,
        )
        page = context.new_page()
        page.goto(html_path.as_uri(), wait_until="load", timeout=15000)
        session = adapter._build_ocr_session(page)

        click_outcome = adapter._execute_step(
            page,
            base_url=html_path.as_uri(),
            step=_make_browser_step(
                step_no=1,
                step_type="click",
                payload_json=payloads[0],
            ),
            case_run_id=1,
            template_contexts={},
            ocr_session=session,
        )
        assert click_outcome.status == "passed"
        assert click_outcome.actual_artifact is not None
        assert click_outcome.actual_artifact.artifact_type == "ocr_action"
        assert click_outcome.actual_artifact.content_bytes.startswith(b"\x89PNG")
        assert page.locator("#status").text_content() == "Clicked"

        placeholder_outcome = adapter._execute_step(
            page,
            base_url=html_path.as_uri(),
            step=_make_browser_step(
                step_no=2,
                step_type="input",
                payload_json=payloads[1],
            ),
            case_run_id=1,
            template_contexts={},
            ocr_session=session,
        )
        assert placeholder_outcome.status == "passed"
        assert page.locator("#placeholder-input").input_value() == "placeholder-value"

        label_outcome = adapter._execute_step(
            page,
            base_url=html_path.as_uri(),
            step=_make_browser_step(
                step_no=3,
                step_type="input",
                payload_json=payloads[2],
            ),
            case_run_id=1,
            template_contexts={},
            ocr_session=session,
        )
        assert label_outcome.status == "passed"
        assert page.locator("#label-input").input_value() == "verified-value"
        assert "verified-value" not in repr(label_outcome.result_metadata_json)
        assert label_outcome.actual_artifact is not None
        assert "verified-value" not in label_outcome.actual_artifact.file_name
        assert label_outcome.actual_artifact.artifact_type == "ocr_action"
        long_press_outcome = adapter._execute_step(
            page,
            base_url=html_path.as_uri(),
            step=_make_browser_step(
                step_no=4,
                step_type="long_press",
                payload_json=payloads[3],
            ),
            case_run_id=1,
            template_contexts={},
            ocr_session=session,
        )
        assert long_press_outcome.status == "passed"
        assert page.locator("#status").text_content() == "Long Pressed"

        scroll_outcome = adapter._execute_step(
            page,
            base_url=html_path.as_uri(),
            step=_make_browser_step(
                step_no=5,
                step_type="scroll",
                payload_json=payloads[4],
            ),
            case_run_id=1,
            template_contexts={},
            ocr_session=session,
        )
        assert scroll_outcome.status == "passed"
        page.wait_for_timeout(50)
        assert page.locator("#scroll-box").evaluate("element => element.scrollTop") > 0
        assert page.locator("#status").text_content() == "Element Scrolled"
        assert session.cache_stats.generation >= 5
        assert session.cache_stats.last_invalidation_reason == "scroll"

        assert_outcome = adapter._execute_step(
            page,
            base_url=html_path.as_uri(),
            step=_make_browser_step(
                step_no=6,
                step_type="ocr_assert",
                payload_json={
                    "scope": "viewport",
                    "assertion": "present",
                    "ocr_target": _target("Run OCR Click"),
                },
            ),
            case_run_id=1,
            template_contexts={},
            ocr_session=session,
        )
        assert assert_outcome.status == "passed"
        assert assert_outcome.actual_artifact is not None
        assert assert_outcome.actual_artifact.artifact_type == "ocr_assert"
        assert assert_outcome.actual_artifact.content_bytes.startswith(b"\x89PNG")
        assert assert_outcome.result_metadata_json["ocr"]["assertion"] == "present"

        session.recognize_viewport(language_profile="en")
        page.set_viewport_size({"width": 820, "height": 620})
        session.recognize_viewport(language_profile="en")
        assert session.cache_stats.last_invalidation_reason == "viewport_changed"

        context.close()
        browser.close()

    assert analyzer.calls >= 5


class _MovingTargetAnalyzer:
    def __init__(self) -> None:
        self.calls = 0
        self.page: Any | None = None

    def analyze_ocr(
        self,
        *,
        image_png_bytes: bytes,
        language_profile: str | None = None,
    ) -> Mapping[str, object]:
        self.calls += 1
        width, height = struct.unpack(">II", image_png_bytes[16:24])
        block_x = 70 if self.calls == 1 else 350
        analysis = {
            "image_width": width,
            "image_height": height,
            "language_profiles": [language_profile or "en"],
            "preprocessing_variants": ["original"],
            "elapsed_ms": 1.0,
            "blocks": [
                _block(
                    1,
                    "Run OCR Click",
                    x=block_x,
                    y=52,
                    width=120,
                    height=20,
                )
            ],
        }
        if self.calls == 1:
            assert self.page is not None
            self.page.evaluate(
                "() => { document.querySelector('#click-target').style.left = '320px' }"
            )
        return analysis


def test_real_playwright_rejects_viewport_target_moved_between_ocr_captures(
    tmp_path: Path,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover
        pytest.skip("Playwright is not installed in the current environment.")

    from app.workers.browser import PlaywrightBrowserExecutionAdapter
    from app.workers.ocr_targeting import OcrTargetingError
    from app.workers.ocr_types import OcrErrorCode

    html_path = tmp_path / "moving-pure-ocr-target.html"
    html_path.write_text(_PURE_OCR_HTML, encoding="utf-8")
    analyzer = _MovingTargetAnalyzer()
    adapter = PlaywrightBrowserExecutionAdapter(
        headless=True,
        navigation_timeout_ms=15000,
        ocr_analyzer=analyzer,
    )
    payload: dict[str, object] = {
        "locator": "ocr",
        "ocr_target": _target("Run OCR Click"),
    }
    assert "selector" not in payload

    with sync_playwright() as playwright:
        browser = _launch_browser(playwright)
        context = browser.new_context(viewport={"width": 800, "height": 600})
        page = context.new_page()
        page.goto(html_path.as_uri(), wait_until="load", timeout=15000)
        analyzer.page = page
        session = adapter._build_ocr_session(page)

        with pytest.raises(OcrTargetingError) as exc_info:
            adapter._execute_step(
                page,
                base_url=html_path.as_uri(),
                step=_make_browser_step(
                    step_no=1,
                    step_type="click",
                    payload_json=payload,
                ),
                case_run_id=1,
                template_contexts={},
                ocr_session=session,
            )

        assert exc_info.value.code == OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED
        assert analyzer.calls == 2
        assert page.locator("#status").text_content() == "Idle"
        context.close()
        browser.close()
