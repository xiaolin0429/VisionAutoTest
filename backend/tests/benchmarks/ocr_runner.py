from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2

from app.workers.ocr_engine import OcrEnginePool, OcrRecognitionPipeline
from app.workers.ocr_page import build_ocr_page_snapshot_from_analysis
from app.workers.ocr_session import PageOcrSession
from app.workers.ocr_targeting import OcrTargetingError, resolve_ocr_target
from app.workers.ocr_types import OcrErrorCode, OcrTargetResolution, OcrTargetSpec
from app.workers.vision import DefaultVisionAssertionAdapter
from tests.benchmarks.ocr_metrics import (
    CharacterErrorCounts,
    DetectionCounts,
    Rect,
    analysis_detections,
    character_error_counts,
    detection_counts,
    manifest_detections,
    percentile,
    ratio,
    rounded_metric,
    to_metric_dict,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = (
    BACKEND_ROOT / "tests" / "fixtures" / "ocr_benchmark" / "v1"
)
MANIFEST_PATH = CORPUS_ROOT / "manifest.json"
PERFORMANCE_PAGE_PATH = CORPUS_ROOT / "performance_page.html"
E2E_PAGE_PATH = CORPUS_ROOT / "e2e_page.html"
DEFAULT_CHROME = Path(
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)
E2E_CONFIGURATIONS: tuple[tuple[str, tuple[int, int], int], ...] = (
    ("desktop-dpr1", (900, 900), 1),
    ("desktop-dpr2", (900, 900), 2),
    ("mobile-dpr1", (390, 844), 1),
    ("mobile-dpr2", (390, 844), 2),
)


class BenchmarkThresholdError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _BenchmarkBrowserStep:
    step_no: int
    step_type: str
    payload_json: dict[str, object]
    timeout_ms: int = 15000
    template_id: int | None = None
    parent_step_no: int | None = None
    branch_key: str | None = None
    branch_name: str | None = None
    branch_step_index: int | None = None


def load_manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def build_pipeline(
    *,
    manifest: Mapping[str, object],
    model_root: Path,
    allow_model_download: bool,
    preprocessing_profile: str,
    max_preprocess_variants: int,
    minimum_confidence: float,
) -> OcrRecognitionPipeline:
    coverage = manifest["coverage"]
    if not isinstance(coverage, Mapping):
        raise ValueError("Benchmark manifest coverage must be an object.")
    raw_profiles = coverage["language_profiles"]
    if not isinstance(raw_profiles, Sequence):
        raise ValueError("Benchmark language_profiles must be an array.")
    profiles = tuple(str(profile) for profile in raw_profiles)
    return OcrRecognitionPipeline(
        engine_pool=OcrEnginePool(
            allowed_language_profiles=profiles,  # type: ignore[arg-type]
            model_root=model_root,
            allow_model_download=allow_model_download,
            cache_size=len(profiles),
        ),
        preprocessing_profile=preprocessing_profile,  # type: ignore[arg-type]
        max_preprocess_variants=max_preprocess_variants,
        minimum_confidence=minimum_confidence,
    )


def prewarm_models(
    pipeline: OcrRecognitionPipeline,
    *,
    manifest: Mapping[str, object],
) -> dict[str, str | None]:
    coverage = manifest["coverage"]
    assert isinstance(coverage, Mapping)
    profiles = tuple(str(item) for item in coverage["language_profiles"])
    return dict(
        pipeline.engine_pool.warmup(  # type: ignore[arg-type]
            profiles,
            strict=True,
        )
    )


def run_accuracy_benchmark(
    pipeline: OcrRecognitionPipeline,
    *,
    manifest: Mapping[str, object],
) -> dict[str, object]:
    clear_detection = DetectionCounts(0, 0, 0)
    clear_character = CharacterErrorCounts(0, 0)
    disturbed_successes = 0
    disturbed_attempts = 0
    unique_resolution_successes = 0
    unique_resolution_attempts = 0
    wrong_operations = 0
    ambiguity_rejections = 0
    ambiguity_attempts = 0
    fixture_results: list[dict[str, object]] = []

    raw_fixtures = manifest["fixtures"]
    if not isinstance(raw_fixtures, Sequence):
        raise ValueError("Benchmark fixtures must be an array.")
    for raw_fixture in raw_fixtures:
        if not isinstance(raw_fixture, Mapping):
            raise ValueError("Benchmark fixture must be an object.")
        fixture = raw_fixture
        image_path = CORPUS_ROOT / str(fixture["file"])
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"Unable to decode benchmark fixture: {image_path}")
        language_profile = str(fixture["language_profile"])
        analysis = pipeline.analyze(
            image=image,
            language_profile=language_profile,  # type: ignore[arg-type]
        )
        predicted = analysis_detections(analysis)

        fixture_detection = DetectionCounts(0, 0, 0)
        fixture_character = CharacterErrorCounts(0, 0)
        if fixture["quality"] == "clear":
            fixture_detection = detection_counts(
                manifest_detections(fixture),
                predicted,
            )
            fixture_character = character_error_counts(
                manifest_detections(fixture, include_cer=True),
                predicted,
            )
            clear_detection += fixture_detection
            clear_character += fixture_character

        snapshot = build_ocr_page_snapshot_from_analysis(
            image_png_bytes=image_path.read_bytes(),
            analysis=analysis,
            viewport_width_css=int(fixture["viewport_css"][0]),  # type: ignore[index]
            viewport_height_css=int(fixture["viewport_css"][1]),  # type: ignore[index]
            device_scale_factor=float(fixture["device_scale_factor"]),
        )
        unique_results = _evaluate_unique_targets(
            snapshot,
            fixture=fixture,
            language_profile=language_profile,
        )
        unique_resolution_attempts += unique_results["attempts"]
        unique_resolution_successes += unique_results["successes"]
        wrong_operations += unique_results["wrong_operations"]
        if fixture["quality"] == "disturbed":
            disturbed_attempts += unique_results["attempts"]
            disturbed_successes += unique_results["successes"]

        ambiguity_results = _evaluate_ambiguity_groups(
            snapshot,
            fixture=fixture,
            language_profile=language_profile,
        )
        ambiguity_attempts += ambiguity_results["attempts"]
        ambiguity_rejections += ambiguity_results["rejections"]

        fixture_results.append(
            {
                "fixture_id": fixture["id"],
                "language_profile": language_profile,
                "quality": fixture["quality"],
                "analysis_elapsed_ms": round(
                    float(analysis["elapsed_ms"]),
                    3,
                ),
                "predicted_block_count": len(predicted),
                "detection": {
                    "true_positive": fixture_detection.true_positive,
                    "false_positive": fixture_detection.false_positive,
                    "false_negative": fixture_detection.false_negative,
                    "f1": rounded_metric(fixture_detection.f1),
                },
                "recognition": {
                    "edit_distance": fixture_character.edit_distance,
                    "character_count": fixture_character.character_count,
                    "cer": rounded_metric(fixture_character.cer),
                },
                "targeting": unique_results,
                "ambiguity": ambiguity_results,
            }
        )

    summary = to_metric_dict(clear_detection, clear_character)
    summary.update(
        {
            "targeting": {
                "disturbed_successes": disturbed_successes,
                "disturbed_attempts": disturbed_attempts,
                "disturbed_success_rate": rounded_metric(
                    ratio(disturbed_successes, disturbed_attempts)
                ),
                "unique_successes": unique_resolution_successes,
                "unique_attempts": unique_resolution_attempts,
                "unique_success_rate": rounded_metric(
                    ratio(
                        unique_resolution_successes,
                        unique_resolution_attempts,
                    )
                ),
                "wrong_operations": wrong_operations,
                "wrong_operation_rate": rounded_metric(
                    ratio(wrong_operations, unique_resolution_attempts)
                ),
            },
            "ambiguity": {
                "rejections": ambiguity_rejections,
                "attempts": ambiguity_attempts,
                "rejection_rate": rounded_metric(
                    ratio(ambiguity_rejections, ambiguity_attempts)
                ),
            },
            "fixtures": fixture_results,
        }
    )
    return summary


def _evaluate_unique_targets(
    snapshot: Any,
    *,
    fixture: Mapping[str, object],
    language_profile: str,
) -> dict[str, Any]:
    raw_annotations = fixture["annotations"]
    assert isinstance(raw_annotations, Sequence)
    successes = 0
    wrong_operations = 0
    failures: list[dict[str, object]] = []
    attempts = 0
    for raw_annotation in raw_annotations:
        assert isinstance(raw_annotation, Mapping)
        if raw_annotation["target"] != "unique":
            continue
        attempts += 1
        target = OcrTargetSpec(
            text=str(raw_annotation["text"]),
            match_mode=str(raw_annotation["match_mode"]),  # type: ignore[arg-type]
            language=language_profile,  # type: ignore[arg-type]
            min_confidence=0.50,
            min_score=0.50,
            ambiguity_margin=0.05,
            action_point=str(raw_annotation["action_point"]),  # type: ignore[arg-type]
        )
        try:
            resolution = resolve_ocr_target(snapshot, target)
        except OcrTargetingError as exc:
            failures.append(
                {
                    "annotation_id": raw_annotation["id"],
                    "expected_text": raw_annotation["text"],
                    "error_code": exc.code.value,
                    "reason": exc.resolution.error_message,
                }
            )
            continue
        point = _resolution_action_point(resolution)
        raw_expected_rect = raw_annotation["action_rect_css"]
        assert isinstance(raw_expected_rect, Mapping)
        expected_rect = Rect.from_mapping(raw_expected_rect)
        if point is None:
            failures.append(
                {
                    "annotation_id": raw_annotation["id"],
                    "expected_text": raw_annotation["text"],
                    "error_code": "NO_ACTION_POINT",
                }
            )
            continue
        if expected_rect.contains(point, tolerance=3.0):
            successes += 1
        else:
            wrong_operations += 1
            failures.append(
                {
                    "annotation_id": raw_annotation["id"],
                    "expected_text": raw_annotation["text"],
                    "error_code": "WRONG_ACTION_POINT",
                    "actual_point": [round(point[0], 3), round(point[1], 3)],
                    "expected_rect": {
                        "x": expected_rect.x,
                        "y": expected_rect.y,
                        "width": expected_rect.width,
                        "height": expected_rect.height,
                    },
                }
            )
    return {
        "successes": successes,
        "attempts": attempts,
        "success_rate": rounded_metric(ratio(successes, attempts)),
        "wrong_operations": wrong_operations,
        "wrong_operation_rate": rounded_metric(
            ratio(wrong_operations, attempts)
        ),
        "failures": failures,
    }


def _evaluate_ambiguity_groups(
    snapshot: Any,
    *,
    fixture: Mapping[str, object],
    language_profile: str,
) -> dict[str, Any]:
    raw_annotations = fixture["annotations"]
    assert isinstance(raw_annotations, Sequence)
    groups: dict[str, Mapping[str, object]] = {}
    for raw_annotation in raw_annotations:
        assert isinstance(raw_annotation, Mapping)
        group = raw_annotation.get("ambiguity_group")
        if group is not None:
            groups.setdefault(str(group), raw_annotation)

    rejections = 0
    failures: list[dict[str, object]] = []
    for group, annotation in groups.items():
        target = OcrTargetSpec(
            text=str(annotation["text"]),
            match_mode="exact",
            language=language_profile,  # type: ignore[arg-type]
            min_confidence=0.50,
            min_score=0.50,
            ambiguity_margin=0.10,
        )
        try:
            resolve_ocr_target(snapshot, target)
        except OcrTargetingError as exc:
            if exc.code == OcrErrorCode.OCR_TARGET_AMBIGUOUS:
                rejections += 1
            else:
                failures.append(
                    {
                        "group": group,
                        "error_code": exc.code.value,
                        "reason": exc.resolution.error_message,
                    }
                )
        else:
            failures.append(
                {
                    "group": group,
                    "error_code": "UNSAFE_RESOLUTION",
                }
            )
    attempts = len(groups)
    return {
        "rejections": rejections,
        "attempts": attempts,
        "rejection_rate": rounded_metric(ratio(rejections, attempts)),
        "failures": failures,
    }


def _resolution_action_point(
    resolution: OcrTargetResolution,
) -> tuple[float, float] | None:
    selected = resolution.selected_candidate
    if selected is None:
        return None
    if resolution.target.action_point == "associated_control":
        rect = selected.element.associated_control_rect
    else:
        rect = selected.element.coordinates.viewport_css_rect
    if rect is None:
        return None
    return (rect.x + rect.width / 2.0, rect.y + rect.height / 2.0)


def run_performance_benchmark(
    pipeline: OcrRecognitionPipeline,
    *,
    chrome_executable: Path,
    iterations: int,
    preprocessing_profile: str,
) -> dict[str, object]:
    if iterations < 2:
        raise ValueError("Performance benchmark requires at least two iterations.")
    if not chrome_executable.is_file():
        raise RuntimeError(f"Chrome executable is unavailable: {chrome_executable}")

    from playwright.sync_api import sync_playwright

    analyzer = DefaultVisionAssertionAdapter(ocr_pipeline=pipeline)
    viewport_durations: list[float] = []
    page_durations: list[float] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=str(chrome_executable),
        )
        try:
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
                locale="en-US",
                timezone_id="UTC",
            )
            try:
                page = context.new_page()
                page.goto(
                    (
                        f"{(CORPUS_ROOT / 'corpus.html').as_uri()}"
                        "?scene=clear_en_dark"
                    ),
                    wait_until="load",
                )
                page.evaluate("() => document.fonts.ready")
                _recognize_viewport_once(
                    page,
                    analyzer=analyzer,
                    preprocessing_profile=preprocessing_profile,
                )
                for _ in range(iterations):
                    started_at = time.perf_counter()
                    _recognize_viewport_once(
                        page,
                        analyzer=analyzer,
                        preprocessing_profile=preprocessing_profile,
                    )
                    viewport_durations.append(
                        (time.perf_counter() - started_at) * 1000.0
                    )

                page.goto(PERFORMANCE_PAGE_PATH.as_uri(), wait_until="load")
                page.evaluate("() => document.fonts.ready")
                _scan_three_viewport_page_once(
                    page,
                    analyzer=analyzer,
                    preprocessing_profile=preprocessing_profile,
                )
                for _ in range(iterations):
                    started_at = time.perf_counter()
                    _scan_three_viewport_page_once(
                        page,
                        analyzer=analyzer,
                        preprocessing_profile=preprocessing_profile,
                    )
                    page_durations.append(
                        (time.perf_counter() - started_at) * 1000.0
                    )
            finally:
                context.close()
        finally:
            chrome_version = browser.version
            browser.close()

    return {
        "chrome_version": chrome_version,
        "iterations": iterations,
        "viewport_1920x1080": _duration_summary(viewport_durations),
        "three_viewport_page": _duration_summary(page_durations),
    }


def run_web_e2e_benchmark(
    pipeline: OcrRecognitionPipeline,
    *,
    chrome_executable: Path,
) -> dict[str, object]:
    if not chrome_executable.is_file():
        raise RuntimeError(f"Chrome executable is unavailable: {chrome_executable}")

    from playwright.sync_api import sync_playwright

    from app.workers.browser import PlaywrightBrowserExecutionAdapter

    analyzer = DefaultVisionAssertionAdapter(ocr_pipeline=pipeline)
    adapter = PlaywrightBrowserExecutionAdapter(
        headless=True,
        navigation_timeout_ms=15000,
        ocr_analyzer=analyzer,
    )
    payloads = _e2e_payloads()
    for _, payload in payloads:
        _assert_no_selector(payload)

    cases: list[dict[str, object]] = []
    action_attempts = 0
    action_successes = 0
    wrong_operations = 0
    step_attempts = 0
    step_successes = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=str(chrome_executable),
        )
        try:
            for case_id, viewport, device_scale_factor in E2E_CONFIGURATIONS:
                case_result = _run_web_e2e_case(
                    browser,
                    adapter=adapter,
                    case_id=case_id,
                    viewport=viewport,
                    device_scale_factor=device_scale_factor,
                    payloads=payloads,
                )
                cases.append(case_result)
                action_attempts += int(case_result["action_attempts"])
                action_successes += int(case_result["action_successes"])
                wrong_operations += int(case_result["wrong_operations"])
                step_attempts += int(case_result["step_attempts"])
                step_successes += int(case_result["step_successes"])
        finally:
            browser.close()

    return {
        "case_count": len(cases),
        "step_attempts": step_attempts,
        "step_successes": step_successes,
        "step_success_rate": rounded_metric(
            ratio(step_successes, step_attempts)
        ),
        "unique_interaction_attempts": action_attempts,
        "unique_interaction_successes": action_successes,
        "unique_interaction_success_rate": rounded_metric(
            ratio(action_successes, action_attempts)
        ),
        "wrong_operations": wrong_operations,
        "wrong_operation_rate": rounded_metric(
            ratio(wrong_operations, action_attempts)
        ),
        "cases": cases,
    }


def _e2e_target(text: str) -> dict[str, object]:
    return {
        "text": text,
        "language": "en",
        "min_confidence": 0.40,
        "min_score": 0.50,
        "ambiguity_margin": 0.05,
    }


def _e2e_payloads() -> tuple[tuple[str, dict[str, object]], ...]:
    return (
        (
            "click",
            {
                "locator": "ocr",
                "ocr_target": _e2e_target("Run Action"),
            },
        ),
        (
            "input",
            {
                "locator": "ocr",
                "ocr_target": _e2e_target("Type account"),
                "text": "Account 42",
                "input_mode": "fill",
                "verify_ocr": True,
            },
        ),
        (
            "select_option",
            {
                "field_target": _e2e_target("Choose country"),
                "option_target": _e2e_target("Japan"),
                "verify_selected": True,
            },
        ),
        (
            "long_press",
            {
                "locator": "ocr",
                "ocr_target": _e2e_target("Hold Action"),
                "duration_ms": 180,
            },
        ),
        (
            "scroll",
            {
                "target": "element",
                "locator": "ocr",
                "ocr_target": _e2e_target("Scroll Region"),
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
                            "ocr_target": _e2e_target("Branch Ready"),
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
                "ocr_target": _e2e_target("Branch Ready"),
            },
        ),
    )


def _assert_no_selector(value: object) -> None:
    if isinstance(value, Mapping):
        if "selector" in value:
            raise ValueError("Pure OCR E2E payload must not contain selector.")
        for nested in value.values():
            _assert_no_selector(nested)
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for nested in value:
            _assert_no_selector(nested)


def _run_web_e2e_case(
    browser: Any,
    *,
    adapter: Any,
    case_id: str,
    viewport: tuple[int, int],
    device_scale_factor: int,
    payloads: Sequence[tuple[str, dict[str, object]]],
) -> dict[str, object]:
    context = browser.new_context(
        viewport={"width": viewport[0], "height": viewport[1]},
        device_scale_factor=device_scale_factor,
        locale="en-US",
        timezone_id="UTC",
    )
    step_results: list[dict[str, object]] = []
    action_attempts = 0
    action_successes = 0
    wrong_operations = 0
    action_step_types = {
        "click",
        "input",
        "select_option",
        "long_press",
        "scroll",
    }
    try:
        page = context.new_page()
        page.goto(E2E_PAGE_PATH.as_uri(), wait_until="load", timeout=15000)
        page.evaluate("() => document.fonts.ready")
        session = adapter._build_ocr_session(page)
        for step_no, (step_type, payload) in enumerate(payloads, start=1):
            if step_type in action_step_types:
                action_attempts += 1
            started_at = time.perf_counter()
            try:
                outcome = adapter._execute_step(
                    page,
                    base_url=E2E_PAGE_PATH.as_uri(),
                    step=_BenchmarkBrowserStep(
                        step_no=step_no,
                        step_type=step_type,
                        payload_json=payload,
                    ),
                    case_run_id=1,
                    template_contexts={},
                    ocr_session=session,
                )
                verification_passed = _verify_e2e_step(
                    page,
                    step_type=step_type,
                    outcome=outcome,
                )
                passed = outcome.status == "passed" and verification_passed
                if step_type in action_step_types and passed:
                    action_successes += 1
                if (
                    step_type in action_step_types
                    and outcome.status == "passed"
                    and not verification_passed
                ):
                    wrong_operations += 1
                step_results.append(
                    {
                        "step_type": step_type,
                        "status": outcome.status,
                        "verification_passed": verification_passed,
                        "passed": passed,
                        "elapsed_ms": round(
                            (time.perf_counter() - started_at) * 1000.0,
                            3,
                        ),
                        "error": outcome.error_message,
                    }
                )
                if not passed:
                    break
            except Exception as exc:  # noqa: BLE001 - report real E2E failure
                step_results.append(
                    {
                        "step_type": step_type,
                        "status": "error",
                        "verification_passed": False,
                        "passed": False,
                        "elapsed_ms": round(
                            (time.perf_counter() - started_at) * 1000.0,
                            3,
                        ),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                break
    finally:
        context.close()

    return {
        "case_id": case_id,
        "viewport_css": list(viewport),
        "device_scale_factor": device_scale_factor,
        "step_attempts": len(step_results),
        "step_successes": sum(
            result["passed"] is True for result in step_results
        ),
        "action_attempts": action_attempts,
        "action_successes": action_successes,
        "wrong_operations": wrong_operations,
        "steps": step_results,
    }


def _verify_e2e_step(
    page: Any,
    *,
    step_type: str,
    outcome: Any,
) -> bool:
    if step_type == "click":
        return page.locator("#status").text_content() == "Action Complete"
    if step_type == "input":
        return page.locator("#account-input").input_value() == "Account 42"
    if step_type == "select_option":
        return (
            page.locator("#country-field").text_content() == "Japan"
            and page.locator("#status").text_content() == "Selection Complete"
        )
    if step_type == "long_press":
        return page.locator("#status").text_content() == "Long Pressed"
    if step_type == "scroll":
        return (
            page.locator("#scroll-box").evaluate(
                "element => element.scrollTop"
            )
            > 0
            and page.locator("#status").text_content() == "Element Scrolled"
        )
    if step_type == "conditional_branch":
        return outcome.error_message == "命中分支：OCR Ready"
    if step_type == "ocr_assert":
        return (
            outcome.result_metadata_json.get("ocr", {}).get("assertion")
            == "present"
        )
    return False


def _recognize_viewport_once(
    page: Any,
    *,
    analyzer: DefaultVisionAssertionAdapter,
    preprocessing_profile: str,
) -> None:
    PageOcrSession(
        page=page,
        analyzer=analyzer,
        preprocessing_profile=preprocessing_profile,  # type: ignore[arg-type]
        stability_wait_ms=0,
    ).recognize_viewport(language_profile="en")


def _scan_three_viewport_page_once(
    page: Any,
    *,
    analyzer: DefaultVisionAssertionAdapter,
    preprocessing_profile: str,
) -> None:
    page.evaluate("() => window.scrollTo(0, 0)")
    session = PageOcrSession(
        page=page,
        analyzer=analyzer,
        preprocessing_profile=preprocessing_profile,  # type: ignore[arg-type]
        max_page_tiles=4,
        page_tile_overlap_ratio=0.20,
        total_timeout_seconds=15.0,
        stability_wait_ms=0,
    )
    resolution = session.resolve(
        OcrTargetSpec(
            text="Third viewport acceptance target",
            language="en",
            scope="page",
            min_confidence=0.50,
            min_score=0.50,
            ambiguity_margin=0.05,
        )
    )
    if resolution.selected_candidate is None:
        raise RuntimeError("Three-viewport benchmark target was not resolved.")


def _duration_summary(values: Sequence[float]) -> dict[str, object]:
    return {
        "sample_count": len(values),
        "minimum_ms": round(min(values), 3),
        "median_ms": round(percentile(values, 0.50), 3),
        "p95_ms": round(percentile(values, 0.95), 3),
        "maximum_ms": round(max(values), 3),
        "samples_ms": [round(value, 3) for value in values],
    }


def evaluate_thresholds(
    *,
    manifest: Mapping[str, object],
    accuracy: Mapping[str, object],
    performance: Mapping[str, object],
    web_e2e: Mapping[str, object],
) -> dict[str, object]:
    raw_thresholds = manifest["thresholds"]
    assert isinstance(raw_thresholds, Mapping)
    detection = accuracy["detection"]
    recognition = accuracy["recognition"]
    targeting = accuracy["targeting"]
    ambiguity = accuracy["ambiguity"]
    viewport_performance = performance["viewport_1920x1080"]
    page_performance = performance["three_viewport_page"]
    assert isinstance(detection, Mapping)
    assert isinstance(recognition, Mapping)
    assert isinstance(targeting, Mapping)
    assert isinstance(ambiguity, Mapping)
    assert isinstance(viewport_performance, Mapping)
    assert isinstance(page_performance, Mapping)

    checks = {
        "clear_detection_f1": {
            "actual": detection["f1"],
            "operator": ">=",
            "threshold": raw_thresholds["clear_detection_f1_min"],
            "passed": float(detection["f1"])
            >= float(raw_thresholds["clear_detection_f1_min"]),
        },
        "clear_zh_en_cer": {
            "actual": recognition["cer"],
            "operator": "<=",
            "threshold": raw_thresholds["clear_zh_en_cer_max"],
            "passed": float(recognition["cer"])
            <= float(raw_thresholds["clear_zh_en_cer_max"]),
        },
        "disturbed_target_success_rate": {
            "actual": targeting["disturbed_success_rate"],
            "operator": ">=",
            "threshold": raw_thresholds["disturbed_target_success_min"],
            "passed": float(targeting["disturbed_success_rate"])
            >= float(raw_thresholds["disturbed_target_success_min"]),
        },
        "wrong_operation_rate": {
            "actual": web_e2e["wrong_operation_rate"],
            "operator": "<",
            "threshold": raw_thresholds[
                "wrong_operation_rate_max_exclusive"
            ],
            "passed": float(web_e2e["wrong_operation_rate"])
            < float(raw_thresholds["wrong_operation_rate_max_exclusive"]),
        },
        "unique_interaction_success_rate": {
            "actual": web_e2e["unique_interaction_success_rate"],
            "operator": ">=",
            "threshold": raw_thresholds[
                "unique_interaction_success_min"
            ],
            "passed": float(web_e2e["unique_interaction_success_rate"])
            >= float(raw_thresholds["unique_interaction_success_min"]),
        },
        "ambiguity_rejection_rate": {
            "actual": ambiguity["rejection_rate"],
            "operator": ">=",
            "threshold": raw_thresholds["ambiguity_rejection_rate_min"],
            "passed": float(ambiguity["rejection_rate"])
            >= float(raw_thresholds["ambiguity_rejection_rate_min"]),
        },
        "viewport_p95_ms": {
            "actual": viewport_performance["p95_ms"],
            "operator": "<=",
            "threshold": raw_thresholds["viewport_p95_ms_max"],
            "passed": float(viewport_performance["p95_ms"])
            <= float(raw_thresholds["viewport_p95_ms_max"]),
        },
        "three_viewport_page_p95_ms": {
            "actual": page_performance["p95_ms"],
            "operator": "<=",
            "threshold": raw_thresholds["three_viewport_page_p95_ms_max"],
            "passed": float(page_performance["p95_ms"])
            <= float(raw_thresholds["three_viewport_page_p95_ms_max"]),
        },
    }
    return {
        "passed": all(bool(check["passed"]) for check in checks.values()),
        "checks": checks,
    }


def build_result(
    *,
    manifest: Mapping[str, object],
    model_root: Path,
    preprocessing_profile: str,
    max_preprocess_variants: int,
    minimum_confidence: float,
    warmup: Mapping[str, str | None],
    accuracy: Mapping[str, object],
    performance: Mapping[str, object],
    web_e2e: Mapping[str, object],
    thresholds: Mapping[str, object],
    command: Sequence[str],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "result_kind": "real_paddleocr",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "command": _portable_command(command),
        "corpus": {
            "id": manifest["corpus_id"],
            "version": manifest["corpus_version"],
            "random_seed": manifest["random_seed"],
            "manifest_sha256": _file_sha256(MANIFEST_PATH),
            "renderer": manifest["renderer"],
        },
        "runtime": {
            "preprocessing_profile": preprocessing_profile,
            "max_preprocess_variants": max_preprocess_variants,
            "minimum_confidence": minimum_confidence,
            "warmup": dict(warmup),
        },
        "environment": collect_environment_metadata(
            model_root=model_root,
            chrome_version=str(performance["chrome_version"]),
        ),
        "accuracy": dict(accuracy),
        "performance": dict(performance),
        "web_e2e": dict(web_e2e),
        "thresholds": dict(thresholds),
    }


def collect_environment_metadata(
    *,
    model_root: Path,
    chrome_version: str,
) -> dict[str, object]:
    package_names = (
        "paddlepaddle",
        "paddleocr",
        "opencv-python-headless",
        "numpy",
        "playwright",
    )
    return {
        "hardware_profile": _anonymous_hardware_profile(),
        "python": platform.python_version(),
        "packages": {
            package_name: _package_version(package_name)
            for package_name in package_names
        },
        "chrome": chrome_version,
        "git_commit": _git_commit(),
        "models": _model_metadata(model_root),
    }


def write_result(path: Path, result: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def require_passing_thresholds(thresholds: Mapping[str, object]) -> None:
    if thresholds.get("passed") is True:
        return
    raw_checks = thresholds.get("checks")
    failed: list[str] = []
    if isinstance(raw_checks, Mapping):
        failed = [
            str(name)
            for name, raw_check in raw_checks.items()
            if isinstance(raw_check, Mapping)
            and raw_check.get("passed") is not True
        ]
    raise BenchmarkThresholdError(
        "OCR benchmark thresholds failed: " + ", ".join(failed)
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _model_metadata(model_root: Path) -> list[dict[str, object]]:
    metadata: list[dict[str, object]] = []
    if not model_root.exists():
        return metadata
    for path in sorted(model_root.rglob("*")):
        if not path.is_file() or path.name not in {
            "inference.pdmodel",
            "inference.pdiparams",
            "inference.pdiparams.info",
        }:
            continue
        metadata.append(
            {
                "path": str(path.relative_to(model_root)),
                "bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    return metadata


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _sysctl_value(name: str) -> str | None:
    try:
        completed = subprocess.run(
            ("sysctl", "-n", name),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = completed.stdout.strip()
    return value or None


def _optional_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _portable_command(command: Sequence[str]) -> list[str]:
    portable: list[str] = []
    repository_root = BACKEND_ROOT.parent.resolve()
    for index, raw_argument in enumerate(command):
        if index == 0:
            portable.append("python")
            continue
        argument = Path(raw_argument).expanduser()
        if not argument.is_absolute():
            portable.append(raw_argument)
            continue
        try:
            relative = argument.resolve().relative_to(repository_root)
        except ValueError:
            portable.append(argument.name)
        else:
            portable.append(f"<repo>/{relative.as_posix()}")
    return portable


def _anonymous_hardware_profile() -> dict[str, object]:
    cpu = (
        _sysctl_value("machdep.cpu.brand_string")
        or platform.processor()
        or platform.machine()
        or "unknown"
    )
    memory_bytes = _optional_int(_sysctl_value("hw.memsize"))
    return {
        "os_family": platform.system() or "unknown",
        "architecture": platform.machine() or "unknown",
        "processor_family": _processor_family(cpu),
        "memory_class": _memory_class(memory_bytes),
    }


def _processor_family(value: str) -> str:
    normalized = value.casefold()
    if "apple" in normalized:
        return "Apple Silicon"
    if "intel" in normalized:
        return "Intel"
    if "amd" in normalized:
        return "AMD"
    return platform.machine() or "unknown"


def _memory_class(memory_bytes: int | None) -> str:
    if memory_bytes is None:
        return "unknown"
    memory_gib = memory_bytes / float(1024**3)
    for upper_bound in (8, 16, 32, 64, 128, 256):
        if memory_gib <= upper_bound:
            return f"up_to_{upper_bound}_gib"
    return "over_256_gib"


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=BACKEND_ROOT.parent,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def assert_real_model_opt_in() -> None:
    if os.environ.get("VAT_RUN_REAL_OCR_BENCHMARK") != "1":
        raise RuntimeError(
            "Set VAT_RUN_REAL_OCR_BENCHMARK=1 to run real PaddleOCR acceptance."
        )
    if "pytest" in sys.modules and os.environ.get("VAT_ALLOW_PYTEST_REAL_OCR") != "1":
        raise RuntimeError(
            "Set VAT_ALLOW_PYTEST_REAL_OCR=1 for real-model pytest execution."
        )
