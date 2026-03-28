from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol, Sequence

from app.core.config import get_settings
from app.models import DeviceProfile, TestCaseStep, utc_now


class UnsupportedStepError(Exception):
    pass


@dataclass
class BrowserArtifact:
    file_name: str
    content_type: str
    content_bytes: bytes
    artifact_type: str = "screenshot"


@dataclass
class BrowserStepResult:
    step_no: int
    step_type: str
    status: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    error_message: str | None = None
    score_value: float | None = None


@dataclass
class CaseExecutionResult:
    status: str
    step_results: list[BrowserStepResult]
    failure_reason_code: str | None = None
    failure_summary: str | None = None
    artifact: BrowserArtifact | None = None


class BrowserExecutionAdapter(Protocol):
    def execute_case(
        self,
        *,
        base_url: str,
        case_run_id: int,
        device_profile: DeviceProfile | None,
        steps: Sequence[TestCaseStep],
    ) -> CaseExecutionResult: ...


def build_browser_execution_adapter() -> BrowserExecutionAdapter:
    settings = get_settings()
    return PlaywrightBrowserExecutionAdapter(
        headless=settings.playwright_headless,
        navigation_timeout_ms=settings.playwright_navigation_timeout_ms,
    )


class PlaywrightBrowserExecutionAdapter:
    def __init__(self, *, headless: bool, navigation_timeout_ms: int) -> None:
        self._headless = headless
        self._navigation_timeout_ms = navigation_timeout_ms

    def execute_case(
        self,
        *,
        base_url: str,
        case_run_id: int,
        device_profile: DeviceProfile | None,
        steps: Sequence[TestCaseStep],
    ) -> CaseExecutionResult:
        sync_playwright, playwright_timeout_error = self._load_playwright()
        step_results: list[BrowserStepResult] = []
        failure_reason_code: str | None = None
        failure_summary: str | None = None
        artifact: BrowserArtifact | None = None

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self._headless)
                context = browser.new_context(**self._context_kwargs(device_profile))
                page = context.new_page()
                page.goto(base_url, wait_until="load", timeout=self._navigation_timeout_ms)

                for step in steps:
                    started_at = utc_now()
                    try:
                        self._execute_step(page, step)
                        status = "passed"
                        error_message = None
                    except UnsupportedStepError as exc:
                        status = "error"
                        error_message = self._format_error(exc)
                        failure_reason_code = "STEP_NOT_SUPPORTED"
                        failure_summary = error_message
                    except playwright_timeout_error as exc:
                        status = "error"
                        error_message = self._format_error(exc)
                        failure_reason_code = "STEP_EXECUTION_TIMEOUT"
                        failure_summary = error_message
                    except Exception as exc:  # noqa: BLE001
                        status = "error"
                        error_message = self._format_error(exc)
                        failure_reason_code = "STEP_EXECUTION_ERROR"
                        failure_summary = error_message

                    finished_at = utc_now()
                    step_results.append(
                        BrowserStepResult(
                            step_no=step.step_no,
                            step_type=step.step_type,
                            status=status,
                            started_at=started_at,
                            finished_at=finished_at,
                            duration_ms=_duration_ms(started_at, finished_at),
                            error_message=error_message,
                            score_value=1.0 if status == "passed" else None,
                        )
                    )
                    if status == "error":
                        break

                artifact = self._capture_artifact(page, case_run_id)
                context.close()
                browser.close()
        except Exception as exc:  # noqa: BLE001
            error_message = self._format_error(exc)
            if not step_results and steps:
                started_at = utc_now()
                finished_at = utc_now()
                step_results.append(
                    BrowserStepResult(
                        step_no=steps[0].step_no,
                        step_type=steps[0].step_type,
                        status="error",
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_ms=_duration_ms(started_at, finished_at),
                        error_message=error_message,
                    )
                )
            failure_reason_code = failure_reason_code or "BROWSER_EXECUTION_ERROR"
            failure_summary = failure_summary or error_message

        if artifact is None and failure_reason_code is None:
            failure_reason_code = "SCREENSHOT_CAPTURE_FAILED"
            failure_summary = "Browser execution completed without screenshot artifact."
            if step_results:
                step_results[-1].status = "error"
                step_results[-1].error_message = failure_summary
                step_results[-1].score_value = None

        status = "passed" if failure_reason_code is None else "error"
        return CaseExecutionResult(
            status=status,
            step_results=step_results,
            failure_reason_code=failure_reason_code,
            failure_summary=failure_summary,
            artifact=artifact,
        )

    def _load_playwright(self):
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Playwright is not installed. Run `pip install -e \".[dev]\"` and `playwright install chromium`."
            ) from exc
        return sync_playwright, PlaywrightTimeoutError

    def _context_kwargs(self, device_profile: DeviceProfile | None) -> dict:
        if device_profile is None:
            return {}
        kwargs = {
            "viewport": {
                "width": int(device_profile.viewport_width),
                "height": int(device_profile.viewport_height),
            },
            "device_scale_factor": float(device_profile.device_scale_factor),
        }
        if device_profile.user_agent:
            kwargs["user_agent"] = device_profile.user_agent
        return kwargs

    def _execute_step(self, page, step: TestCaseStep) -> None:
        payload = step.payload_json or {}
        timeout_ms = int(step.timeout_ms)
        if step.step_type == "wait":
            wait_ms = self._payload_int(payload, "ms")
            if wait_ms < 0:
                raise ValueError("wait step `ms` must be greater than or equal to 0.")
            page.wait_for_timeout(wait_ms)
            return
        if step.step_type == "click":
            selector = self._payload_str(payload, "selector")
            page.locator(selector).click(timeout=timeout_ms)
            return
        if step.step_type == "input":
            selector = self._payload_str(payload, "selector")
            text = self._payload_str(payload, "text")
            page.locator(selector).fill(text, timeout=timeout_ms)
            return
        raise UnsupportedStepError(f"Unsupported step type: {step.step_type}")

    def _capture_artifact(self, page, case_run_id: int) -> BrowserArtifact | None:
        screenshot_bytes = page.screenshot(type="png", full_page=True)
        if not screenshot_bytes:
            return None
        return BrowserArtifact(
            file_name=f"case-run-{case_run_id}.png",
            content_type="image/png",
            content_bytes=screenshot_bytes,
        )

    def _payload_int(self, payload: dict, key: str) -> int:
        value = payload.get(key)
        if isinstance(value, bool) or value is None:
            raise ValueError(f"Step payload `{key}` is required.")
        if isinstance(value, (int, float, Decimal)):
            return int(value)
        raise ValueError(f"Step payload `{key}` must be numeric.")

    def _payload_str(self, payload: dict, key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Step payload `{key}` must be a non-empty string.")
        return value

    def _format_error(self, exc: Exception) -> str:
        message = str(exc).strip()
        if not message:
            return type(exc).__name__
        return f"{type(exc).__name__}: {message.splitlines()[0]}"


def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
    return max(1, int((finished_at - started_at).total_seconds() * 1000))
