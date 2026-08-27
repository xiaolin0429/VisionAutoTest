from __future__ import annotations

import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import pytest

pytest.importorskip("cv2")
pytestmark = [pytest.mark.playwright, pytest.mark.ocr_fake]

from tests.support.fakes import _make_browser_step


_SELECT_OPTION_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <style>
      * { box-sizing: border-box; }
      body { margin: 0; font: 18px Arial, sans-serif; color: #111827; background: #fff; }
      button {
        position: absolute; width: 240px; height: 52px;
        border: 2px solid #1f2937; background: #fff; font: 18px Arial, sans-serif;
      }
      #country-field { left: 40px; top: 40px; }
      #wrong-field { left: 400px; top: 40px; }
      #country-menu {
        position: absolute; left: 40px; top: 108px; width: 240px; height: 52px;
      }
      #country-option { left: 0; top: 0; }
      #status { position: absolute; left: 40px; top: 190px; }
    </style>
  </head>
  <body>
    <button id="country-field" type="button">Choose country</button>
    <button id="wrong-field" type="button">Other field</button>
    <div id="country-menu" hidden>
      <button id="country-option" type="button">China</button>
    </div>
    <div id="status">Idle</div>
    <script>
      const field = document.querySelector('#country-field');
      const wrongField = document.querySelector('#wrong-field');
      const menu = document.querySelector('#country-menu');
      field.addEventListener('click', () => { menu.hidden = false; });
      document.querySelector('#country-option').addEventListener('click', () => {
        if (document.body.dataset.mode === 'success') {
          field.textContent = 'China';
        } else {
          wrongField.textContent = 'China';
        }
        document.querySelector('#status').textContent = 'Option clicked';
        menu.hidden = false;
      });
    </script>
  </body>
</html>
"""


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


class _SelectAnalyzer:
    def __init__(self, *, mode: Literal["success", "wrong-field"]) -> None:
        self.mode = mode
        self.calls = 0

    def analyze_ocr(
        self,
        *,
        image_png_bytes: bytes,
        language_profile: str | None = None,
    ) -> Mapping[str, object]:
        self.calls += 1
        width, height = struct.unpack(">II", image_png_bytes[16:24])
        if self.calls <= 2:
            blocks = [
                _block(
                    1,
                    "Choose country",
                    x=86,
                    y=56,
                    width=148,
                    height=20,
                ),
                _block(
                    2,
                    "Other field",
                    x=468,
                    y=56,
                    width=104,
                    height=20,
                ),
            ]
        elif self.calls <= 4:
            blocks = [
                _block(
                    1,
                    "Choose country",
                    x=86,
                    y=56,
                    width=148,
                    height=20,
                ),
                _block(2, "China", x=130, y=124, width=60, height=20),
            ]
        elif self.mode == "success":
            blocks = [
                _block(1, "China", x=130, y=56, width=60, height=20),
                _block(2, "China", x=130, y=124, width=60, height=20),
            ]
        else:
            blocks = [
                _block(
                    1,
                    "Choose country",
                    x=86,
                    y=56,
                    width=148,
                    height=20,
                ),
                _block(2, "China", x=130, y=124, width=60, height=20),
                _block(3, "China", x=490, y=56, width=60, height=20),
            ]
        return {
            "image_width": width,
            "image_height": height,
            "language_profiles": [language_profile or "en"],
            "preprocessing_variants": ["original"],
            "elapsed_ms": 1.0,
            "blocks": blocks,
        }


def _target(text: str) -> dict[str, object]:
    return {
        "text": text,
        "language": "en",
        "min_confidence": 0.5,
        "min_score": 0.5,
        "ambiguity_margin": 0.05,
    }


def _payload() -> dict[str, object]:
    return {
        "field_target": _target("Choose country"),
        "option_target": _target("China"),
        "verify_selected": True,
    }


def _assert_no_selector(value: object) -> None:
    if isinstance(value, Mapping):
        assert "selector" not in value
        for nested in value.values():
            _assert_no_selector(nested)
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        for nested in value:
            _assert_no_selector(nested)


def _launch_browser(playwright: Any) -> Any:
    from playwright.sync_api import Error as PlaywrightError

    try:
        return playwright.chromium.launch(headless=True)
    except PlaywrightError as exc:
        if "Executable doesn't exist" not in str(exc):
            raise
        chrome = Path(
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        )
        if chrome.is_file():
            return playwright.chromium.launch(
                headless=True,
                executable_path=str(chrome),
            )
        raise


def _execute_select(
    *,
    adapter: Any,
    page: Any,
    payload: dict[str, object],
) -> Any:
    session = adapter._build_ocr_session(page)
    return adapter._execute_step(
        page,
        base_url=page.url,
        step=_make_browser_step(
            step_no=1,
            step_type="select_option",
            payload_json=payload,
        ),
        case_run_id=1,
        template_contexts={},
        ocr_session=session,
    )


def test_real_playwright_select_verifies_field_while_menu_remains_open(
    tmp_path: Path,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover
        pytest.skip("Playwright is not installed in the current environment.")

    from app.workers.browser import PlaywrightBrowserExecutionAdapter

    fixture_path = tmp_path / "select-option-success.html"
    fixture_path.write_text(_SELECT_OPTION_HTML, encoding="utf-8")
    analyzer = _SelectAnalyzer(mode="success")
    adapter = PlaywrightBrowserExecutionAdapter(
        headless=True,
        navigation_timeout_ms=15000,
        ocr_analyzer=analyzer,
    )
    payload = _payload()
    _assert_no_selector(payload)

    with sync_playwright() as playwright:
        browser = _launch_browser(playwright)
        page = browser.new_page(viewport={"width": 800, "height": 500})
        page.goto(fixture_path.as_uri(), wait_until="load", timeout=15000)
        page.evaluate("() => { document.body.dataset.mode = 'success' }")

        outcome = _execute_select(
            adapter=adapter,
            page=page,
            payload=payload,
        )

        assert outcome.status == "passed"
        assert analyzer.calls == 5
        assert page.locator("#country-field").text_content() == "China"
        assert page.locator("#country-menu").is_visible()
        assert page.locator("#status").text_content() == "Option clicked"
        browser.close()


def test_real_playwright_select_rejects_menu_and_wrong_field_text(
    tmp_path: Path,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover
        pytest.skip("Playwright is not installed in the current environment.")

    from app.workers.browser import PlaywrightBrowserExecutionAdapter
    from app.workers.browser_ocr_actions import OcrActionVerificationError
    from app.workers.ocr_types import OcrErrorCode

    fixture_path = tmp_path / "select-option-wrong-field.html"
    fixture_path.write_text(_SELECT_OPTION_HTML, encoding="utf-8")
    analyzer = _SelectAnalyzer(mode="wrong-field")
    adapter = PlaywrightBrowserExecutionAdapter(
        headless=True,
        navigation_timeout_ms=15000,
        ocr_analyzer=analyzer,
    )
    payload = _payload()
    _assert_no_selector(payload)

    with sync_playwright() as playwright:
        browser = _launch_browser(playwright)
        page = browser.new_page(viewport={"width": 800, "height": 500})
        page.goto(fixture_path.as_uri(), wait_until="load", timeout=15000)
        page.evaluate("() => { document.body.dataset.mode = 'wrong-field' }")

        with pytest.raises(OcrActionVerificationError) as exc_info:
            _execute_select(
                adapter=adapter,
                page=page,
                payload=payload,
            )

        assert exc_info.value.code == OcrErrorCode.OCR_ACTION_VERIFICATION_FAILED
        assert analyzer.calls == 5
        assert page.locator("#country-field").text_content() == "Choose country"
        assert page.locator("#wrong-field").text_content() == "China"
        assert page.locator("#country-menu").is_visible()
        assert page.locator("#status").text_content() == "Option clicked"
        browser.close()
