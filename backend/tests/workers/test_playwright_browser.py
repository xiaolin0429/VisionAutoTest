from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.playwright

from tests.support.fakes import _make_browser_step, _write_browser_steps_fixture


def test_demo_acceptance_target_is_compatible_with_real_playwright_adapter():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover
        pytest.skip("Playwright is not installed in the current environment.")

    from app.main import DEMO_ACCEPTANCE_HTML

    temp_html = Path("/tmp/vat_demo_acceptance_target.html")
    temp_html.write_text(DEMO_ACCEPTANCE_HTML, encoding="utf-8")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(temp_html.as_uri(), wait_until="load", timeout=15000)
        page.locator("[data-testid='name-input']").fill("VisionAutoTest", timeout=15000)
        page.locator("[data-testid='submit-button']").click(timeout=15000)
        assert (
            page.locator("[data-testid='result-banner']").text_content()
            == "Hello, VisionAutoTest"
        )
        browser.close()


def test_playwright_browser_adapter_executes_navigate_scroll_and_long_press():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover
        pytest.skip("Playwright is not installed in the current environment.")

    from app.workers.browser import PlaywrightBrowserExecutionAdapter

    fixture_path = _write_browser_steps_fixture()
    adapter = PlaywrightBrowserExecutionAdapter(
        headless=True, navigation_timeout_ms=15000
    )
    base_url = f"{fixture_path.as_uri()}?view=home"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 960})
        page.goto(base_url, wait_until="load", timeout=15000)

        navigate_result = adapter._execute_step(
            page,
            base_url=base_url,
            step=_make_browser_step(
                step_no=1,
                step_type="navigate",
                payload_json={
                    "url": f"{fixture_path.as_posix()}?view=details",
                    "wait_until": "load",
                },
            ),
            case_run_id=1,
            template_contexts={},
        )
        assert navigate_result.status == "passed"
        assert (
            page.locator("[data-testid='navigate-status']").text_content()
            == "Details View"
        )

        element_scroll_result = adapter._execute_step(
            page,
            base_url=base_url,
            step=_make_browser_step(
                step_no=2,
                step_type="scroll",
                payload_json={
                    "target": "element",
                    "selector": "[data-testid='scroll-container']",
                    "direction": "down",
                    "distance": 240,
                },
            ),
            case_run_id=1,
            template_contexts={},
        )
        assert element_scroll_result.status == "passed"
        assert (
            page.locator("[data-testid='element-scroll-status']").text_content()
            == "Element Scrolled"
        )

        long_press_result = adapter._execute_step(
            page,
            base_url=base_url,
            step=_make_browser_step(
                step_no=3,
                step_type="long_press",
                payload_json={
                    "selector": "[data-testid='long-press-target']",
                    "duration_ms": 800,
                },
            ),
            case_run_id=1,
            template_contexts={},
        )
        assert long_press_result.status == "passed"
        assert (
            page.locator("[data-testid='press-status']").text_content()
            == "Long Press Activated"
        )

        page_scroll_result = adapter._execute_step(
            page,
            base_url=base_url,
            step=_make_browser_step(
                step_no=4,
                step_type="scroll",
                payload_json={
                    "target": "page",
                    "direction": "down",
                    "distance": 420,
                    "behavior": "smooth",
                },
            ),
            case_run_id=1,
            template_contexts={},
        )
        assert page_scroll_result.status == "passed"
        assert (
            page.locator("[data-testid='page-scroll-status']").text_content()
            == "Page Scrolled"
        )

        browser.close()


def test_playwright_browser_adapter_executes_click_and_input():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover
        pytest.skip("Playwright is not installed in the current environment.")

    from app.main import DEMO_ACCEPTANCE_HTML
    from app.workers.browser import PlaywrightBrowserExecutionAdapter

    temp_html = Path("/tmp/vat_demo_acceptance_target_browser_adapter.html")
    temp_html.write_text(DEMO_ACCEPTANCE_HTML, encoding="utf-8")
    adapter = PlaywrightBrowserExecutionAdapter(
        headless=True, navigation_timeout_ms=15000
    )
    base_url = temp_html.as_uri()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 960})
        page.goto(base_url, wait_until="load", timeout=15000)

        input_result = adapter._execute_step(
            page,
            base_url=base_url,
            step=_make_browser_step(
                step_no=1,
                step_type="input",
                payload_json={
                    "selector": "[data-testid='name-input']",
                    "text": "VisionAutoTest",
                    "input_mode": "fill",
                },
            ),
            case_run_id=1,
            template_contexts={},
        )
        assert input_result.status == "passed"
        assert (
            page.locator("[data-testid='name-input']").input_value() == "VisionAutoTest"
        )

        click_result = adapter._execute_step(
            page,
            base_url=base_url,
            step=_make_browser_step(
                step_no=2,
                step_type="click",
                payload_json={"selector": "[data-testid='submit-button']"},
            ),
            case_run_id=1,
            template_contexts={},
        )
        assert click_result.status == "passed"
        assert (
            page.locator("[data-testid='result-banner']").text_content()
            == "Hello, VisionAutoTest"
        )

        browser.close()


def test_playwright_browser_adapter_executes_conditional_branch():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover
        pytest.skip("Playwright is not installed in the current environment.")

    from app.workers.browser import PlaywrightBrowserExecutionAdapter

    fixture_path = _write_browser_steps_fixture()
    adapter = PlaywrightBrowserExecutionAdapter(
        headless=True, navigation_timeout_ms=15000
    )
    base_url = f"{fixture_path.as_uri()}?view=details"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 960})
        page.goto(base_url, wait_until="load", timeout=15000)

        result = adapter._execute_step(
            page,
            base_url=base_url,
            step=_make_browser_step(
                step_no=1,
                step_type="conditional_branch",
                payload_json={
                    "branches": [
                        {
                            "branch_key": "details-visible",
                            "branch_name": "Details Ready",
                            "condition": {
                                "type": "selector_exists",
                                "selector": "[data-testid='navigate-status']",
                            },
                            "steps": [
                                {
                                    "step_type": "wait",
                                    "step_name": "wait-branch",
                                    "payload_json": {"ms": 10},
                                }
                            ],
                        }
                    ]
                },
            ),
            case_run_id=1,
            template_contexts={},
        )
        assert result.status == "passed"
        assert result.error_message == "命中分支：Details Ready"

        browser.close()
