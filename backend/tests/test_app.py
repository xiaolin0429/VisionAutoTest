from __future__ import annotations

import base64
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

TEST_ADMIN_USERNAME = "admin"
TEST_ADMIN_PASSWORD = "test-admin-password"
TINY_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9s2GoswAAAAASUVORK5CYII="
)
ACTUAL_ARTIFACT_BYTES = TINY_PNG_BYTES + b"-actual"
DIFF_ARTIFACT_BYTES = TINY_PNG_BYTES + b"-diff"
OCR_ARTIFACT_BYTES = TINY_PNG_BYTES + b"-ocr"
BROWSER_STEPS_HTML = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Browser Steps Fixture</title>
    <style>
      body {
        margin: 0;
        font-family: Arial, sans-serif;
      }
      main {
        width: min(720px, calc(100vw - 32px));
        margin: 0 auto;
        padding: 32px 0 96px;
      }
      #scroll-container {
        height: 180px;
        overflow: auto;
        border: 1px solid #ccd6e0;
        border-radius: 16px;
        padding: 12px;
      }
      #scroll-content {
        width: 820px;
        height: 520px;
        position: relative;
        background: linear-gradient(135deg, rgba(79, 172, 254, 0.18), rgba(20, 33, 61, 0.05));
      }
      #element-scroll-target {
        position: absolute;
        right: 24px;
        bottom: 24px;
        padding: 10px 14px;
        background: #14213d;
        color: #fff;
      }
      #page-spacer {
        height: 900px;
      }
      #long-press-target {
        margin-top: 20px;
        padding: 18px 24px;
        border: 1px dashed #8193a5;
        background: #fff;
      }
    </style>
  </head>
  <body>
    <main>
      <h1 data-testid="fixture-title">Browser Steps Fixture</h1>
      <div data-testid="navigate-status">Default View</div>
      <div data-testid="page-scroll-status">Page Not Scrolled</div>
      <div data-testid="element-scroll-status">Element Not Scrolled</div>
      <div id="scroll-container" data-testid="scroll-container">
        <div id="scroll-content">
          <div id="element-scroll-target" data-testid="element-scroll-target">Element Scroll Target</div>
        </div>
      </div>
      <button id="long-press-target" data-testid="long-press-target" type="button">Press And Hold</button>
      <div data-testid="press-status">Long Press Idle</div>
      <div id="page-spacer"></div>
    </main>
    <script>
      const params = new URLSearchParams(window.location.search);
      const view = params.get("view");
      const navigateStatus = document.querySelector("[data-testid='navigate-status']");
      const pageScrollStatus = document.querySelector("[data-testid='page-scroll-status']");
      const elementScrollStatus = document.querySelector("[data-testid='element-scroll-status']");
      const scrollContainer = document.querySelector("[data-testid='scroll-container']");
      const longPressTarget = document.querySelector("[data-testid='long-press-target']");
      const pressStatus = document.querySelector("[data-testid='press-status']");

      if (view === "details") {
        navigateStatus.textContent = "Details View";
      }

      const syncPageScrollStatus = () => {
        pageScrollStatus.textContent = window.scrollY > 80 ? "Page Scrolled" : "Page Not Scrolled";
      };
      window.addEventListener("scroll", syncPageScrollStatus, { passive: true });
      syncPageScrollStatus();

      scrollContainer.addEventListener("scroll", () => {
        const moved = scrollContainer.scrollTop > 0 || scrollContainer.scrollLeft > 0;
        elementScrollStatus.textContent = moved ? "Element Scrolled" : "Element Not Scrolled";
      });

      let longPressTimer = null;
      let longPressActive = false;
      const clearTimer = () => {
        if (longPressTimer !== null) {
          window.clearTimeout(longPressTimer);
          longPressTimer = null;
        }
      };
      const startPress = () => {
        clearTimer();
        longPressActive = true;
        pressStatus.textContent = "Long Press Pending";
        longPressTimer = window.setTimeout(() => {
          if (longPressActive) {
            pressStatus.textContent = "Long Press Activated";
          }
        }, 650);
      };
      const stopPress = () => {
        longPressActive = false;
        clearTimer();
        if (pressStatus.textContent !== "Long Press Activated") {
          pressStatus.textContent = "Long Press Idle";
        }
      };

      longPressTarget.addEventListener("mousedown", startPress);
      longPressTarget.addEventListener("mouseup", stopPress);
      longPressTarget.addEventListener("mouseleave", stopPress);
    </script>
  </body>
</html>
"""


def _require_test_database_url() -> str:
    database_url = os.environ.get("VAT_TEST_DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "VAT_TEST_DATABASE_URL is required. Please prepare an external PostgreSQL test database before running backend tests."
        )
    return database_url


def _reset_local_data() -> None:
    if "app.db.session" in sys.modules:
        from app.db.session import engine

        engine.dispose()
    stale_modules = [module_name for module_name in sys.modules if module_name == "app" or module_name.startswith("app.")]
    for module_name in stale_modules:
        sys.modules.pop(module_name, None)
    backend_root = Path(__file__).resolve().parents[1]
    testdata_root = backend_root / ".testdata"
    testdata_root.mkdir(exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="case_", dir=testdata_root))
    os.environ["VAT_DATABASE_URL"] = _require_test_database_url()
    os.environ["VAT_APP_ENV"] = "test"
    os.environ["VAT_DATABASE_AUTO_CREATE"] = "false"
    os.environ["VAT_DATABASE_AUTO_MIGRATE"] = "true"
    os.environ.pop("VAT_DATABASE_ADMIN_URL", None)
    os.environ["VAT_LOCAL_STORAGE_PATH"] = str(temp_dir / "media")
    os.environ["VAT_DEFAULT_ADMIN_USERNAME"] = TEST_ADMIN_USERNAME
    os.environ["VAT_DEFAULT_ADMIN_PASSWORD"] = TEST_ADMIN_PASSWORD
    os.environ["VAT_JWT_SECRET_KEY"] = "test-jwt-secret-key-visionautotest-2026"
    os.environ["VAT_JWT_ALGORITHM"] = "HS256"
    os.environ["VAT_JWT_ISSUER"] = "visionautotest-backend-test"
    os.environ["VAT_DATA_ENCRYPTION_KEY"] = "test-data-encryption-key-visionautotest-2026"

    from app.db.migrations import reset_database_schema, upgrade_database

    reset_database_schema(database_url=os.environ["VAT_DATABASE_URL"])
    upgrade_database(database_url=os.environ["VAT_DATABASE_URL"])


def _install_fake_browser_adapter(monkeypatch) -> None:
    from app.workers.browser import BrowserArtifact, BrowserStepResult, CaseExecutionResult

    class FakeBrowserAdapter:
        supported_step_types = {"wait", "click", "input", "navigate", "scroll", "long_press"}

        def execute_case(self, *, base_url: str, case_run_id: int, device_profile, steps, template_contexts):
            _ = (base_url, case_run_id, device_profile, template_contexts)
            step_results: list[BrowserStepResult] = []
            for step in steps:
                started_at = datetime.now(timezone.utc)
                finished_at = datetime.now(timezone.utc)
                if step.step_type not in self.supported_step_types:
                    step_results.append(
                        BrowserStepResult(
                            step_no=step.step_no,
                            step_type=step.step_type,
                            status="error",
                            started_at=started_at,
                            finished_at=finished_at,
                            duration_ms=1,
                            error_message=f"Unsupported step type: {step.step_type}",
                        )
                    )
                    return CaseExecutionResult(
                        status="error",
                        step_results=step_results,
                        failure_reason_code="STEP_NOT_SUPPORTED",
                        failure_summary=f"Unsupported step type: {step.step_type}",
                        artifact=BrowserArtifact(
                            file_name=f"case-run-{case_run_id}.png",
                            content_type="image/png",
                            content_bytes=TINY_PNG_BYTES,
                        ),
                    )

                step_results.append(
                    BrowserStepResult(
                        step_no=step.step_no,
                        step_type=step.step_type,
                        status="passed",
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_ms=1,
                        score_value=1.0,
                    )
                )

            return CaseExecutionResult(
                status="passed",
                step_results=step_results,
                artifact=BrowserArtifact(
                    file_name=f"case-run-{case_run_id}.png",
                    content_type="image/png",
                    content_bytes=TINY_PNG_BYTES,
                ),
            )

    monkeypatch.setattr("app.workers.execution.build_browser_execution_adapter", lambda: FakeBrowserAdapter())


def _write_browser_steps_fixture() -> Path:
    fixture_dir = Path(tempfile.mkdtemp(prefix="browser_steps_"))
    fixture_path = fixture_dir / "fixture.html"
    fixture_path.write_text(BROWSER_STEPS_HTML, encoding="utf-8")
    return fixture_path


def _make_browser_step(
    *,
    step_no: int,
    step_type: str,
    payload_json: dict,
    timeout_ms: int = 15000,
    template_id: int | None = None,
):
    return SimpleNamespace(
        step_no=step_no,
        step_type=step_type,
        payload_json=payload_json,
        timeout_ms=timeout_ms,
        template_id=template_id,
    )


def _install_visual_browser_adapter(monkeypatch, *, template_status: str = "passed", ocr_status: str = "passed") -> None:
    from app.workers.browser import BrowserArtifact, BrowserStepResult, CaseExecutionResult
    from app.workers.vision import VisionArtifact

    class FakeVisualBrowserAdapter:
        def execute_case(self, *, base_url: str, case_run_id: int, device_profile, steps, template_contexts):
            _ = (base_url, case_run_id, device_profile)
            step_results: list[BrowserStepResult] = []
            failure_reason_code: str | None = None
            failure_summary: str | None = None
            case_status = "passed"

            for step in steps:
                started_at = datetime.now(timezone.utc)
                finished_at = datetime.now(timezone.utc)
                status = "passed"
                error_message = None
                score_value = 1.0
                expected_media_object_id = None
                actual_artifact = None
                diff_artifact = None

                if step.step_type == "template_assert":
                    template_context = template_contexts[step.template_id]
                    expected_media_object_id = template_context.baseline_media_object_id
                    actual_artifact = VisionArtifact(
                        file_name=f"case-run-{case_run_id}-step-{step.step_no}-actual.png",
                        content_type="image/png",
                        content_bytes=ACTUAL_ARTIFACT_BYTES,
                        artifact_type="actual_screenshot",
                    )
                    status = template_status
                    score_value = 0.98 if status == "passed" else 0.21
                    if status == "failed":
                        error_message = "Template assertion failed."
                        diff_artifact = VisionArtifact(
                            file_name=f"case-run-{case_run_id}-step-{step.step_no}-diff.png",
                            content_type="image/png",
                            content_bytes=DIFF_ARTIFACT_BYTES,
                            artifact_type="diff_screenshot",
                        )
                        failure_reason_code = "TEMPLATE_ASSERTION_FAILED"
                        failure_summary = error_message
                        case_status = "failed"
                    elif status == "error":
                        error_message = "Template engine error."
                        failure_reason_code = "STEP_EXECUTION_ERROR"
                        failure_summary = error_message
                        case_status = "error"
                elif step.step_type == "ocr_assert":
                    actual_artifact = VisionArtifact(
                        file_name=f"case-run-{case_run_id}-step-{step.step_no}-ocr.png",
                        content_type="image/png",
                        content_bytes=OCR_ARTIFACT_BYTES,
                        artifact_type="ocr_screenshot",
                    )
                    status = ocr_status
                    score_value = 1.0 if status == "passed" else 0.0
                    if status == "failed":
                        error_message = "OCR assertion failed."
                        failure_reason_code = "OCR_ASSERTION_FAILED"
                        failure_summary = error_message
                        case_status = "failed"
                    elif status == "error":
                        error_message = "OCR engine error."
                        failure_reason_code = "STEP_EXECUTION_ERROR"
                        failure_summary = error_message
                        case_status = "error"

                step_results.append(
                    BrowserStepResult(
                        step_no=step.step_no,
                        step_type=step.step_type,
                        status=status,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_ms=1,
                        error_message=error_message,
                        score_value=score_value,
                        expected_media_object_id=expected_media_object_id,
                        actual_artifact=actual_artifact,
                        diff_artifact=diff_artifact,
                    )
                )

                if status in {"failed", "error"}:
                    break

            return CaseExecutionResult(
                status=case_status,
                step_results=step_results,
                failure_reason_code=failure_reason_code,
                failure_summary=failure_summary,
                artifact=BrowserArtifact(
                    file_name=f"case-run-{case_run_id}.png",
                    content_type="image/png",
                    content_bytes=TINY_PNG_BYTES,
                ),
            )

    monkeypatch.setattr("app.workers.execution.build_browser_execution_adapter", lambda: FakeVisualBrowserAdapter())


def _install_noop_dispatcher(monkeypatch) -> None:
    class NoopDispatcher:
        def dispatch_test_run(self, test_run_id: int) -> None:
            _ = test_run_id

    monkeypatch.setattr("app.api.v1.executions.get_test_run_dispatcher", lambda _background_tasks: NoopDispatcher())


def _install_template_workbench_adapter(monkeypatch, *, analyses: list[dict] | None = None, ocr_error: str | None = None) -> None:
    queue = list(analyses or [])

    class FakeVisionAdapter:
        def assert_template(self, **_kwargs):
            raise NotImplementedError

        def assert_ocr(self, **_kwargs):
            raise NotImplementedError

        def analyze_ocr(self, *, image_png_bytes: bytes) -> dict:
            _ = image_png_bytes
            if ocr_error is not None:
                raise RuntimeError(ocr_error)
            if queue:
                return queue.pop(0)
            return {
                "engine_name": "paddleocr",
                "image_width": 200,
                "image_height": 100,
                "blocks": [
                    {
                        "order_no": 1,
                        "text": "VisionAutoTest",
                        "confidence": 0.98,
                        "polygon_points": [{"x": 20, "y": 10}, {"x": 90, "y": 10}, {"x": 90, "y": 32}, {"x": 20, "y": 32}],
                        "pixel_rect": {"x": 20, "y": 10, "width": 70, "height": 22},
                        "ratio_rect": {"x_ratio": 0.1, "y_ratio": 0.1, "width_ratio": 0.35, "height_ratio": 0.22},
                    }
                ],
            }

        def build_mask_preview(self, *, image_png_bytes: bytes, mask_regions) -> dict:
            _ = (image_png_bytes, mask_regions)
            return {
                "image_width": 200,
                "image_height": 100,
                "overlay_png_bytes": TINY_PNG_BYTES + b"-overlay",
                "processed_png_bytes": TINY_PNG_BYTES + b"-processed",
            }

    monkeypatch.setattr("app.services.assets.build_vision_assertion_adapter", lambda: FakeVisionAdapter())


def _create_media_object(client: TestClient, *, headers: dict[str, str], usage: str = "baseline") -> int:
    response = client.post(
        "/api/v1/media-objects",
        headers=headers,
        data={"usage": usage},
        files={"file": ("baseline.png", TINY_PNG_BYTES, "image/png")},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def _create_template(
    client: TestClient,
    *,
    headers: dict[str, str],
    media_object_id: int,
    template_code: str,
    template_name: str,
    match_strategy: str = "template",
    status: str = "published",
) -> int:
    response = client.post(
        "/api/v1/templates",
        headers=headers,
        json={
            "template_code": template_code,
            "template_name": template_name,
            "template_type": "page",
            "match_strategy": match_strategy,
            "threshold_value": 0.95,
            "status": status,
            "original_media_object_id": media_object_id,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def _get_template_current_baseline_revision_id(client: TestClient, *, headers: dict[str, str], template_id: int) -> int:
    response = client.get(f"/api/v1/templates/{template_id}", headers=headers)
    assert response.status_code == 200
    baseline_revision_id = response.json()["data"]["current_baseline_revision_id"]
    assert baseline_revision_id is not None
    return baseline_revision_id


def test_healthz():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "ok"


def test_demo_acceptance_target_page_is_served():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/demo/acceptance-target")
        assert response.status_code == 200
        assert "VisionAutoTest Demo Target" in response.text
        assert "data-testid=\"cta-open-form\"" in response.text
        assert "data-testid=\"submit-button\"" in response.text
        assert "data-testid=\"name-input\"" in response.text
        assert "data-testid=\"demo-form\" hidden" not in response.text
        assert "data-testid=\"scroll-container\"" in response.text
        assert "data-testid=\"long-press-target\"" in response.text


def test_session_login_returns_jwt_token_shape():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        response = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert response.status_code == 201
        payload = response.json()["data"]
        assert payload["token_type"] == "Bearer"
        assert payload["access_token"].count(".") == 2
        assert payload["session_id"].startswith("ses_")


def test_refresh_token_expired_returns_specific_error_and_marks_status():
    _reset_local_data()
    from datetime import timedelta

    from app.db.session import SessionLocal
    from app.main import app
    from app.models import RefreshToken

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert login_resp.status_code == 201
        refresh_token = login_resp.json()["data"]["refresh_token"]

        with SessionLocal() as db:
            token = db.query(RefreshToken).filter(RefreshToken.status == "active").one()
            token.expires_at = token.expires_at - timedelta(days=8)
            db.commit()

        refresh_resp = client.post("/api/v1/session-refreshes", json={"refresh_token": refresh_token})
        assert refresh_resp.status_code == 401
        assert refresh_resp.json()["error"]["code"] == "REFRESH_TOKEN_EXPIRED"

        with SessionLocal() as db:
            token = db.query(RefreshToken).filter(RefreshToken.token_hash.is_not(None)).one()
            assert token.status == "expired"


def test_revoked_session_refresh_token_returns_revoked_error():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert login_resp.status_code == 201
        payload = login_resp.json()["data"]
        token = payload["access_token"]
        refresh_token = payload["refresh_token"]
        headers = {"Authorization": f"Bearer {token}"}

        revoke_resp = client.delete("/api/v1/sessions/current", headers=headers)
        assert revoke_resp.status_code == 204

        refresh_resp = client.post("/api/v1/session-refreshes", json={"refresh_token": refresh_token})
        assert refresh_resp.status_code == 401
        assert refresh_resp.json()["error"]["code"] == "REFRESH_TOKEN_REVOKED"

        current_user_resp = client.get("/api/v1/users/current", headers=headers)
        assert current_user_resp.status_code == 401
        assert current_user_resp.json()["error"]["code"] == "TOKEN_REVOKED"


def test_used_refresh_token_returns_invalid_error():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert login_resp.status_code == 201
        refresh_token = login_resp.json()["data"]["refresh_token"]

        first_refresh_resp = client.post("/api/v1/session-refreshes", json={"refresh_token": refresh_token})
        assert first_refresh_resp.status_code == 201

        second_refresh_resp = client.post("/api/v1/session-refreshes", json={"refresh_token": refresh_token})
        assert second_refresh_resp.status_code == 401
        assert second_refresh_resp.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"


def test_logout_makes_stale_refresh_token_return_revoked_error():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert login_resp.status_code == 201
        initial_payload = login_resp.json()["data"]
        old_refresh_token = initial_payload["refresh_token"]

        refresh_resp = client.post("/api/v1/session-refreshes", json={"refresh_token": old_refresh_token})
        assert refresh_resp.status_code == 201
        latest_payload = refresh_resp.json()["data"]
        latest_access_token = latest_payload["access_token"]

        revoke_resp = client.delete(
            "/api/v1/sessions/current",
            headers={"Authorization": f"Bearer {latest_access_token}"},
        )
        assert revoke_resp.status_code == 204

        stale_refresh_resp = client.post("/api/v1/session-refreshes", json={"refresh_token": old_refresh_token})
        assert stale_refresh_resp.status_code == 401
        assert stale_refresh_resp.json()["error"]["code"] == "REFRESH_TOKEN_REVOKED"


def test_demo_acceptance_target_is_compatible_with_real_playwright_adapter():
    _reset_local_data()
    from pathlib import Path

    import pytest

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
        assert page.locator("[data-testid='result-banner']").text_content() == "Hello, VisionAutoTest"
        browser.close()


def test_playwright_browser_adapter_executes_navigate_scroll_and_long_press():
    import pytest

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover
        pytest.skip("Playwright is not installed in the current environment.")

    from app.workers.browser import PlaywrightBrowserExecutionAdapter

    fixture_path = _write_browser_steps_fixture()
    adapter = PlaywrightBrowserExecutionAdapter(headless=True, navigation_timeout_ms=15000)
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
                payload_json={"url": f"{fixture_path.as_posix()}?view=details", "wait_until": "load"},
            ),
            case_run_id=1,
            template_contexts={},
        )
        assert navigate_result.status == "passed"
        assert page.locator("[data-testid='navigate-status']").text_content() == "Details View"

        element_scroll_result = adapter._execute_step(
            page,
            base_url=base_url,
            step=_make_browser_step(
                step_no=2,
                step_type="scroll",
                payload_json={"target": "element", "selector": "[data-testid='scroll-container']", "direction": "down", "distance": 240},
            ),
            case_run_id=1,
            template_contexts={},
        )
        assert element_scroll_result.status == "passed"
        assert page.locator("[data-testid='element-scroll-status']").text_content() == "Element Scrolled"

        long_press_result = adapter._execute_step(
            page,
            base_url=base_url,
            step=_make_browser_step(
                step_no=3,
                step_type="long_press",
                payload_json={"selector": "[data-testid='long-press-target']", "duration_ms": 800},
            ),
            case_run_id=1,
            template_contexts={},
        )
        assert long_press_result.status == "passed"
        assert page.locator("[data-testid='press-status']").text_content() == "Long Press Activated"

        page_scroll_result = adapter._execute_step(
            page,
            base_url=base_url,
            step=_make_browser_step(
                step_no=4,
                step_type="scroll",
                payload_json={"target": "page", "direction": "down", "distance": 420, "behavior": "smooth"},
            ),
            case_run_id=1,
            template_contexts={},
        )
        assert page_scroll_result.status == "passed"
        assert page.locator("[data-testid='page-scroll-status']").text_content() == "Page Scrolled"

        browser.close()


def test_bootstrap_seeds_demo_acceptance_bundle(monkeypatch):
    _reset_local_data()
    from app.db.bootstrap import (
        DEMO_CASE_CODE,
        DEMO_CASE_STEPS,
        DEMO_DEVICE_PROFILE_NAME,
        DEMO_ENV_PROFILE_NAME,
        DEMO_SUITE_CODE,
        DEMO_TEMPLATE_CODE,
        DEMO_WORKSPACE_CODE,
        seed_default_admin,
        seed_demo_acceptance_data,
    )
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import BaselineRevision, DeviceProfile, EnvironmentProfile, Template, TestCase, TestCaseStep, TestSuite, Workspace, WorkspaceMember

    _install_fake_browser_adapter(monkeypatch)
    seed_default_admin()
    seed_demo_acceptance_data(force=True)
    seed_demo_acceptance_data(force=True)

    with SessionLocal() as db:
        workspace = db.query(Workspace).filter(Workspace.workspace_code == DEMO_WORKSPACE_CODE, Workspace.is_deleted.is_(False)).one()
        environment = db.query(EnvironmentProfile).filter(
            EnvironmentProfile.workspace_id == workspace.id,
            EnvironmentProfile.profile_name == DEMO_ENV_PROFILE_NAME,
            EnvironmentProfile.is_deleted.is_(False),
        ).one()
        device = db.query(DeviceProfile).filter(
            DeviceProfile.workspace_id == workspace.id,
            DeviceProfile.profile_name == DEMO_DEVICE_PROFILE_NAME,
            DeviceProfile.is_deleted.is_(False),
        ).one()
        template = db.query(Template).filter(
            Template.workspace_id == workspace.id,
            Template.template_code == DEMO_TEMPLATE_CODE,
            Template.is_deleted.is_(False),
        ).one()
        baseline = db.query(BaselineRevision).filter(BaselineRevision.id == template.current_baseline_revision_id).one()
        test_case = db.query(TestCase).filter(
            TestCase.workspace_id == workspace.id,
            TestCase.case_code == DEMO_CASE_CODE,
            TestCase.is_deleted.is_(False),
        ).one()
        suite = db.query(TestSuite).filter(
            TestSuite.workspace_id == workspace.id,
            TestSuite.suite_code == DEMO_SUITE_CODE,
            TestSuite.is_deleted.is_(False),
        ).one()
        member = db.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == workspace.owner_user_id,
        ).one()
        steps = db.query(TestCaseStep).filter(TestCaseStep.test_case_id == test_case.id).order_by(TestCaseStep.step_no.asc()).all()

        assert environment.base_url.endswith("/demo/acceptance-target")
        assert device.is_default is True
        assert template.current_baseline_revision_id is not None
        assert baseline.media_object_id is not None
        assert test_case.status == "published"
        assert suite.status == "active"
        assert member.workspace_role == "workspace_admin"
        assert len(steps) == len(DEMO_CASE_STEPS)

        workspace_id = workspace.id
        environment_profile_id = environment.id
        test_suite_id = suite.id

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert login_resp.status_code == 201
        token = login_resp.json()["data"]["access_token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-Id": str(workspace_id),
            "Idempotency-Key": "seeded-demo-run",
        }

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=headers,
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers={"Authorization": f"Bearer {token}"})
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "passed"


def test_mvp_backend_smoke_flow(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import MediaObject, ReportArtifact, RunReport, StepResult

    _install_fake_browser_adapter(monkeypatch)

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        assert login_resp.status_code == 201
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "mvp_demo", "workspace_name": "MVP Demo"},
            headers=headers,
        )
        assert workspace_resp.status_code == 201
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        assert env_resp.status_code == 201
        environment_profile_id = env_resp.json()["data"]["id"]

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_login", "case_name": "Login Case", "status": "published"},
            headers=workspace_headers,
        )
        assert case_resp.status_code == 201
        test_case_id = case_resp.json()["data"]["id"]

        steps_resp = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Wait Render", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )
        assert steps_resp.status_code == 200

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_smoke", "suite_name": "Smoke Suite", "status": "active"},
            headers=workspace_headers,
        )
        assert suite_resp.status_code == 201
        test_suite_id = suite_resp.json()["data"]["id"]

        suite_cases_resp = client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )
        assert suite_cases_resp.status_code == 200

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-001"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "passed"

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        assert case_runs_resp.status_code == 200
        case_runs = case_runs_resp.json()["data"]
        assert len(case_runs) == 1
        assert case_runs[0]["status"] == "passed"

        step_results_resp = client.get(f"/api/v1/case-runs/{case_runs[0]['id']}/step-results", headers=workspace_headers)
        assert step_results_resp.status_code == 200
        assert len(step_results_resp.json()["data"]) == 1

        with SessionLocal() as db:
            report = db.query(RunReport).filter(RunReport.test_run_id == test_run_id).one()
            step_result = db.query(StepResult).filter(StepResult.case_run_id == case_runs[0]["id"]).one()
            media = db.query(MediaObject).filter(MediaObject.id == step_result.actual_media_object_id).one()
            artifact = db.query(ReportArtifact).filter(ReportArtifact.report_id == report.id).one()
            report_resp = client.get(f"/api/v1/reports/{report.id}", headers=workspace_headers)
            assert report_resp.status_code == 200
            assert report_resp.json()["data"]["summary_status"] == "passed"
            assert report_resp.json()["data"]["summary_json"]["status"] == "passed"
            assert report_resp.json()["data"]["summary_json"]["counts"]["passed"] == 1
            assert step_result.actual_media_object_id is not None
            assert media.usage == "artifact"
            assert artifact.media_object_id == media.id
            assert artifact.artifact_type == "run_screenshot"
            assert artifact.case_run_id == case_runs[0]["id"]
            assert artifact.step_result_id is None
            assert artifact.artifact_url == f"/api/v1/media-objects/{media.id}/content"


def test_empty_suite_cannot_create_test_run():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "empty_suite_ws", "workspace_name": "Empty Suite WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_empty", "suite_name": "Empty Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-empty"},
        )
        assert run_resp.status_code == 422
        assert run_resp.json()["error"]["code"] == "TEST_SUITE_EMPTY"


def test_cancelling_test_run_transitions_to_cancelled(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import RunReport, TestRun
    from app.workers.execution import process_test_run as real_process_test_run

    _install_noop_dispatcher(monkeypatch)
    _install_fake_browser_adapter(monkeypatch)

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "cancel_ws", "workspace_name": "Cancel WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "cancel_case", "case_name": "Cancel Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Wait Render", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_cancel", "suite_name": "Cancel Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-cancel"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]
        assert run_resp.json()["data"]["status"] == "queued"

        cancelling_resp = client.patch(
            f"/api/v1/test-runs/{test_run_id}",
            json={"status": "cancelling"},
            headers=workspace_headers,
        )
        assert cancelling_resp.status_code == 200
        assert cancelling_resp.json()["data"]["status"] == "cancelling"

        real_process_test_run(test_run_id)

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "cancelled"

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        assert case_runs_resp.status_code == 200
        assert case_runs_resp.json()["data"][0]["status"] == "cancelled"
        assert case_runs_resp.json()["data"][0]["failure_reason_code"] == "TEST_RUN_CANCELLED"
        assert case_runs_resp.json()["data"][0]["failure_summary"] == "Test run was cancelled."

        with SessionLocal() as db:
            test_run = db.get(TestRun, test_run_id)
            report = db.query(RunReport).filter(RunReport.test_run_id == test_run_id).one()
            assert test_run.status == "cancelled"
            assert report.summary_status == "cancelled"
            assert report.summary_json["cancelled_case_count"] == 1
            assert report.summary_json["failure"]["code"] == "TEST_RUN_CANCELLED"
            assert report.summary_json["failure"]["summary"] == "Test run was cancelled."


def test_cancelling_during_finalization_does_not_end_as_passed(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import RunReport, TestRun, User
    from app.services import execution as execution_service
    from app.services.execution import finalize_completed_test_run as real_finalize_completed_test_run
    from app.workers.execution import process_test_run as real_process_test_run
    from sqlalchemy import select

    _install_noop_dispatcher(monkeypatch)
    _install_fake_browser_adapter(monkeypatch)

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "finalize_race_ws", "workspace_name": "Finalize Race WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "finalize_race_case", "case_name": "Finalize Race Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Wait Render", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_finalize_race", "suite_name": "Finalize Race Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-finalize-race"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        patch_sent = {"done": False}

        def racing_finalize(db, test_run, *, passed_count: int, failed_count: int, error_count: int):
            if not patch_sent["done"]:
                patch_sent["done"] = True
                with SessionLocal() as competing_db:
                    latest_test_run = competing_db.get(TestRun, test_run.id)
                    current_user = competing_db.scalar(select(User).where(User.username == "admin"))
                    assert current_user is not None
                    updated = execution_service.update_test_run_status(
                        competing_db,
                        user=current_user,
                        test_run=latest_test_run,
                        status="cancelling",
                    )
                    assert updated.status == "cancelling"
            return real_finalize_completed_test_run(
                db,
                test_run,
                passed_count=passed_count,
                failed_count=failed_count,
                error_count=error_count,
            )

        monkeypatch.setattr("app.workers.execution.finalize_completed_test_run", racing_finalize)

        real_process_test_run(test_run_id)

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "cancelled"

        with SessionLocal() as db:
            test_run = db.get(TestRun, test_run_id)
            report = db.query(RunReport).filter(RunReport.test_run_id == test_run_id).one()
            assert test_run.status == "cancelled"
            assert report.summary_status == "cancelled"


def test_invalid_template_assert_step_is_rejected_during_step_save():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "unsupported_ws", "workspace_name": "Unsupported WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "unsupported_case", "case_name": "Unsupported Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "template_assert", "step_name": "Unsupported", "payload_json": {}}],
            headers=workspace_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"


def test_invalid_ocr_assert_step_is_rejected_during_step_save():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "invalid_ocr_ws", "workspace_name": "Invalid OCR WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "invalid_ocr_case", "case_name": "Invalid OCR Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "ocr_assert", "step_name": "Invalid OCR", "payload_json": {"selector": "#main"}}],
            headers=workspace_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"


def test_new_step_types_are_saved_for_components_and_test_cases():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "new_steps_ws", "workspace_name": "New Steps WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        component_resp = client.post(
            "/api/v1/components",
            json={"component_code": "cmp_new_steps", "component_name": "New Steps Component", "status": "published"},
            headers=workspace_headers,
        )
        component_id = component_resp.json()["data"]["id"]

        component_steps_resp = client.put(
            f"/api/v1/components/{component_id}/steps",
            json=[
                {"step_no": 1, "step_type": "navigate", "step_name": "Open Details", "payload_json": {"url": "/demo/acceptance-target?view=details"}, "timeout_ms": 21000, "retry_times": 1},
                {"step_no": 2, "step_type": "scroll", "step_name": "Scroll Container", "payload_json": {"target": "element", "selector": "[data-testid='scroll-container']", "direction": "down", "distance": 220}, "timeout_ms": 22000, "retry_times": 2},
                {"step_no": 3, "step_type": "long_press", "step_name": "Press Target", "payload_json": {"selector": "[data-testid='long-press-target']", "duration_ms": 800}, "timeout_ms": 23000, "retry_times": 3},
            ],
            headers=workspace_headers,
        )
        assert component_steps_resp.status_code == 200
        assert [item["step_type"] for item in component_steps_resp.json()["data"]] == ["navigate", "scroll", "long_press"]
        assert [item["timeout_ms"] for item in component_steps_resp.json()["data"]] == [21000, 22000, 23000]
        assert [item["retry_times"] for item in component_steps_resp.json()["data"]] == [1, 2, 3]

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_new_steps", "case_name": "Case New Steps", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        case_steps_resp = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {"step_no": 1, "step_type": "navigate", "step_name": "Open Details", "payload_json": {"url": "/demo/acceptance-target?view=details", "wait_until": "domcontentloaded"}},
                {"step_no": 2, "step_type": "scroll", "step_name": "Scroll Page", "payload_json": {"target": "page", "direction": "down", "distance": 360, "behavior": "smooth"}},
                {"step_no": 3, "step_type": "long_press", "step_name": "Press Target", "payload_json": {"selector": "[data-testid='long-press-target']", "duration_ms": 800, "button": "left"}},
            ],
            headers=workspace_headers,
        )
        assert case_steps_resp.status_code == 200
        assert [item["step_type"] for item in case_steps_resp.json()["data"]] == ["navigate", "scroll", "long_press"]
        assert case_steps_resp.json()["data"][0]["payload_json"]["wait_until"] == "domcontentloaded"
        assert case_steps_resp.json()["data"][1]["payload_json"]["behavior"] == "smooth"


def test_invalid_navigate_step_is_rejected_during_step_save():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "invalid_nav_ws", "workspace_name": "Invalid Navigate WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "invalid_nav_case", "case_name": "Invalid Navigate Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "navigate", "step_name": "Invalid Navigate", "payload_json": {"url": "login", "wait_until": "ready"}}],
            headers=workspace_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"


def test_invalid_scroll_step_is_rejected_during_step_save():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "invalid_scroll_ws", "workspace_name": "Invalid Scroll WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "invalid_scroll_case", "case_name": "Invalid Scroll Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "scroll", "step_name": "Invalid Scroll", "payload_json": {"target": "element", "direction": "down", "distance": 0}}],
            headers=workspace_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"


def test_invalid_long_press_step_is_rejected_during_step_save():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "invalid_press_ws", "workspace_name": "Invalid Long Press WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "invalid_press_case", "case_name": "Invalid Long Press Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        response = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "long_press", "step_name": "Invalid Long Press", "payload_json": {"selector": "#target", "duration_ms": -1, "button": "right"}}],
            headers=workspace_headers,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"


def test_template_create_rejects_unsupported_match_strategy():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "unsupported_strategy_ws", "workspace_name": "Unsupported Strategy WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        media_object_id = _create_media_object(client, headers=workspace_headers)
        response = client.post(
            "/api/v1/templates",
            headers=workspace_headers,
            json={
                "template_code": "tpl_orb",
                "template_name": "ORB Template",
                "template_type": "page",
                "match_strategy": "orb",
                "threshold_value": 0.95,
                "status": "draft",
                "original_media_object_id": media_object_id,
            },
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "TEMPLATE_MATCH_STRATEGY_UNSUPPORTED"


def test_template_ocr_analysis_persists_snapshot_and_can_be_read(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import TemplateOCRResult

    _install_template_workbench_adapter(monkeypatch)

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_ocr_ws", "workspace_name": "Template OCR WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_ocr_snapshot",
            template_name="OCR Snapshot Template",
        )
        baseline_revision_id = _get_template_current_baseline_revision_id(client, headers=workspace_headers, template_id=template_id)

        create_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
            headers=workspace_headers,
        )
        assert create_resp.status_code == 201
        payload = create_resp.json()["data"]
        assert payload["status"] == "succeeded"
        assert payload["engine_name"] == "paddleocr"
        assert payload["image_width"] == 200
        assert payload["image_height"] == 100
        assert payload["blocks"][0]["text"] == "VisionAutoTest"
        assert payload["blocks"][0]["ratio_rect"]["x_ratio"] == 0.1

        get_resp = client.get(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
            headers=workspace_headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["id"] == payload["id"]

        with SessionLocal() as db:
            snapshots = db.query(TemplateOCRResult).filter(TemplateOCRResult.template_id == template_id).all()
            assert len(snapshots) == 1
            assert snapshots[0].baseline_revision_id == baseline_revision_id


def test_template_ocr_analysis_rerun_updates_same_snapshot(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import TemplateOCRResult

    _install_template_workbench_adapter(
        monkeypatch,
        analyses=[
            {
                "engine_name": "paddleocr",
                "image_width": 200,
                "image_height": 100,
                "blocks": [
                    {
                        "order_no": 1,
                        "text": "first-run",
                        "confidence": 0.91,
                        "polygon_points": [{"x": 10, "y": 10}, {"x": 60, "y": 10}, {"x": 60, "y": 24}, {"x": 10, "y": 24}],
                        "pixel_rect": {"x": 10, "y": 10, "width": 50, "height": 14},
                        "ratio_rect": {"x_ratio": 0.05, "y_ratio": 0.1, "width_ratio": 0.25, "height_ratio": 0.14},
                    }
                ],
            },
            {
                "engine_name": "paddleocr",
                "image_width": 200,
                "image_height": 100,
                "blocks": [
                    {
                        "order_no": 1,
                        "text": "second-run",
                        "confidence": 0.95,
                        "polygon_points": [{"x": 20, "y": 20}, {"x": 80, "y": 20}, {"x": 80, "y": 40}, {"x": 20, "y": 40}],
                        "pixel_rect": {"x": 20, "y": 20, "width": 60, "height": 20},
                        "ratio_rect": {"x_ratio": 0.1, "y_ratio": 0.2, "width_ratio": 0.3, "height_ratio": 0.2},
                    }
                ],
            },
        ],
    )

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_ocr_rerun_ws", "workspace_name": "Template OCR Rerun WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_ocr_rerun",
            template_name="OCR Rerun Template",
        )
        baseline_revision_id = _get_template_current_baseline_revision_id(client, headers=workspace_headers, template_id=template_id)

        first_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
            headers=workspace_headers,
        )
        second_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
            headers=workspace_headers,
        )

        assert first_resp.status_code == 201
        assert second_resp.status_code == 201
        assert first_resp.json()["data"]["id"] == second_resp.json()["data"]["id"]
        assert second_resp.json()["data"]["blocks"][0]["text"] == "second-run"

        with SessionLocal() as db:
            snapshots = db.query(TemplateOCRResult).filter(TemplateOCRResult.template_id == template_id).all()
            assert len(snapshots) == 1
            assert snapshots[0].result_json["blocks"][0]["text"] == "second-run"


def test_template_ocr_missing_snapshot_returns_not_generated_placeholder(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_template_workbench_adapter(monkeypatch)

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_ocr_missing_ws", "workspace_name": "Template OCR Missing WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_ocr_missing",
            template_name="OCR Missing Template",
        )
        baseline_revision_id = _get_template_current_baseline_revision_id(client, headers=workspace_headers, template_id=template_id)

        response = client.get(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
            headers=workspace_headers,
        )
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["status"] == "not_generated"
        assert payload["error_code"] == "TEMPLATE_OCR_RESULT_NOT_FOUND"
        assert payload["blocks"] == []
        assert payload["id"] is None


def test_template_ocr_failure_persists_failed_snapshot(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import TemplateOCRResult

    _install_template_workbench_adapter(monkeypatch, ocr_error="ocr engine unavailable")

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_ocr_fail_ws", "workspace_name": "Template OCR Fail WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_ocr_fail",
            template_name="OCR Fail Template",
        )
        baseline_revision_id = _get_template_current_baseline_revision_id(client, headers=workspace_headers, template_id=template_id)

        create_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
            headers=workspace_headers,
        )
        assert create_resp.status_code == 500
        assert create_resp.json()["error"]["code"] == "TEMPLATE_OCR_ANALYSIS_FAILED"

        get_resp = client.get(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
            headers=workspace_headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["status"] == "failed"
        assert get_resp.json()["data"]["error_code"] == "TEMPLATE_OCR_ANALYSIS_FAILED"
        assert get_resp.json()["data"]["blocks"] == []

        with SessionLocal() as db:
            snapshot = db.query(TemplateOCRResult).filter(TemplateOCRResult.template_id == template_id).one()
            assert snapshot.status == "failed"
            assert snapshot.error_code == "TEMPLATE_OCR_ANALYSIS_FAILED"


def test_template_preview_uses_persisted_masks_when_request_omitted(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_template_workbench_adapter(monkeypatch)

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_preview_ws", "workspace_name": "Template Preview WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_preview_saved",
            template_name="Preview Saved Template",
        )
        baseline_revision_id = _get_template_current_baseline_revision_id(client, headers=workspace_headers, template_id=template_id)

        mask_resp = client.post(
            f"/api/v1/templates/{template_id}/mask-regions",
            headers=workspace_headers,
            json={"region_name": "saved_mask", "x_ratio": 0.1, "y_ratio": 0.2, "width_ratio": 0.3, "height_ratio": 0.2, "sort_order": 1},
        )
        assert mask_resp.status_code == 201

        preview_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/preview-images",
            headers=workspace_headers,
            json={},
        )
        assert preview_resp.status_code == 201
        payload = preview_resp.json()["data"]
        assert payload["image_width"] == 200
        assert payload["image_height"] == 100
        assert payload["mask_regions"][0]["name"] == "saved_mask"
        assert payload["overlay_content_url"].endswith(f"/api/v1/media-objects/{payload['overlay_media_object_id']}/content")
        assert payload["processed_content_url"].endswith(f"/api/v1/media-objects/{payload['processed_media_object_id']}/content")

        overlay_resp = client.get(payload["overlay_content_url"], headers=workspace_headers)
        processed_resp = client.get(payload["processed_content_url"], headers=workspace_headers)
        assert overlay_resp.status_code == 200
        assert processed_resp.status_code == 200


def test_template_preview_draft_masks_do_not_persist(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_template_workbench_adapter(monkeypatch)

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_preview_draft_ws", "workspace_name": "Template Preview Draft WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_preview_draft",
            template_name="Preview Draft Template",
        )
        baseline_revision_id = _get_template_current_baseline_revision_id(client, headers=workspace_headers, template_id=template_id)

        preview_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions/{baseline_revision_id}/preview-images",
            headers=workspace_headers,
            json={
                "mask_regions": [
                    {"name": "draft_1", "x_ratio": 0.05, "y_ratio": 0.1, "width_ratio": 0.2, "height_ratio": 0.2, "sort_order": 2},
                    {"x_ratio": 0.4, "y_ratio": 0.2, "width_ratio": 0.1, "height_ratio": 0.1, "sort_order": 1},
                ]
            },
        )
        assert preview_resp.status_code == 201
        payload = preview_resp.json()["data"]
        assert len(payload["mask_regions"]) == 2
        assert payload["mask_regions"][0]["name"] == "mask_region_2"
        assert payload["mask_regions"][1]["name"] == "draft_1"

        list_resp = client.get(f"/api/v1/templates/{template_id}/mask-regions", headers=workspace_headers)
        assert list_resp.status_code == 200
        assert list_resp.json()["data"] == []


def test_environment_secret_values_are_encrypted_at_rest():
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import EnvironmentVariable

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "env_secret_ws", "workspace_name": "Env Secret WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "secret-env", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        create_resp = client.post(
            f"/api/v1/environment-profiles/{environment_profile_id}/variables",
            headers=workspace_headers,
            json={"var_key": "API_TOKEN", "value": "plain-secret-value", "is_secret": True},
        )
        assert create_resp.status_code == 201
        assert create_resp.json()["data"]["display_value"] == "******"

        with SessionLocal() as db:
            variable = db.query(EnvironmentVariable).filter(EnvironmentVariable.environment_profile_id == environment_profile_id).one()
            assert variable.var_value_ciphertext != "plain-secret-value"
            assert "plain-secret-value" not in variable.var_value_ciphertext

def test_adapter_initialization_failure_marks_test_run_error(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import RunReport

    monkeypatch.setattr("app.workers.execution.build_browser_execution_adapter", lambda: (_ for _ in ()).throw(RuntimeError("adapter init failed")))

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "adapter_failure_ws", "workspace_name": "Adapter Failure WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "adapter_failure_case", "case_name": "Adapter Failure Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Wait Render", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_adapter_failure", "suite_name": "Adapter Failure Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-adapter-failure"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "error"
        assert detail_resp.json()["data"]["error_case_count"] == 1

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        assert case_runs_resp.status_code == 200
        assert case_runs_resp.json()["data"][0]["status"] == "error"
        assert case_runs_resp.json()["data"][0]["failure_reason_code"] == "TEST_RUN_EXECUTION_ERROR"

        with SessionLocal() as db:
            report = db.query(RunReport).filter(RunReport.test_run_id == test_run_id).one()
            assert report.summary_status == "error"
            assert "adapter init failed" in report.summary_json["message"]
            assert report.summary_json["failure"]["code"] == "TEST_RUN_EXECUTION_ERROR"


def test_component_call_steps_are_expanded_and_executed(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_fake_browser_adapter(monkeypatch)

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "component_call_ws", "workspace_name": "Component Call WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        component_resp = client.post(
            "/api/v1/components",
            json={"component_code": "shared_login", "component_name": "Shared Login", "status": "published"},
            headers=workspace_headers,
        )
        assert component_resp.status_code == 201
        component = component_resp.json()["data"]
        assert component["published_at"] is not None
        component_id = component["id"]

        component_steps_resp = client.put(
            f"/api/v1/components/{component_id}/steps",
            json=[
                {"step_no": 1, "step_type": "wait", "step_name": "Wait In Component", "payload_json": {"ms": 100}},
                {"step_no": 2, "step_type": "click", "step_name": "Click In Component", "payload_json": {"selector": "#login"}},
            ],
            headers=workspace_headers,
        )
        assert component_steps_resp.status_code == 200

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_component_call", "case_name": "Component Call Case", "status": "published"},
            headers=workspace_headers,
        )
        assert case_resp.status_code == 201
        test_case_id = case_resp.json()["data"]["id"]

        case_steps_resp = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {"step_no": 1, "step_type": "wait", "step_name": "Outer Wait", "payload_json": {"ms": 100}},
                {"step_no": 2, "step_type": "component_call", "step_name": "Invoke Component", "component_id": component_id},
                {"step_no": 3, "step_type": "input", "step_name": "Outer Input", "payload_json": {"selector": "#username", "text": "admin"}},
            ],
            headers=workspace_headers,
        )
        assert case_steps_resp.status_code == 200

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_component_call", "suite_name": "Component Call Suite", "status": "active"},
            headers=workspace_headers,
        )
        assert suite_resp.status_code == 201
        test_suite_id = suite_resp.json()["data"]["id"]

        suite_cases_resp = client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )
        assert suite_cases_resp.status_code == 200

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-component-call"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        assert case_runs_resp.status_code == 200
        case_run_id = case_runs_resp.json()["data"][0]["id"]

        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        assert step_results_resp.status_code == 200
        step_results = step_results_resp.json()["data"]
        assert len(step_results) == 4
        assert [item["step_no"] for item in step_results] == [1, 2, 3, 4]
        assert [item["step_type"] for item in step_results] == ["wait", "wait", "click", "input"]
        assert all(item["status"] == "passed" for item in step_results)


def test_component_call_can_expand_new_browser_steps(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_fake_browser_adapter(monkeypatch)

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "component_new_steps_ws", "workspace_name": "Component New Steps WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        component_resp = client.post(
            "/api/v1/components",
            json={"component_code": "shared_interactions", "component_name": "Shared Interactions", "status": "published"},
            headers=workspace_headers,
        )
        component_id = component_resp.json()["data"]["id"]

        component_steps_resp = client.put(
            f"/api/v1/components/{component_id}/steps",
            json=[
                {"step_no": 1, "step_type": "scroll", "step_name": "Scroll Container", "payload_json": {"target": "element", "selector": "[data-testid='scroll-container']", "direction": "down", "distance": 180}},
                {"step_no": 2, "step_type": "long_press", "step_name": "Long Press In Component", "payload_json": {"selector": "[data-testid='long-press-target']", "duration_ms": 800}},
            ],
            headers=workspace_headers,
        )
        assert component_steps_resp.status_code == 200

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_component_new_steps", "case_name": "Component New Steps Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        case_steps_resp = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {"step_no": 1, "step_type": "navigate", "step_name": "Navigate First", "payload_json": {"url": "/demo/acceptance-target?view=details"}},
                {"step_no": 2, "step_type": "component_call", "step_name": "Invoke Component", "component_id": component_id},
            ],
            headers=workspace_headers,
        )
        assert case_steps_resp.status_code == 200

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_component_new_steps", "suite_name": "Component New Steps Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={"test_suite_id": test_suite_id, "environment_profile_id": environment_profile_id, "trigger_source": "manual"},
            headers=workspace_headers | {"Idempotency-Key": "run-component-new-steps"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_results = step_results_resp.json()["data"]
        assert [item["step_type"] for item in step_results] == ["navigate", "scroll", "long_press"]
        assert all(item["status"] == "passed" for item in step_results)


def test_new_browser_steps_work_with_ocr_assert_execution(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_visual_browser_adapter(monkeypatch, ocr_status="passed")

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "browser_ocr_ws", "workspace_name": "Browser OCR WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_browser_ocr", "case_name": "Browser OCR Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {"step_no": 1, "step_type": "navigate", "step_name": "Navigate", "payload_json": {"url": "/demo/acceptance-target?view=details"}},
                {"step_no": 2, "step_type": "long_press", "step_name": "Long Press", "payload_json": {"selector": "[data-testid='long-press-target']", "duration_ms": 800}},
                {"step_no": 3, "step_type": "ocr_assert", "step_name": "OCR Check", "payload_json": {"selector": "[data-testid='result-banner']", "expected_text": "details"}},
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_browser_ocr", "suite_name": "Browser OCR Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={"test_suite_id": test_suite_id, "environment_profile_id": environment_profile_id, "trigger_source": "manual"},
            headers=workspace_headers | {"Idempotency-Key": "run-browser-ocr"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "passed"

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_results = step_results_resp.json()["data"]
        assert [item["step_type"] for item in step_results] == ["navigate", "long_press", "ocr_assert"]
        assert all(item["status"] == "passed" for item in step_results)


def test_template_assert_requires_matching_template_strategy_before_execution():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_strategy_ws", "workspace_name": "Template Strategy WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_ocr_only",
            template_name="OCR Template",
            match_strategy="ocr",
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_template_strategy", "case_name": "Template Strategy Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        case_steps_resp = client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Template Assert",
                    "template_id": template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )
        assert case_steps_resp.status_code == 422
        assert case_steps_resp.json()["error"]["code"] == "STEP_CONFIGURATION_INVALID"


def test_template_assert_success_persists_expected_and_actual_media(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_visual_browser_adapter(monkeypatch, template_status="passed")

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_pass_ws", "workspace_name": "Template Pass WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_pass",
            template_name="Pass Template",
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_template_pass", "case_name": "Template Pass Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Template Pass",
                    "template_id": template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_template_pass", "suite_name": "Template Pass Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-template-pass"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "passed"

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]
        assert step_result["status"] == "passed"
        assert step_result["expected_media_object_id"] is not None
        assert step_result["actual_media_object_id"] is not None
        assert step_result["diff_media_object_id"] is None
        report_resp = client.get(f"/api/v1/test-runs/{test_run_id}/report", headers=workspace_headers)
        artifacts_resp = client.get(f"/api/v1/reports/{report_resp.json()['data']['id']}/artifacts", headers=workspace_headers)
        assert artifacts_resp.status_code == 200
        assert {item["artifact_type"] for item in artifacts_resp.json()["data"]} == {"run_screenshot", "step_actual"}


def test_template_assert_failure_marks_run_failed_and_persists_diff_media(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_visual_browser_adapter(monkeypatch, template_status="failed")

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "template_fail_ws", "workspace_name": "Template Fail WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_fail",
            template_name="Fail Template",
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_template_fail", "case_name": "Template Fail Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Template Fail",
                    "template_id": template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_template_fail", "suite_name": "Template Fail Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-template-fail"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "failed"

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        assert case_runs_resp.json()["data"][0]["status"] == "failed"
        assert case_runs_resp.json()["data"][0]["failure_reason_code"] == "TEMPLATE_ASSERTION_FAILED"
        assert case_runs_resp.json()["data"][0]["failure_summary"] == "Template assertion failed."
        case_run_id = case_runs_resp.json()["data"][0]["id"]

        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]
        assert step_result["status"] == "failed"
        assert step_result["expected_media_object_id"] is not None
        assert step_result["actual_media_object_id"] is not None
        assert step_result["diff_media_object_id"] is not None
        report_resp = client.get(f"/api/v1/test-runs/{test_run_id}/report", headers=workspace_headers)
        assert report_resp.json()["data"]["summary_json"]["failure"]["code"] == "TEMPLATE_ASSERTION_FAILED"
        assert report_resp.json()["data"]["summary_json"]["failure"]["summary"] == "Template assertion failed."
        artifacts_resp = client.get(f"/api/v1/reports/{report_resp.json()['data']['id']}/artifacts", headers=workspace_headers)
        assert artifacts_resp.status_code == 200
        assert {item["artifact_type"] for item in artifacts_resp.json()["data"]} == {"run_screenshot", "step_actual", "step_diff"}
        assert all(item["artifact_url"] == f"/api/v1/media-objects/{item['media_object_id']}/content" for item in artifacts_resp.json()["data"])


def test_ocr_assert_failure_marks_run_failed(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_visual_browser_adapter(monkeypatch, ocr_status="failed")

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "ocr_fail_ws", "workspace_name": "OCR Fail WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_ocr_fail", "case_name": "OCR Fail Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "ocr_assert",
                    "step_name": "OCR Fail",
                    "payload_json": {"selector": "#main", "expected_text": "expected text"},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_ocr_fail", "suite_name": "OCR Fail Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-ocr-fail"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        detail_resp = client.get(f"/api/v1/test-runs/{test_run_id}", headers=workspace_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["data"]["status"] == "failed"

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        assert case_runs_resp.json()["data"][0]["status"] == "failed"
        case_run_id = case_runs_resp.json()["data"][0]["id"]

        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]
        assert step_result["status"] == "failed"
        assert step_result["actual_media_object_id"] is not None
        assert step_result["diff_media_object_id"] is None
        report_resp = client.get(f"/api/v1/test-runs/{test_run_id}/report", headers=workspace_headers)
        assert report_resp.json()["data"]["summary_json"]["failure"]["code"] == "OCR_ASSERTION_FAILED"
        assert report_resp.json()["data"]["summary_json"]["failure"]["summary"] == "OCR assertion failed."
        artifacts_resp = client.get(f"/api/v1/reports/{report_resp.json()['data']['id']}/artifacts", headers=workspace_headers)
        assert artifacts_resp.status_code == 200
        assert {item["artifact_type"] for item in artifacts_resp.json()["data"]} == {"run_screenshot", "step_ocr"}
        assert all(item["artifact_url"] == f"/api/v1/media-objects/{item['media_object_id']}/content" for item in artifacts_resp.json()["data"])


def test_partial_failed_run_has_stable_report_failure_summary(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_visual_browser_adapter(monkeypatch, template_status="failed")

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "partial_failed_ws", "workspace_name": "Partial Failed WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        pass_case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "partial_pass_case", "case_name": "Partial Pass Case", "status": "published"},
            headers=workspace_headers,
        )
        pass_case_id = pass_case_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-cases/{pass_case_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Pass Wait", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_partial_fail",
            template_name="Partial Fail Template",
        )
        fail_case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "partial_fail_case", "case_name": "Partial Fail Case", "status": "published"},
            headers=workspace_headers,
        )
        fail_case_id = fail_case_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-cases/{fail_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Fail Template",
                    "template_id": template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_partial_fail", "suite_name": "Partial Fail Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[
                {"test_case_id": pass_case_id, "sort_order": 1},
                {"test_case_id": fail_case_id, "sort_order": 2},
            ],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-partial-fail"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        report_resp = client.get(f"/api/v1/test-runs/{test_run_id}/report", headers=workspace_headers)
        assert report_resp.status_code == 200
        assert report_resp.json()["data"]["summary_status"] == "partial_failed"
        assert report_resp.json()["data"]["summary_json"]["failure"]["code"] == "TEMPLATE_ASSERTION_FAILED"
        assert report_resp.json()["data"]["summary_json"]["failure"]["summary"] == "Template assertion failed."


def test_failure_evidence_can_be_adopted_as_new_baseline(monkeypatch):
    _reset_local_data()
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import BaselineRevision, Template

    _install_visual_browser_adapter(monkeypatch, template_status="failed")

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "baseline_adopt_ws", "workspace_name": "Baseline Adopt WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_adopt_source",
            template_name="Adopt Source Template",
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_adopt_source", "case_name": "Adopt Source Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Adopt Source Step",
                    "template_id": template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_adopt_source", "suite_name": "Adopt Source Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-baseline-adopt"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]
        report_resp = client.get(f"/api/v1/test-runs/{test_run_id}/report", headers=workspace_headers)
        report_id = report_resp.json()["data"]["id"]

        adopt_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions",
            headers=workspace_headers,
            json={
                "media_object_id": step_result["actual_media_object_id"],
                "source_type": "adopted_from_failure",
                "source_report_id": report_id,
                "source_case_run_id": case_run_id,
                "source_step_result_id": step_result["id"],
                "remark": "accept latest screenshot",
                "is_current": True,
            },
        )
        assert adopt_resp.status_code == 201
        baseline = adopt_resp.json()["data"]
        assert baseline["source_type"] == "adopted_from_failure"
        assert baseline["source_report_id"] == report_id
        assert baseline["source_case_run_id"] == case_run_id
        assert baseline["source_step_result_id"] == step_result["id"]
        assert baseline["media_object_id"] == step_result["actual_media_object_id"]

        with SessionLocal() as db:
            template = db.get(Template, template_id)
            assert template is not None
            assert template.current_baseline_revision_id == baseline["id"]
            revisions = db.query(BaselineRevision).filter(BaselineRevision.template_id == template_id).order_by(BaselineRevision.revision_no.asc()).all()
            assert revisions[-1].source_report_id == report_id
            assert revisions[-1].source_case_run_id == case_run_id
            assert revisions[-1].source_step_result_id == step_result["id"]
            assert revisions[-1].is_current is True
            assert revisions[0].is_current is False


def test_baseline_adoption_rejects_mismatched_failure_chain(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_visual_browser_adapter(monkeypatch, template_status="failed")

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "baseline_mismatch_ws", "workspace_name": "Baseline Mismatch WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        media_object_id = _create_media_object(client, headers=workspace_headers)
        source_template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_mismatch_source",
            template_name="Mismatch Source Template",
        )
        other_media_resp = client.post(
            "/api/v1/media-objects",
            headers=workspace_headers,
            data={"usage": "artifact"},
            files={"file": ("other-baseline.png", TINY_PNG_BYTES + b"-other-template", "image/png")},
        )
        assert other_media_resp.status_code == 201
        other_media_object_id = other_media_resp.json()["data"]["id"]
        target_template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=other_media_object_id,
            template_code="tpl_mismatch_target",
            template_name="Mismatch Target Template",
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_mismatch_source", "case_name": "Mismatch Source Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Mismatch Step",
                    "template_id": source_template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_mismatch_source", "suite_name": "Mismatch Source Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-baseline-mismatch"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]

        mismatch_resp = client.post(
            f"/api/v1/templates/{target_template_id}/baseline-revisions",
            headers=workspace_headers,
            json={
                "media_object_id": step_result["actual_media_object_id"],
                "source_type": "adopted_from_failure",
                "source_step_result_id": step_result["id"],
                "is_current": True,
            },
        )
        assert mismatch_resp.status_code == 422
        assert mismatch_resp.json()["error"]["code"] == "BASELINE_ADOPTION_MISMATCH"


def test_baseline_adoption_rejects_diff_media_object(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_visual_browser_adapter(monkeypatch, template_status="failed")

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "baseline_diff_ws", "workspace_name": "Baseline Diff WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_diff_source",
            template_name="Diff Source Template",
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_diff_source", "case_name": "Diff Source Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Diff Step",
                    "template_id": template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_diff_source", "suite_name": "Diff Source Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-baseline-diff"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]

        invalid_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions",
            headers=workspace_headers,
            json={
                "media_object_id": step_result["diff_media_object_id"],
                "source_type": "adopted_from_failure",
                "source_step_result_id": step_result["id"],
                "is_current": True,
            },
        )
        assert invalid_resp.status_code == 422
        assert invalid_resp.json()["error"]["code"] == "BASELINE_ADOPTION_INVALID"


def test_baseline_adoption_rejects_cross_workspace_media_object(monkeypatch):
    _reset_local_data()
    from app.main import app

    _install_visual_browser_adapter(monkeypatch, template_status="failed")

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "baseline_cross_ws", "workspace_name": "Baseline Cross WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        media_object_id = _create_media_object(client, headers=workspace_headers)
        template_id = _create_template(
            client,
            headers=workspace_headers,
            media_object_id=media_object_id,
            template_code="tpl_cross_ws",
            template_name="Cross Workspace Template",
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "case_cross_ws", "case_name": "Cross Workspace Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[
                {
                    "step_no": 1,
                    "step_type": "template_assert",
                    "step_name": "Cross Workspace Step",
                    "template_id": template_id,
                    "payload_json": {},
                }
            ],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_cross_ws", "suite_name": "Cross Workspace Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]
        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        other_workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "baseline_cross_other_ws", "workspace_name": "Baseline Cross Other WS"},
            headers=headers,
        )
        other_workspace_id = other_workspace_resp.json()["data"]["id"]
        other_workspace_headers = headers | {"X-Workspace-Id": str(other_workspace_id)}
        foreign_media_object_id = _create_media_object(client, headers=other_workspace_headers)

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-baseline-cross"},
        )
        assert run_resp.status_code == 201
        test_run_id = run_resp.json()["data"]["id"]

        case_runs_resp = client.get(f"/api/v1/test-runs/{test_run_id}/case-runs", headers=workspace_headers)
        case_run_id = case_runs_resp.json()["data"][0]["id"]
        step_results_resp = client.get(f"/api/v1/case-runs/{case_run_id}/step-results", headers=workspace_headers)
        step_result = step_results_resp.json()["data"][0]

        cross_resp = client.post(
            f"/api/v1/templates/{template_id}/baseline-revisions",
            headers=workspace_headers,
            json={
                "media_object_id": foreign_media_object_id,
                "source_type": "adopted_from_failure",
                "source_step_result_id": step_result["id"],
                "is_current": True,
            },
        )
        assert cross_resp.status_code == 404
        assert cross_resp.json()["error"]["code"] == "MEDIA_OBJECT_NOT_FOUND"


def test_non_active_suite_cannot_create_test_run():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "inactive_suite_ws", "workspace_name": "Inactive Suite WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "published_case", "case_name": "Published Case", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Wait Render", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_draft", "suite_name": "Draft Suite", "status": "draft"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-inactive-suite"},
        )
        assert run_resp.status_code == 422
        assert run_resp.json()["error"]["code"] == "TEST_SUITE_NOT_ACTIVE"


def test_draft_test_case_cannot_create_test_run():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "draft_case_ws", "workspace_name": "Draft Case WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "draft_case", "case_name": "Draft Case", "status": "draft"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Wait Render", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_active_case", "suite_name": "Active Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-draft-case"},
        )
        assert run_resp.status_code == 422
        assert run_resp.json()["error"]["code"] == "PUBLISHED_VERSION_REQUIRED"


def test_draft_component_cannot_create_test_run():
    _reset_local_data()
    from app.main import app

    with TestClient(app) as client:
        login_resp = client.post("/api/v1/sessions", json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD})
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        workspace_resp = client.post(
            "/api/v1/workspaces",
            json={"workspace_code": "draft_component_ws", "workspace_name": "Draft Component WS"},
            headers=headers,
        )
        workspace_id = workspace_resp.json()["data"]["id"]
        workspace_headers = headers | {"X-Workspace-Id": str(workspace_id)}

        env_resp = client.post(
            "/api/v1/environment-profiles",
            json={"profile_name": "dev", "base_url": "https://example.com"},
            headers=workspace_headers,
        )
        environment_profile_id = env_resp.json()["data"]["id"]

        component_resp = client.post(
            "/api/v1/components",
            json={"component_code": "draft_component", "component_name": "Draft Component", "status": "draft"},
            headers=workspace_headers,
        )
        component_id = component_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/components/{component_id}/steps",
            json=[{"step_no": 1, "step_type": "wait", "step_name": "Wait In Component", "payload_json": {"ms": 100}}],
            headers=workspace_headers,
        )

        case_resp = client.post(
            "/api/v1/test-cases",
            json={"case_code": "published_case_with_component", "case_name": "Published Case With Component", "status": "published"},
            headers=workspace_headers,
        )
        test_case_id = case_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-cases/{test_case_id}/steps",
            json=[{"step_no": 1, "step_type": "component_call", "step_name": "Invoke Draft Component", "component_id": component_id}],
            headers=workspace_headers,
        )

        suite_resp = client.post(
            "/api/v1/test-suites",
            json={"suite_code": "suite_draft_component", "suite_name": "Draft Component Suite", "status": "active"},
            headers=workspace_headers,
        )
        test_suite_id = suite_resp.json()["data"]["id"]

        client.put(
            f"/api/v1/test-suites/{test_suite_id}/cases",
            json=[{"test_case_id": test_case_id, "sort_order": 1}],
            headers=workspace_headers,
        )

        run_resp = client.post(
            "/api/v1/test-runs",
            json={
                "test_suite_id": test_suite_id,
                "environment_profile_id": environment_profile_id,
                "trigger_source": "manual",
            },
            headers=workspace_headers | {"Idempotency-Key": "run-draft-component"},
        )
        assert run_resp.status_code == 422
        assert run_resp.json()["error"]["code"] == "PUBLISHED_VERSION_REQUIRED"
