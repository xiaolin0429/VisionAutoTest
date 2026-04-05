from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol, Sequence
from urllib.parse import urljoin, urlparse

from app.core.config import get_settings
from app.models import DeviceProfile, utc_now
from app.workers.browser_step_registry import get_step_handler
from app.workers.vision import (
    OcrLocateResult,
    TemplateAssertionContext,
    TemplateLocateResult,
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
                page.goto(
                    base_url, wait_until="load", timeout=self._navigation_timeout_ms
                )

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
                'Playwright is not installed. Run `pip install -e ".[dev]"` and `playwright install chromium`.'
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
        base_url: str,
        step: BrowserStep,
        case_run_id: int,
        template_contexts: dict[int, TemplateAssertionContext],
    ) -> StepExecutionOutcome:
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
        parent_step_no = step.parent_step_no
        if parent_step_no is None:
            return True
        parent_step = next(
            (item for item in steps if item.step_no == parent_step_no), None
        )
        if parent_step is None or parent_step.step_type != "conditional_branch":
            return False
        selected = self._select_matching_branch(
            page,
            payload=parent_step.payload_json or {},
            template_contexts=template_contexts,
        )
        if selected is None:
            return False
        selected_key = selected.get("branch_key")
        if selected_key is None and selected.get("condition") is None:
            selected_key = "else"
        return step.branch_key == selected_key

    def _select_matching_branch(
        self,
        page,
        *,
        payload: dict,
        template_contexts: dict[int, TemplateAssertionContext],
    ) -> dict | None:
        branches = (
            payload.get("branches") if isinstance(payload.get("branches"), list) else []
        )
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            if self._evaluate_branch_condition(
                page,
                condition=branch.get("condition"),
                template_contexts=template_contexts,
            ):
                return branch
        else_branch = payload.get("else_branch")
        if isinstance(else_branch, dict) and else_branch.get("enabled") is True:
            return {
                "branch_key": "else",
                "branch_name": else_branch.get("branch_name") or "默认分支",
                "condition": None,
            }
        return None

    def _evaluate_branch_condition(
        self,
        page,
        *,
        condition: object,
        template_contexts: dict[int, TemplateAssertionContext],
    ) -> bool:
        if not isinstance(condition, dict):
            raise ValueError("conditional_branch requires condition object.")
        condition_type = condition.get("type")
        if condition_type == "selector_exists":
            selector = condition.get("selector")
            if not isinstance(selector, str) or not selector.strip():
                raise ValueError("selector_exists requires selector.")
            return page.locator(selector).count() > 0
        if condition_type == "ocr_text_visible":
            expected_text = condition.get("expected_text")
            if not isinstance(expected_text, str) or not expected_text.strip():
                raise ValueError("ocr_text_visible requires expected_text.")
            screenshot_bytes = page.screenshot(type="png", full_page=False)
            try:
                self._vision_adapter.locate_by_ocr(
                    image_png_bytes=screenshot_bytes,
                    target_text=expected_text.strip(),
                    match_mode=condition.get("match_mode", "contains"),
                    case_sensitive=bool(condition.get("case_sensitive", False)),
                    occurrence=1,
                )
                return True
            except RuntimeError:
                return False
        if condition_type == "template_visible":
            template_id = condition.get("template_id")
            if isinstance(template_id, bool) or not isinstance(template_id, int):
                raise ValueError("template_visible requires template_id.")
            if template_id not in template_contexts:
                raise ValueError("Template condition context is missing.")
            screenshot_bytes = page.screenshot(type="png", full_page=True)
            threshold_override = condition.get("threshold")
            try:
                self._vision_adapter.locate_by_template(
                    context=template_contexts[template_id],
                    actual_png_bytes=screenshot_bytes,
                    threshold_override=float(threshold_override)
                    if isinstance(threshold_override, (int, float, Decimal))
                    else None,
                )
                return True
            except RuntimeError:
                return False
        raise ValueError("conditional_branch condition type is not supported.")

    def _execute_navigate(
        self, page, *, step: BrowserStep, base_url: str, timeout_ms: int
    ) -> StepExecutionOutcome:
        payload = step.payload_json or {}
        url = self._payload_str(payload, "url")
        wait_until = payload.get("wait_until", "load")
        if wait_until not in {"load", "domcontentloaded", "networkidle"}:
            raise ValueError(
                "navigate `wait_until` must be `load`, `domcontentloaded`, or `networkidle`."
            )
        page.goto(
            self._resolve_navigate_url(base_url, url),
            wait_until=wait_until,
            timeout=timeout_ms,
        )
        return StepExecutionOutcome(status="passed", score_value=1.0)

    def _execute_scroll(
        self,
        page,
        *,
        step: BrowserStep,
        timeout_ms: int,
        template_contexts: dict[int, TemplateAssertionContext],
    ) -> StepExecutionOutcome:
        payload = step.payload_json or {}
        target = self._payload_str(payload, "target")
        if target not in {"page", "element"}:
            raise ValueError("scroll `target` must be `page` or `element`.")

        direction = self._payload_str(payload, "direction")
        distance = self._payload_float(payload, "distance")
        if distance <= 0:
            raise ValueError("scroll `distance` must be greater than 0.")
        behavior = payload.get("behavior", "auto")
        if behavior not in {"auto", "smooth"}:
            raise ValueError("scroll `behavior` must be `auto` or `smooth`.")

        delta_x, delta_y = self._scroll_delta(direction, distance)
        if target == "page":
            before = page.evaluate(
                """() => {
                    const root = document.scrollingElement || document.documentElement;
                    return { left: root.scrollLeft, top: root.scrollTop };
                }"""
            )
            page.evaluate(
                """({ left, top, behavior }) => {
                    const root = document.scrollingElement || document.documentElement;
                    root.scrollBy({ left, top, behavior });
                }""",
                {"left": delta_x, "top": delta_y, "behavior": behavior},
            )
            self._settle_scroll(page, behavior)
            after = page.evaluate(
                """() => {
                    const root = document.scrollingElement || document.documentElement;
                    return { left: root.scrollLeft, top: root.scrollTop };
                }"""
            )
            if before == after:
                raise RuntimeError(
                    "Page scroll did not move; ensure the page can scroll in the requested direction."
                )
            return StepExecutionOutcome(status="passed", score_value=1.0)

        if self._uses_visual_locator(payload):
            loc = self._resolve_interaction_target(
                page, payload, template_contexts=template_contexts
            )
            point = self._resolve_visual_anchor_point(payload, loc)
            page.mouse.move(point.x, point.y)
            page.mouse.wheel(delta_x, delta_y)
            self._settle_scroll(page, behavior)
            return StepExecutionOutcome(status="passed", score_value=1.0)

        selector = self._payload_str(payload, "selector")
        locator = page.locator(selector)
        locator.wait_for(state="visible", timeout=timeout_ms)
        before = locator.evaluate(
            "element => ({ left: element.scrollLeft, top: element.scrollTop })"
        )
        locator.evaluate(
            """(element, args) => {
                element.scrollBy({ left: args.left, top: args.top, behavior: args.behavior });
            }""",
            {"left": delta_x, "top": delta_y, "behavior": behavior},
        )
        self._settle_scroll(page, behavior)
        after = locator.evaluate(
            "element => ({ left: element.scrollLeft, top: element.scrollTop })"
        )
        if before == after:
            raise RuntimeError(
                "Element scroll did not move; ensure the target element can scroll in the requested direction."
            )
        return StepExecutionOutcome(status="passed", score_value=1.0)

    def _execute_long_press(
        self,
        page,
        *,
        step: BrowserStep,
        timeout_ms: int,
        template_contexts: dict[int, TemplateAssertionContext],
    ) -> StepExecutionOutcome:
        payload = step.payload_json or {}
        duration_ms = self._payload_int(payload, "duration_ms")
        if duration_ms <= 0:
            raise ValueError("long_press `duration_ms` must be greater than 0.")
        button = payload.get("button", "left")
        if button != "left":
            raise ValueError("long_press `button` currently only supports `left`.")

        if self._uses_visual_locator(payload):
            loc = self._resolve_interaction_target(
                page, payload, template_contexts=template_contexts
            )
            point = self._resolve_visual_anchor_point(payload, loc)
            cx, cy = point.x, point.y
        else:
            selector = self._payload_str(payload, "selector")
            locator = page.locator(selector)
            locator.wait_for(state="visible", timeout=timeout_ms)
            element = locator.element_handle(timeout=timeout_ms)
            if element is None:
                raise RuntimeError("long_press target element was not found.")
            element.scroll_into_view_if_needed(timeout=timeout_ms)
            box = element.bounding_box()
            if box is None or box["width"] <= 0 or box["height"] <= 0:
                raise RuntimeError(
                    "long_press target element has no visible bounding box."
                )
            cx, cy = box["x"] + (box["width"] / 2), box["y"] + (box["height"] / 2)

        page.mouse.move(cx, cy)
        page.mouse.down(button=button)
        page.wait_for_timeout(duration_ms)
        page.mouse.up(button=button)
        return StepExecutionOutcome(status="passed", score_value=1.0)

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

    def _resolve_navigate_url(self, base_url: str, url: str) -> str:
        if url.startswith("/"):
            return urljoin(base_url, url)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(
                "navigate `url` must be an absolute http/https URL or a path starting with `/`."
            )
        return url

    def _scroll_delta(self, direction: str, distance: float) -> tuple[float, float]:
        if direction == "up":
            return 0.0, -distance
        if direction == "down":
            return 0.0, distance
        if direction == "left":
            return -distance, 0.0
        if direction == "right":
            return distance, 0.0
        raise ValueError("scroll `direction` must be `up`, `down`, `left`, or `right`.")

    def _settle_scroll(self, page, behavior: str) -> None:
        page.wait_for_timeout(50)
        if behavior == "smooth":
            page.wait_for_timeout(250)

    def _uses_visual_locator(self, payload: dict) -> bool:
        return payload.get("locator") in {"ocr", "visual"}

    def _is_ocr_locator(self, payload: dict) -> bool:
        return payload.get("locator") == "ocr"

    def _is_visual_template_locator(self, payload: dict) -> bool:
        return payload.get("locator") == "visual"

    def _resolve_interaction_target(
        self,
        page,
        payload: dict,
        *,
        template_contexts: dict[int, TemplateAssertionContext],
    ) -> OcrLocateResult | TemplateLocateResult:
        if self._is_ocr_locator(payload):
            return self._resolve_ocr_target(page, payload)
        if self._is_visual_template_locator(payload):
            return self._resolve_visual_target(
                page, payload, template_contexts=template_contexts
            )
        raise ValueError("Unsupported interaction locator.")

    def _resolve_ocr_target(self, page, payload: dict) -> OcrLocateResult:
        ocr_text = payload.get("ocr_text")
        if not isinstance(ocr_text, str) or not ocr_text.strip():
            raise ValueError("OCR locator requires `ocr_text` in payload.")
        match_mode = payload.get("ocr_match_mode", "contains")
        case_sensitive = payload.get("ocr_case_sensitive", False)
        occurrence = payload.get("ocr_occurrence", 1)
        screenshot_bytes = page.screenshot(type="png", full_page=False)
        return self._vision_adapter.locate_by_ocr(
            image_png_bytes=screenshot_bytes,
            target_text=ocr_text.strip(),
            match_mode=match_mode,
            case_sensitive=bool(case_sensitive),
            occurrence=int(occurrence),
        )

    def _resolve_visual_target(
        self,
        page,
        payload: dict,
        *,
        template_contexts: dict[int, TemplateAssertionContext],
    ) -> TemplateLocateResult:
        template_id = payload.get("template_id")
        if isinstance(template_id, bool) or not isinstance(template_id, int):
            raise ValueError("visual locator requires `template_id` in payload.")
        if template_id not in template_contexts:
            raise ValueError("Visual locator template context is missing.")

        threshold_override = payload.get("threshold")
        if threshold_override is not None:
            threshold_override = self._payload_float(payload, "threshold")

        screenshot_bytes = page.screenshot(type="png", full_page=True)
        return self._vision_adapter.locate_by_template(
            context=template_contexts[template_id],
            actual_png_bytes=screenshot_bytes,
            threshold_override=threshold_override,
        )

    def _resolve_visual_anchor_point(
        self, payload: dict, target: OcrLocateResult | TemplateLocateResult
    ) -> InteractionPoint:
        if isinstance(target, OcrLocateResult):
            return InteractionPoint(x=target.center_x, y=target.center_y)

        anchor_x_ratio = self._optional_ratio(payload, "anchor_x_ratio", default=0.5)
        anchor_y_ratio = self._optional_ratio(payload, "anchor_y_ratio", default=0.5)
        return InteractionPoint(
            x=target.rect_x + (target.rect_width * anchor_x_ratio),
            y=target.rect_y + (target.rect_height * anchor_y_ratio),
        )

    def _input_via_keyboard(
        self,
        page,
        *,
        text: str,
        input_mode: str,
        otp_length: int | None,
        per_char_delay_ms: int,
    ) -> None:
        if input_mode == "fill":
            page.keyboard.type(text)
            return

        if input_mode == "type":
            page.keyboard.type(text, delay=per_char_delay_ms)
            return

        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("input `text` must be a non-empty string.")
        expected_length = otp_length if otp_length is not None else len(normalized_text)
        if len(normalized_text) != expected_length:
            raise ValueError("input `text` length must match `otp_length` in otp mode.")

        for char in normalized_text:
            page.keyboard.insert_text(char)
            page.wait_for_timeout(per_char_delay_ms)

    def _prepare_input_focus(self, page, *, input_mode: str) -> None:
        if input_mode != "otp":
            return

        focused = page.evaluate(
            """() => {
                const inputs = Array.from(document.querySelectorAll('input.base-code-box-input'));
                const firstVisible = inputs.find((item) => {
                    if (!(item instanceof HTMLInputElement)) return false;
                    const rect = item.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0 && !item.disabled;
                });
                if (!(firstVisible instanceof HTMLInputElement)) {
                    return false;
                }
                firstVisible.focus();
                firstVisible.click();
                return document.activeElement === firstVisible;
            }"""
        )
        if focused:
            page.wait_for_timeout(100)

    def _verify_input_applied(
        self,
        page,
        *,
        text: str,
        input_mode: str,
        otp_length: int | None,
    ) -> None:
        if input_mode == "fill":
            return

        if input_mode == "otp":
            expected_length = otp_length if otp_length is not None else len(text)
            otp_state = page.evaluate(
                """() => {
                    const inputs = Array.from(document.querySelectorAll('input.base-code-box-input'));
                    return inputs.map((item) => ({ value: item.value || '' }));
                }"""
            )
            if isinstance(otp_state, list) and otp_state:
                joined = "".join(str(item.get("value", "")) for item in otp_state)
                if len(joined) == expected_length and joined == text:
                    return
                raise RuntimeError(
                    "OTP input did not populate verification boxes with the expected value."
                )

        active_value = page.evaluate(
            """() => {
                const active = document.activeElement;
                if (active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement) {
                    return active.value || '';
                }
                return '';
            }"""
        )
        if active_value != text:
            raise RuntimeError("Keyboard input did not persist the expected value.")

    def _optional_positive_int(self, payload: dict, key: str) -> int | None:
        value = payload.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError(f"Step payload `{key}` must be numeric.")
        parsed = int(value)
        if parsed < 1:
            raise ValueError(f"Step payload `{key}` must be greater than 0.")
        return parsed

    def _optional_non_negative_int(
        self, payload: dict, key: str, *, default: int
    ) -> int:
        value = payload.get(key)
        if value is None:
            return default
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError(f"Step payload `{key}` must be numeric.")
        parsed = int(value)
        if parsed < 0:
            raise ValueError(
                f"Step payload `{key}` must be greater than or equal to 0."
            )
        return parsed

    def _optional_ratio(self, payload: dict, key: str, *, default: float) -> float:
        value = payload.get(key)
        if value is None:
            return default
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError(f"Step payload `{key}` must be numeric.")
        parsed = float(value)
        if parsed < 0 or parsed > 1:
            raise ValueError(f"Step payload `{key}` must be between 0 and 1.")
        return parsed

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
