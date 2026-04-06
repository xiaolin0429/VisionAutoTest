from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence

from app.core.config import get_settings
from app.models import DeviceProfile, utc_now
from app.workers import browser_branching, browser_locators, browser_payloads
from app.workers.browser_step_registry import get_step_handler
from app.workers.vision import (
    TemplateAssertionContext,
    VisionArtifact,
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
    parent_step_no: int | None = None
    branch_key: str | None = None
    branch_name: str | None = None
    branch_step_index: int | None = None


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


@dataclass(slots=True)
class InteractionPoint:
    x: float
    y: float


class BrowserStep(Protocol):
    step_no: int
    step_type: str
    payload_json: dict
    timeout_ms: int
    template_id: int | None
    parent_step_no: int | None
    branch_key: str | None
    branch_name: str | None
    branch_step_index: int | None


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
    """Build the browser execution adapter from runtime settings.

    Returns:
        A Playwright-backed adapter configured with the current headless and timeout settings.
    """
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
        self._interaction_point_cls = InteractionPoint

    def execute_case(
        self,
        *,
        base_url: str,
        case_run_id: int,
        device_profile: DeviceProfile | None,
        steps: Sequence[BrowserStep],
        template_contexts: dict[int, TemplateAssertionContext],
    ) -> CaseExecutionResult:
        """Execute one case end-to-end inside a fresh browser context.

        Args:
            base_url: Entry URL used to open the target application before step execution.
            case_run_id: Case run id used when naming final screenshot artifacts.
            device_profile: Optional viewport and user-agent profile for the browser context.
            steps: Flattened step sequence to execute in order.
            template_contexts: Template lookup data required by visual assertions and branches.

        Returns:
            The terminal case result including per-step outcomes, representative failure reason,
            and the final screenshot artifact when capture succeeds.
        """
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
                page.goto(
                    base_url, wait_until="load", timeout=self._navigation_timeout_ms
                )

                # Steps are executed in order, but branch child steps are only materialized
                # at runtime after the parent conditional evaluates against the current page.
                for step in steps:
                    if step.parent_step_no is not None:
                        if not self._should_execute_branch_step(
                            page,
                            step=step,
                            steps=steps,
                            template_contexts=template_contexts,
                        ):
                            continue
                    started_at = utc_now()
                    try:
                        outcome = self._execute_step(
                            page,
                            base_url=base_url,
                            step=step,
                            case_run_id=case_run_id,
                            template_contexts=template_contexts,
                        )
                    except UnsupportedStepError as exc:
                        outcome = StepExecutionOutcome(
                            status="error", error_message=self._format_error(exc)
                        )
                        failure_reason_code = "STEP_NOT_SUPPORTED"
                        failure_summary = outcome.error_message
                    except ValueError as exc:
                        outcome = StepExecutionOutcome(
                            status="error", error_message=self._format_error(exc)
                        )
                        failure_reason_code = "STEP_CONFIGURATION_INVALID"
                        failure_summary = outcome.error_message
                    except playwright_timeout_error as exc:
                        outcome = StepExecutionOutcome(
                            status="error", error_message=self._format_error(exc)
                        )
                        failure_reason_code = "STEP_EXECUTION_TIMEOUT"
                        failure_summary = outcome.error_message
                    except Exception as exc:  # noqa: BLE001
                        outcome = StepExecutionOutcome(
                            status="error", error_message=self._format_error(exc)
                        )
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
                            parent_step_no=step.parent_step_no,
                            branch_key=step.branch_key,
                            branch_name=step.branch_name,
                            branch_step_index=step.branch_step_index,
                        )
                    )
                    if outcome.status == "failed":
                        # Assertion failures stop the case as a business failure, which is
                        # distinct from runtime errors such as invalid payloads or timeouts.
                        failure_reason_code = self._failure_code_for_assertion(
                            step.step_type
                        )
                        failure_summary = (
                            outcome.error_message or f"{step.step_type} failed."
                        )
                        break
                    if outcome.status == "error":
                        failure_reason_code = (
                            failure_reason_code or "STEP_EXECUTION_ERROR"
                        )
                        failure_summary = failure_summary or outcome.error_message
                        break

                # A case screenshot is captured even after step failure so reports retain a
                # final visual artifact whenever the browser context is still available.
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

        # Screenshot capture is treated as part of the execution contract for successful runs.
        # If the case appears passed but no artifact exists, the run is downgraded to error.
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
                'Playwright is not installed. Run `pip install -e ".[dev]"` and `playwright install chromium`.'
            ) from exc
        return sync_playwright, PlaywrightTimeoutError

    def _context_kwargs(self, device_profile: DeviceProfile | None) -> dict:
        """Translate a stored device profile into Playwright context kwargs.

        Args:
            device_profile: Optional persisted device settings for viewport and user agent.

        Returns:
            Keyword arguments passed into ``browser.new_context``.
        """
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
        base_url: str,
        step: BrowserStep,
        case_run_id: int,
        template_contexts: dict[int, TemplateAssertionContext],
    ) -> StepExecutionOutcome:
        """Dispatch a single step to the registered browser step handler.

        Args:
            page: Active Playwright page for the current case.
            base_url: Base URL used by navigate-like handlers when resolving relative targets.
            step: Current flattened step definition.
            case_run_id: Case run id used by handlers that emit artifacts.
            template_contexts: Template lookup data shared by visual handlers.

        Returns:
            The normalized step execution outcome returned by the handler.

        Raises:
            UnsupportedStepError: If no handler is registered for the step type.
        """
        payload = step.payload_json or {}
        timeout_ms = int(step.timeout_ms)
        handler = get_step_handler(step.step_type)
        if handler is not None:
            return handler(
                self,
                page,
                base_url=base_url,
                step=step,
                case_run_id=case_run_id,
                timeout_ms=timeout_ms,
                template_contexts=template_contexts,
            )
        raise UnsupportedStepError(f"Unsupported step type: {step.step_type}")

    def _should_execute_branch_step(
        self,
        page,
        *,
        step: BrowserStep,
        steps: Sequence[BrowserStep],
        template_contexts: dict[int, TemplateAssertionContext],
    ) -> bool:
        """Decide whether a branch child step belongs to the selected branch.

        Args:
            page: Active Playwright page used to evaluate the parent branch condition.
            step: Candidate child step under a ``conditional_branch`` parent.
            steps: Full flattened step sequence so the parent step can be looked up.
            template_contexts: Template lookup data needed by visual branch conditions.

        Returns:
            ``True`` when the current child step belongs to the selected branch; otherwise ``False``.
        """
        return browser_branching.should_execute_branch_step(
            self,
            page,
            step=step,
            steps=steps,
            template_contexts=template_contexts,
        )

    def _select_matching_branch(
        self,
        page,
        *,
        payload: dict,
        template_contexts: dict[int, TemplateAssertionContext],
    ) -> dict | None:
        return browser_branching.select_matching_branch(
            self,
            page,
            payload=payload,
            template_contexts=template_contexts,
        )

    def _evaluate_branch_condition(
        self,
        page,
        *,
        condition: object,
        template_contexts: dict[int, TemplateAssertionContext],
    ) -> bool:
        return browser_branching.evaluate_branch_condition(
            self,
            page,
            condition=condition,
            template_contexts=template_contexts,
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
        return browser_payloads.payload_int(payload, key)

    def _payload_float(self, payload: dict, key: str) -> float:
        return browser_payloads.payload_float(payload, key)

    def _payload_str(self, payload: dict, key: str) -> str:
        return browser_payloads.payload_str(payload, key)

    def _resolve_navigate_url(self, base_url: str, url: str) -> str:
        return browser_payloads.resolve_navigate_url(base_url, url)

    def _scroll_delta(self, direction: str, distance: float) -> tuple[float, float]:
        return browser_payloads.scroll_delta(direction, distance)

    def _settle_scroll(self, page, behavior: str) -> None:
        browser_payloads.settle_scroll(page, behavior)

    def _uses_visual_locator(self, payload: dict) -> bool:
        return browser_locators.uses_visual_locator(payload)

    def _is_ocr_locator(self, payload: dict) -> bool:
        return browser_locators.is_ocr_locator(payload)

    def _is_visual_template_locator(self, payload: dict) -> bool:
        return browser_locators.is_visual_template_locator(payload)

    def _resolve_interaction_target(
        self,
        page,
        payload: dict,
        *,
        template_contexts: dict[int, TemplateAssertionContext],
    ):
        return browser_locators.resolve_interaction_target(
            self,
            page,
            payload,
            template_contexts=template_contexts,
        )

    def _resolve_ocr_target(self, page, payload: dict):
        return browser_locators.resolve_ocr_target(self, page, payload)

    def _resolve_visual_target(
        self,
        page,
        payload: dict,
        *,
        template_contexts: dict[int, TemplateAssertionContext],
    ):
        return browser_locators.resolve_visual_target(
            self,
            page,
            payload,
            template_contexts=template_contexts,
        )

    def _resolve_visual_anchor_point(self, payload: dict, target) -> InteractionPoint:
        return browser_locators.resolve_visual_anchor_point(self, payload, target)

    def _input_via_keyboard(
        self,
        page,
        *,
        text: str,
        input_mode: str,
        otp_length: int | None,
        per_char_delay_ms: int,
    ) -> None:
        browser_payloads.input_via_keyboard(
            page,
            text=text,
            input_mode=input_mode,
            otp_length=otp_length,
            per_char_delay_ms=per_char_delay_ms,
        )

    def _prepare_input_focus(self, page, *, input_mode: str) -> None:
        browser_payloads.prepare_input_focus(page, input_mode=input_mode)

    def _verify_input_applied(
        self,
        page,
        *,
        text: str,
        input_mode: str,
        otp_length: int | None,
    ) -> None:
        browser_payloads.verify_input_applied(
            page,
            text=text,
            input_mode=input_mode,
            otp_length=otp_length,
        )

    def _optional_positive_int(self, payload: dict, key: str) -> int | None:
        return browser_payloads.optional_positive_int(payload, key)

    def _optional_non_negative_int(
        self, payload: dict, key: str, *, default: int
    ) -> int:
        return browser_payloads.optional_non_negative_int(payload, key, default=default)

    def _optional_ratio(self, payload: dict, key: str, *, default: float) -> float:
        return browser_payloads.optional_ratio(payload, key, default=default)

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
