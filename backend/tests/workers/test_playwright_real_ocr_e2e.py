from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from tests.support.fakes import _make_browser_step

pytestmark = [
    pytest.mark.playwright,
    pytest.mark.vision,
    pytest.mark.ocr_benchmark,
    pytest.mark.ocr_real_model,
    pytest.mark.skipif(
        os.environ.get("VAT_RUN_REAL_OCR_BENCHMARK") != "1",
        reason="Set VAT_RUN_REAL_OCR_BENCHMARK=1 for real PaddleOCR E2E.",
    ),
]

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MODEL_ROOT = BACKEND_ROOT / ".data" / "ocr-models"
E2E_PAGE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "ocr_benchmark"
    / "v1"
    / "e2e_page.html"
)
CHROME_EXECUTABLE = Path(
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)


def _target(text: str) -> dict[str, object]:
    return {
        "text": text,
        "language": "en",
        "min_confidence": 0.40,
        "min_score": 0.50,
        "ambiguity_margin": 0.05,
    }


def _assert_no_selector(value: object) -> None:
    if isinstance(value, Mapping):
        assert "selector" not in value
        for nested in value.values():
            _assert_no_selector(nested)
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for nested in value:
            _assert_no_selector(nested)


def _build_real_adapter() -> Any:
    from app.workers.browser import PlaywrightBrowserExecutionAdapter
    from app.workers.ocr_engine import OcrEnginePool, OcrRecognitionPipeline
    from app.workers.vision import DefaultVisionAssertionAdapter

    pipeline = OcrRecognitionPipeline(
        engine_pool=OcrEnginePool(
            allowed_language_profiles=("en",),
            model_root=MODEL_ROOT,
            allow_model_download=False,
            cache_size=1,
        ),
        preprocessing_profile="balanced",
        max_preprocess_variants=5,
        minimum_confidence=0.40,
    )
    analyzer = DefaultVisionAssertionAdapter(ocr_pipeline=pipeline)
    analyzer.prewarm_ocr(("en",), strict=True)
    return PlaywrightBrowserExecutionAdapter(
        headless=True,
        navigation_timeout_ms=15000,
        ocr_analyzer=analyzer,
    )


def _launch_browser(playwright: Any) -> Any:
    launch_options: dict[str, object] = {"headless": True}
    if CHROME_EXECUTABLE.is_file():
        launch_options["executable_path"] = str(CHROME_EXECUTABLE)
    return playwright.chromium.launch(**launch_options)


@pytest.mark.parametrize(
    ("viewport", "device_scale_factor"),
    [
        ((900, 900), 1),
        ((900, 900), 2),
        ((390, 844), 1),
        ((390, 844), 2),
    ],
    ids=("desktop-dpr1", "desktop-dpr2", "mobile-dpr1", "mobile-dpr2"),
)
def test_real_paddleocr_executes_all_pure_ocr_web_steps_without_selectors(
    viewport: tuple[int, int],
    device_scale_factor: int,
) -> None:
    from playwright.sync_api import sync_playwright

    adapter = _build_real_adapter()
    payloads: list[tuple[str, dict[str, object]]] = [
        (
            "click",
            {
                "locator": "ocr",
                "ocr_target": _target("Run Action"),
            },
        ),
        (
            "input",
            {
                "locator": "ocr",
                "ocr_target": _target("Type account"),
                "text": "Account 42",
                "input_mode": "fill",
                "verify_ocr": True,
            },
        ),
        (
            "select_option",
            {
                "field_target": _target("Choose country"),
                "option_target": _target("Japan"),
                "verify_selected": True,
            },
        ),
        (
            "long_press",
            {
                "locator": "ocr",
                "ocr_target": _target("Hold Action"),
                "duration_ms": 180,
            },
        ),
        (
            "scroll",
            {
                "target": "element",
                "locator": "ocr",
                "ocr_target": _target("Scroll Region"),
                "direction": "down",
                "distance": 160,
            },
        ),
        (
            "conditional_branch",
            {
                "branches": [
                    {
                        "branch_key": "ocr-ready",
                        "branch_name": "OCR Ready",
                        "condition": {
                            "type": "ocr_text_visible",
                            "ocr_target": _target("Branch Ready"),
                        },
                        "steps": [
                            {
                                "step_type": "wait",
                                "step_name": "branch wait",
                                "payload_json": {"ms": 1},
                            }
                        ],
                    }
                ]
            },
        ),
        (
            "ocr_assert",
            {
                "scope": "viewport",
                "assertion": "present",
                "ocr_target": _target("Branch Ready"),
            },
        ),
    ]
    for _, payload in payloads:
        _assert_no_selector(payload)

    with sync_playwright() as playwright:
        browser = _launch_browser(playwright)
        context = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            device_scale_factor=device_scale_factor,
            locale="en-US",
            timezone_id="UTC",
        )
        try:
            page = context.new_page()
            page.goto(E2E_PAGE.as_uri(), wait_until="load", timeout=15000)
            page.evaluate("() => document.fonts.ready")
            session = adapter._build_ocr_session(page)

            outcomes: dict[str, Any] = {}
            for step_no, (step_type, payload) in enumerate(payloads, start=1):
                outcomes[step_type] = adapter._execute_step(
                    page,
                    base_url=E2E_PAGE.as_uri(),
                    step=_make_browser_step(
                        step_no=step_no,
                        step_type=step_type,
                        payload_json=payload,
                    ),
                    case_run_id=1,
                    template_contexts={},
                    ocr_session=session,
                )
                assert outcomes[step_type].status == "passed"

            assert page.locator("#account-input").input_value() == "Account 42"
            assert page.locator("#country-field").text_content() == "Japan"
            assert page.locator("#scroll-box").evaluate(
                "element => element.scrollTop"
            ) > 0
            assert page.locator("#status").text_content() == "Element Scrolled"
            assert outcomes["conditional_branch"].error_message == (
                "命中分支：OCR Ready"
            )
            assert outcomes["ocr_assert"].result_metadata_json["ocr"][
                "assertion"
            ] == "present"
            assert session.cache_stats.analysis_misses >= 1
        finally:
            context.close()
            browser.close()
