from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol, Sequence

from app.core.config import get_settings
from app.models import DeviceProfile, utc_now
from app.workers.vision import (
    TemplateAssertionContext,
    VisionArtifact,
    VisionAssertionOutcome,
    build_vision_assertion_adapter,
)


class UnsupportedStepError(Exception):
    pass


@dataclass(slots=True)
class BrowserArtifact:
    file_name: str
    content_type: str
    content_bytes: bytes
    artifact_type: str = "run_screenshot"


@dataclass(slots=True)
class BrowserStepResult:
    step_no: int
    step_type: str
    status: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    error_message: str | None = None
    score_value: float | None = None
    expected_media_object_id: int | None = None
    actual_artifact: VisionArtifact | None = None
    diff_artifact: VisionArtifact | None = None


@dataclass(slots=True)
class CaseExecutionResult:
    status: str
    step_results: list[BrowserStepResult]
    failure_reason_code: str | None = None
    failure_summary: str | None = None
    artifact: BrowserArtifact | None = None


@dataclass(slots=True)
class StepExecutionOutcome:
    status: str
    score_value: float | None = None
    error_message: str | None = None
    expected_media_object_id: int | None = None
    actual_artifact: VisionArtifact | None = None
    diff_artifact: VisionArtifact | None = None


class BrowserStep(Protocol):
    step_no: int
    step_type: str
    payload_json: dict
    timeout_ms: int
    template_id: int | None


class BrowserExecutionAdapter(Protocol):
    def execute_case(
        self,
        *,
        base_url: str,
        case_run_id: int,
        device_profile: DeviceProfile | None,
        steps: Sequence[BrowserStep],
        template_contexts: dict[int, TemplateAssertionContext],
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
        self._vision_adapter = build_vision_assertion_adapter()

    def execute_case(
        self,
        *,
        base_url: str,
        case_run_id: int,
        device_profile: DeviceProfile | None,
        steps: Sequence[BrowserStep],
        template_contexts: dict[int, TemplateAssertionContext],
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
                        outcome = self._execute_step(
                            page,
                            step=step,
                            case_run_id=case_run_id,
                            template_contexts=template_contexts,
                        )
                    except UnsupportedStepError as exc:
                        outcome = StepExecutionOutcome(status="error", error_message=self._format_error(exc))
                        failure_reason_code = "STEP_NOT_SUPPORTED"
                        failure_summary = outcome.error_message
                    except ValueError as exc:
                        outcome = StepExecutionOutcome(status="error", error_message=self._format_error(exc))
                        failure_reason_code = "STEP_CONFIGURATION_INVALID"
                        failure_summary = outcome.error_message
                    except playwright_timeout_error as exc:
                        outcome = StepExecutionOutcome(status="error", error_message=self._format_error(exc))
                        failure_reason_code = "STEP_EXECUTION_TIMEOUT"
                        failure_summary = outcome.error_message
                    except Exception as exc:  # noqa: BLE001
                        outcome = StepExecutionOutcome(status="error", error_message=self._format_error(exc))
                        failure_reason_code = "STEP_EXECUTION_ERROR"
                        failure_summary = outcome.error_message

                    finished_at = utc_now()
                    step_results.append(
                        BrowserStepResult(
                            step_no=step.step_no,
                            step_type=step.step_type,
                            status=outcome.status,
                            started_at=started_at,
                            finished_at=finished_at,
                            duration_ms=_duration_ms(started_at, finished_at),
                            error_message=outcome.error_message,
                            score_value=outcome.score_value,
                            expected_media_object_id=outcome.expected_media_object_id,
                            actual_artifact=outcome.actual_artifact,
                            diff_artifact=outcome.diff_artifact,
                        )
                    )

                    if outcome.status == "failed":
                        failure_reason_code = self._failure_code_for_assertion(step.step_type)
                        failure_summary = outcome.error_message or f"{step.step_type} failed."
                        break
                    if outcome.status == "error":
                        failure_reason_code = failure_reason_code or "STEP_EXECUTION_ERROR"
                        failure_summary = failure_summary or outcome.error_message
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

        status = "passed"
        if any(item.status == "error" for item in step_results):
            status = "error"
        elif any(item.status == "failed" for item in step_results):
            status = "failed"

        if artifact is None and status == "passed":
            failure_reason_code = "SCREENSHOT_CAPTURE_FAILED"
            failure_summary = "Browser execution completed without screenshot artifact."
            status = "error"
            if step_results:
                step_results[-1].status = "error"
                step_results[-1].error_message = failure_summary
                step_results[-1].score_value = None

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

    def _execute_step(
        self,
        page,
        *,
        step: BrowserStep,
        case_run_id: int,
        template_contexts: dict[int, TemplateAssertionContext],
    ) -> StepExecutionOutcome:
        payload = step.payload_json or {}
        timeout_ms = int(step.timeout_ms)
        if step.step_type == "wait":
            wait_ms = self._payload_int(payload, "ms")
            if wait_ms < 0:
                raise ValueError("wait step `ms` must be greater than or equal to 0.")
            page.wait_for_timeout(wait_ms)
            return StepExecutionOutcome(status="passed", score_value=1.0)
        if step.step_type == "click":
            selector = self._payload_str(payload, "selector")
            page.locator(selector).click(timeout=timeout_ms)
            return StepExecutionOutcome(status="passed", score_value=1.0)
        if step.step_type == "input":
            selector = self._payload_str(payload, "selector")
            text = self._payload_str(payload, "text")
            page.locator(selector).fill(text, timeout=timeout_ms)
            return StepExecutionOutcome(status="passed", score_value=1.0)
        if step.step_type == "template_assert":
            return self._execute_template_assert(
                page,
                step=step,
                case_run_id=case_run_id,
                template_contexts=template_contexts,
            )
        if step.step_type == "ocr_assert":
            return self._execute_ocr_assert(page, step=step, case_run_id=case_run_id, timeout_ms=timeout_ms)
        raise UnsupportedStepError(f"Unsupported step type: {step.step_type}")

    def _execute_template_assert(
        self,
        page,
        *,
        step: BrowserStep,
        case_run_id: int,
        template_contexts: dict[int, TemplateAssertionContext],
    ) -> StepExecutionOutcome:
        if step.template_id is None or step.template_id not in template_contexts:
            raise ValueError("Template assertion context is missing.")
        payload = step.payload_json or {}
        threshold_override = payload.get("threshold")
        if threshold_override is not None:
            threshold_override = self._payload_float(payload, "threshold")
        screenshot_bytes = page.screenshot(type="png", full_page=True)
        outcome = self._vision_adapter.assert_template(
            context=template_contexts[step.template_id],
            actual_png_bytes=screenshot_bytes,
            actual_file_name=f"case-run-{case_run_id}-step-{step.step_no}-actual.png",
            threshold_override=threshold_override,
        )
        return StepExecutionOutcome(
            status=outcome.status,
            score_value=outcome.score_value,
            error_message=outcome.error_message,
            expected_media_object_id=outcome.expected_media_object_id,
            actual_artifact=outcome.actual_artifact,
            diff_artifact=outcome.diff_artifact,
        )

    def _execute_ocr_assert(self, page, *, step: BrowserStep, case_run_id: int, timeout_ms: int) -> StepExecutionOutcome:
        payload = step.payload_json or {}
        selector = self._payload_str(payload, "selector")
        expected_text = self._payload_str(payload, "expected_text")
        match_mode = payload.get("match_mode", "contains")
        if match_mode not in {"exact", "contains"}:
            raise ValueError("ocr_assert `match_mode` must be either `exact` or `contains`.")
        case_sensitive = payload.get("case_sensitive", False)
        if not isinstance(case_sensitive, bool):
            raise ValueError("ocr_assert `case_sensitive` must be boolean.")
        image_bytes = page.locator(selector).screenshot(type="png", timeout=timeout_ms)
        outcome = self._vision_adapter.assert_ocr(
            image_png_bytes=image_bytes,
            image_file_name=f"case-run-{case_run_id}-step-{step.step_no}-ocr.png",
            expected_text=expected_text,
            match_mode=match_mode,
            case_sensitive=case_sensitive,
        )
        return StepExecutionOutcome(
            status=outcome.status,
            score_value=outcome.score_value,
            error_message=outcome.error_message,
            actual_artifact=outcome.actual_artifact,
        )

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

    def _payload_float(self, payload: dict, key: str) -> float:
        value = payload.get(key)
        if isinstance(value, bool) or value is None:
            raise ValueError(f"Step payload `{key}` is required.")
        if isinstance(value, (int, float, Decimal)):
            return float(value)
        raise ValueError(f"Step payload `{key}` must be numeric.")

    def _payload_str(self, payload: dict, key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Step payload `{key}` must be a non-empty string.")
        return value

    def _failure_code_for_assertion(self, step_type: str) -> str:
        if step_type == "template_assert":
            return "TEMPLATE_ASSERTION_FAILED"
        if step_type == "ocr_assert":
            return "OCR_ASSERTION_FAILED"
        return "ASSERTION_FAILED"

    def _format_error(self, exc: Exception) -> str:
        message = str(exc).strip()
        if not message:
            return type(exc).__name__
        return f"{type(exc).__name__}: {message.splitlines()[0]}"


def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
    return max(1, int((finished_at - started_at).total_seconds() * 1000))
