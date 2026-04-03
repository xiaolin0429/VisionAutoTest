from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from tests.support.constants import (
    ACTUAL_ARTIFACT_BYTES,
    BROWSER_STEPS_HTML,
    DIFF_ARTIFACT_BYTES,
    OCR_ARTIFACT_BYTES,
    TINY_PNG_BYTES,
)


def _install_fake_browser_adapter(monkeypatch) -> None:
    from app.workers.browser import (
        BrowserArtifact,
        BrowserStepResult,
        CaseExecutionResult,
    )

    class FakeBrowserAdapter:
        supported_step_types = {
            "wait",
            "click",
            "input",
            "navigate",
            "scroll",
            "long_press",
        }

        def execute_case(
            self,
            *,
            base_url: str,
            case_run_id: int,
            device_profile,
            steps,
            template_contexts,
        ):
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

    monkeypatch.setattr(
        "app.workers.execution.build_browser_execution_adapter",
        lambda: FakeBrowserAdapter(),
    )


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


def _install_visual_browser_adapter(
    monkeypatch, *, template_status: str = "passed", ocr_status: str = "passed"
) -> None:
    from app.workers.browser import (
        BrowserArtifact,
        BrowserStepResult,
        CaseExecutionResult,
    )
    from app.workers.vision import VisionArtifact

    class FakeVisualBrowserAdapter:
        def execute_case(
            self,
            *,
            base_url: str,
            case_run_id: int,
            device_profile,
            steps,
            template_contexts,
        ):
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

    monkeypatch.setattr(
        "app.workers.execution.build_browser_execution_adapter",
        lambda: FakeVisualBrowserAdapter(),
    )


def _install_noop_dispatcher(monkeypatch) -> None:
    class NoopDispatcher:
        def dispatch_test_run(self, test_run_id: int) -> None:
            _ = test_run_id

    monkeypatch.setattr(
        "app.api.v1.executions.get_test_run_dispatcher",
        lambda _background_tasks: NoopDispatcher(),
    )


def _install_counting_browser_adapter(
    monkeypatch, *, call_counter: dict[str, int]
) -> None:
    from app.workers.browser import (
        BrowserArtifact,
        BrowserStepResult,
        CaseExecutionResult,
    )

    class CountingBrowserAdapter:
        supported_step_types = {
            "wait",
            "click",
            "input",
            "navigate",
            "scroll",
            "long_press",
        }

        def execute_case(
            self,
            *,
            base_url: str,
            case_run_id: int,
            device_profile,
            steps,
            template_contexts,
        ):
            _ = (base_url, case_run_id, device_profile, template_contexts)
            call_counter["execute_case"] = call_counter.get("execute_case", 0) + 1
            step_results: list[BrowserStepResult] = []
            for step in steps:
                started_at = datetime.now(timezone.utc)
                finished_at = datetime.now(timezone.utc)
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

    monkeypatch.setattr(
        "app.workers.execution.build_browser_execution_adapter",
        lambda: CountingBrowserAdapter(),
    )


def _install_template_workbench_adapter(
    monkeypatch, *, analyses: list[dict] | None = None, ocr_error: str | None = None
) -> None:
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
                        "polygon_points": [
                            {"x": 20, "y": 10},
                            {"x": 90, "y": 10},
                            {"x": 90, "y": 32},
                            {"x": 20, "y": 32},
                        ],
                        "pixel_rect": {"x": 20, "y": 10, "width": 70, "height": 22},
                        "ratio_rect": {
                            "x_ratio": 0.1,
                            "y_ratio": 0.1,
                            "width_ratio": 0.35,
                            "height_ratio": 0.22,
                        },
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

    monkeypatch.setattr(
        "app.services.assets.build_vision_assertion_adapter",
        lambda: FakeVisionAdapter(),
    )
