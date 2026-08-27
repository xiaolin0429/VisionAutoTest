from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from app.workers.browser_ocr_actions import execute_ocr_select_option
from app.workers.browser_locators import (
    build_input_verification_target,
    raise_input_verification_error,
)
from app.workers.ocr_assertions import (
    OcrAssertionEvaluation,
    evaluate_ocr_assertion,
)
from app.workers.ocr_contract import (
    NormalizedOcrAssertPayload,
    normalize_ocr_assert_payload,
)
from app.workers.ocr_engine import OcrEngineError
from app.workers.ocr_evidence import (
    OcrEvidenceCacheSnapshot,
    OcrEvidenceCapture,
    OcrResolutionEvidence,
    build_ocr_annotation_png,
    build_ocr_result_metadata,
)
from app.workers.ocr_page import (
    OcrPageGeometryError,
    build_ocr_page_snapshot_from_analysis,
)
from app.workers.ocr_targeting import OcrTargetingError, resolve_ocr_target
from app.workers.ocr_types import (
    OcrErrorCode,
    OcrLanguageProfile,
    OcrPageSnapshot,
    OcrPoint,
    OcrTargetResolution,
    OcrTargetSpec,
)
from app.workers.vision import VisionArtifact


def _step_execution_outcome(**kwargs):
    from app.workers.browser import StepExecutionOutcome

    return StepExecutionOutcome(**kwargs)


def _invalidate_ocr_session(ocr_session, reason: str) -> None:
    if ocr_session is not None:
        ocr_session.invalidate(reason)


def _evidence_for_resolution(
    ocr_session,
    resolution: OcrTargetResolution | None,
) -> OcrResolutionEvidence | None:
    getter = getattr(ocr_session, "evidence_for", None)
    return getter(resolution) if callable(getter) else None


def _sensitive_values(step) -> tuple[str, ...]:
    if step.step_type != "input":
        return ()
    payload = step.payload_json or {}
    if not any(
        payload.get(key) is True
        for key in ("sensitive", "is_sensitive", "input_is_sensitive")
    ):
        return ()
    text = payload.get("text")
    return (text,) if isinstance(text, str) and text else ()


def _build_ocr_artifact(
    *,
    evidence: OcrResolutionEvidence | None,
    case_run_id: int,
    step_no: int,
    artifact_type: str,
    action_point: OcrPoint | None = None,
    sensitive_values: tuple[str, ...] = (),
) -> VisionArtifact | None:
    if evidence is None:
        return None
    try:
        content_bytes = build_ocr_annotation_png(
            evidence,
            action_point=action_point,
            sensitive_values=sensitive_values,
        )
    except Exception:  # noqa: BLE001 - evidence must never replace step semantics
        return None
    return VisionArtifact(
        file_name=(
            f"case-run-{case_run_id}-step-{step_no}-{artifact_type}.png"
        ),
        content_type="image/png",
        content_bytes=content_bytes,
        artifact_type=artifact_type,
    )


def _build_ocr_action_evidence(
    *,
    loc,
    case_run_id: int,
    step,
) -> tuple[dict[str, object], VisionArtifact | None]:
    sensitive_values = _sensitive_values(step)
    metadata = build_ocr_result_metadata(
        loc.resolution,
        evidence=loc.evidence,
        action_point=loc.point,
        sensitive_values=sensitive_values,
    )
    artifact = _build_ocr_artifact(
        evidence=loc.evidence,
        case_run_id=case_run_id,
        step_no=step.step_no,
        artifact_type="ocr_action",
        action_point=loc.point,
        sensitive_values=sensitive_values,
    )
    return metadata, artifact


def _resolution_action_point(
    resolution: OcrTargetResolution,
) -> OcrPoint | None:
    selected = resolution.selected_candidate
    if selected is None:
        return None
    if resolution.target.action_point == "associated_control":
        rect = selected.element.associated_control_rect
    else:
        rect = selected.element.coordinates.viewport_css_rect
    if rect is None:
        return None
    return OcrPoint(
        x=rect.x + rect.width / 2.0,
        y=rect.y + rect.height / 2.0,
    )


def execute_wait(
    adapter,
    page,
    *,
    step,
    timeout_ms: int,
    ocr_session=None,
    **_kwargs,
):
    payload = step.payload_json or {}
    wait_ms = adapter._payload_int(payload, "ms")
    if wait_ms < 0:
        raise ValueError("wait step `ms` must be greater than or equal to 0.")
    page.wait_for_timeout(wait_ms)
    _invalidate_ocr_session(ocr_session, "wait")
    return _step_execution_outcome(status="passed", score_value=1.0)


def execute_navigate(
    adapter,
    page,
    *,
    step,
    base_url: str,
    timeout_ms: int,
    ocr_session=None,
    **_kwargs,
):
    payload = step.payload_json or {}
    url = adapter._payload_str(payload, "url")
    wait_until = payload.get("wait_until", "load")
    if wait_until not in {"load", "domcontentloaded", "networkidle"}:
        raise ValueError(
            "navigate `wait_until` must be `load`, `domcontentloaded`, or `networkidle`."
        )
    page.goto(
        adapter._resolve_navigate_url(base_url, url),
        wait_until=wait_until,
        timeout=timeout_ms,
    )
    _invalidate_ocr_session(ocr_session, "navigate")
    return _step_execution_outcome(status="passed", score_value=1.0)


def execute_click(
    adapter,
    page,
    *,
    step,
    case_run_id: int,
    timeout_ms: int,
    template_contexts,
    ocr_session=None,
    **_kwargs,
):
    payload = step.payload_json or {}
    result_metadata_json = {}
    actual_artifact = None
    if adapter._uses_visual_locator(payload):
        loc = adapter._resolve_interaction_target(
            page,
            payload,
            template_contexts=template_contexts,
            ocr_session=ocr_session,
        )
        point = adapter._resolve_visual_anchor_point(payload, loc)
        page.mouse.click(point.x, point.y)
        if adapter._is_ocr_locator(payload):
            result_metadata_json, actual_artifact = _build_ocr_action_evidence(
                loc=loc,
                case_run_id=case_run_id,
                step=step,
            )
    else:
        selector = adapter._payload_str(payload, "selector")
        page.locator(selector).click(timeout=timeout_ms)
    _invalidate_ocr_session(ocr_session, "click")
    return _step_execution_outcome(
        status="passed",
        score_value=1.0,
        actual_artifact=actual_artifact,
        result_metadata_json=result_metadata_json,
    )


def execute_input(
    adapter,
    page,
    *,
    step,
    case_run_id: int,
    timeout_ms: int,
    template_contexts,
    ocr_session=None,
    **_kwargs,
):
    payload = step.payload_json or {}
    text = adapter._payload_str(payload, "text")
    input_mode = payload.get("input_mode", "fill")
    if input_mode not in {"fill", "type", "otp"}:
        raise ValueError("input `input_mode` must be `fill`, `type`, or `otp`.")
    per_char_delay_ms = adapter._optional_non_negative_int(
        payload, "per_char_delay_ms", default=80
    )
    result_metadata_json = {}
    actual_artifact = None
    if adapter._is_ocr_locator(payload):
        loc = adapter._resolve_interaction_target(
            page,
            payload,
            template_contexts=template_contexts,
            ocr_session=ocr_session,
        )
        point = adapter._resolve_visual_anchor_point(payload, loc)
        page.mouse.click(point.x, point.y)
        if input_mode == "fill":
            page.keyboard.press("ControlOrMeta+A")
            page.keyboard.press("Backspace")
        adapter._input_via_keyboard(
            page,
            text=text,
            input_mode=input_mode,
            otp_length=adapter._optional_positive_int(payload, "otp_length"),
            per_char_delay_ms=per_char_delay_ms,
        )
        _invalidate_ocr_session(ocr_session, "input")
        verification_target = build_input_verification_target(
            payload,
            action_target=loc.resolution.target,
        )
        if verification_target is not None:
            try:
                ocr_session.resolve(verification_target)
            except OcrTargetingError as exc:
                raise_input_verification_error(verification_target, exc)
        result_metadata_json, actual_artifact = _build_ocr_action_evidence(
            loc=loc,
            case_run_id=case_run_id,
            step=step,
        )
    elif adapter._uses_visual_locator(payload):
        loc = adapter._resolve_interaction_target(
            page,
            payload,
            template_contexts=template_contexts,
            ocr_session=ocr_session,
        )
        point = adapter._resolve_visual_anchor_point(payload, loc)
        page.mouse.click(point.x, point.y)
        adapter._prepare_input_focus(page, input_mode=input_mode)
        adapter._input_via_keyboard(
            page,
            text=text,
            input_mode=input_mode,
            otp_length=adapter._optional_positive_int(payload, "otp_length"),
            per_char_delay_ms=per_char_delay_ms,
        )
        adapter._verify_input_applied(
            page,
            text=text,
            input_mode=input_mode,
            otp_length=adapter._optional_positive_int(payload, "otp_length"),
        )
        _invalidate_ocr_session(ocr_session, "input")
    else:
        selector = adapter._payload_str(payload, "selector")
        locator = page.locator(selector)
        if input_mode == "fill":
            locator.fill(text, timeout=timeout_ms)
            current_value = locator.input_value(timeout=timeout_ms)
            if current_value != text:
                raise RuntimeError("Input fill did not persist the expected value.")
        else:
            locator.click(timeout=timeout_ms)
            adapter._prepare_input_focus(page, input_mode=input_mode)
            adapter._input_via_keyboard(
                page,
                text=text,
                input_mode=input_mode,
                otp_length=adapter._optional_positive_int(payload, "otp_length"),
                per_char_delay_ms=per_char_delay_ms,
            )
            adapter._verify_input_applied(
                page,
                text=text,
                input_mode=input_mode,
                otp_length=adapter._optional_positive_int(payload, "otp_length"),
            )
        _invalidate_ocr_session(ocr_session, "input")
    return _step_execution_outcome(
        status="passed",
        score_value=1.0,
        actual_artifact=actual_artifact,
        result_metadata_json=result_metadata_json,
    )


def execute_select_option(
    adapter,
    page,
    *,
    step,
    case_run_id: int,
    timeout_ms: int,
    ocr_session=None,
    **_kwargs,
):
    _ = adapter
    if ocr_session is None:
        raise OcrEngineError(
            OcrErrorCode.OCR_ENGINE_UNAVAILABLE,
            "select_option requires a case-local PageOcrSession.",
        )
    result = execute_ocr_select_option(
        page,
        ocr_session=ocr_session,
        payload=step.payload_json or {},
        timeout_ms=timeout_ms,
    )
    field_evidence = _evidence_for_resolution(
        ocr_session,
        result.field_resolution,
    )
    option_evidence = _evidence_for_resolution(
        ocr_session,
        result.option_resolution,
    )
    option_point = _resolution_action_point(result.option_resolution)
    primary_metadata = build_ocr_result_metadata(
        result.option_resolution,
        evidence=option_evidence,
        action_point=option_point,
    )
    stages: dict[str, object] = {
        "field": build_ocr_result_metadata(
            result.field_resolution,
            evidence=field_evidence,
            action_point=_resolution_action_point(result.field_resolution),
        )["ocr"],
        "option": primary_metadata["ocr"],
    }
    if result.verification_resolution is not None:
        stages["verification"] = build_ocr_result_metadata(
            result.verification_resolution,
            evidence=_evidence_for_resolution(
                ocr_session,
                result.verification_resolution,
            ),
        )["ocr"]
    primary_metadata["ocr_stages"] = stages
    return _step_execution_outcome(
        status="passed",
        score_value=1.0,
        actual_artifact=_build_ocr_artifact(
            evidence=option_evidence,
            case_run_id=case_run_id,
            step_no=step.step_no,
            artifact_type="ocr_action",
            action_point=option_point,
        ),
        result_metadata_json=primary_metadata,
    )


def execute_conditional_branch(
    adapter,
    page,
    *,
    step,
    template_contexts,
    ocr_session=None,
    **_kwargs,
):
    selected = adapter._select_matching_branch(
        page,
        payload=step.payload_json or {},
        template_contexts=template_contexts,
        ocr_session=ocr_session,
    )
    if selected is None:
        raise RuntimeError(
            "conditional_branch did not match any branch and no else_branch was configured."
        )
    label = selected.get("branch_name") or selected.get("branch_key") or "默认分支"
    return _step_execution_outcome(
        status="passed",
        score_value=1.0,
        error_message=f"命中分支：{label}",
    )


def execute_ocr_assert(
    adapter,
    page,
    *,
    step,
    case_run_id: int,
    timeout_ms: int,
    ocr_session=None,
    **_kwargs,
):
    payload = step.payload_json or {}
    normalized = normalize_ocr_assert_payload(payload)
    evidence: OcrResolutionEvidence | None = None
    image_bytes: bytes | None = None
    if normalized.is_legacy:
        assert normalized.selector is not None
        image_bytes = page.locator(normalized.selector).screenshot(
            type="png",
            timeout=timeout_ms,
        )
        if "ocr_target" not in payload and normalized.assertion == "present":
            legacy_outcome = adapter._vision_adapter.assert_ocr(
                image_png_bytes=image_bytes,
                image_file_name=(
                    f"case-run-{case_run_id}-step-{step.step_no}-ocr.png"
                ),
                expected_text=normalized.target.text,
                match_mode=normalized.target.match_mode,
                case_sensitive=normalized.target.case_sensitive,
            )
            actual_artifact = legacy_outcome.actual_artifact
            if actual_artifact is not None:
                actual_artifact = VisionArtifact(
                    file_name=(
                        f"case-run-{case_run_id}-step-{step.step_no}-ocr-assert.png"
                    ),
                    content_type=actual_artifact.content_type,
                    content_bytes=actual_artifact.content_bytes,
                    artifact_type="ocr_assert",
                )
            legacy_metadata = build_ocr_result_metadata(
                OcrTargetResolution(
                    status=(
                        "resolved"
                        if legacy_outcome.status == "passed"
                        else "not_found"
                    ),
                    target=normalized.target,
                )
            )
            legacy_ocr_metadata = legacy_metadata["ocr"]
            assert isinstance(legacy_ocr_metadata, dict)
            legacy_ocr_metadata.update(
                {
                    "assertion": "present",
                    "assertion_status": legacy_outcome.status,
                    "assertion_scope": "element_legacy",
                    "legacy_element_scope": True,
                }
            )
            return _step_execution_outcome(
                status=legacy_outcome.status,
                score_value=legacy_outcome.score_value,
                error_message=legacy_outcome.error_message,
                actual_artifact=actual_artifact,
                result_metadata_json=legacy_metadata,
            )
        snapshot = _build_legacy_ocr_snapshot(
            adapter,
            image_bytes=image_bytes,
            language_profile=normalized.target.language,
        )
        evaluation = evaluate_ocr_assertion(
            normalized,
            resolve=lambda target: resolve_ocr_target(snapshot, target),
        )
        evidence = _build_static_ocr_evidence(
            target=normalized.target,
            resolution=evaluation.resolution,
            snapshot=snapshot,
            image_bytes=image_bytes,
        )
    else:
        if ocr_session is None:
            raise OcrEngineError(
                OcrErrorCode.OCR_ENGINE_UNAVAILABLE,
                "Pure OCR assertion requires a case-local PageOcrSession.",
            )
        evaluation = evaluate_ocr_assertion(
            normalized,
            resolve=ocr_session.resolve,
        )
        evidence = _evidence_for_resolution(
            ocr_session,
            evaluation.resolution,
        )

    actual_artifact = _build_ocr_artifact(
        evidence=evidence,
        case_run_id=case_run_id,
        step_no=step.step_no,
        artifact_type="ocr_assert",
    )
    if actual_artifact is None:
        if image_bytes is None:
            image_bytes = page.screenshot(type="png", full_page=False)
        actual_artifact = VisionArtifact(
            file_name=(
                f"case-run-{case_run_id}-step-{step.step_no}-ocr-assert.png"
            ),
            content_type="image/png",
            content_bytes=image_bytes,
            artifact_type="ocr_assert",
        )

    return _step_execution_outcome(
        status=evaluation.status,
        score_value=evaluation.score_value,
        error_message=evaluation.error_message,
        failure_reason_code=(
            evaluation.resolution.error_code.value
            if evaluation.status == "error"
            and evaluation.resolution is not None
            and evaluation.resolution.error_code is not None
            else None
        ),
        actual_artifact=actual_artifact,
        result_metadata_json=_build_ocr_assertion_metadata(
            normalized=normalized,
            evaluation=evaluation,
            evidence=evidence,
        ),
    )


def _build_legacy_ocr_snapshot(
    adapter,
    *,
    image_bytes: bytes,
    language_profile: OcrLanguageProfile,
) -> OcrPageSnapshot:
    try:
        analysis = adapter._ocr_analyzer.analyze_ocr(
            image_png_bytes=image_bytes,
            language_profile=language_profile,
        )
    except OcrEngineError:
        raise
    except Exception as exc:
        raise OcrEngineError(
            OcrErrorCode.OCR_ANALYSIS_FAILED,
            f"Legacy OCR analyzer failed: {exc}",
        ) from exc
    if not isinstance(analysis, Mapping):
        raise OcrEngineError(
            OcrErrorCode.OCR_ANALYSIS_FAILED,
            "Legacy OCR analyzer returned an invalid analysis object.",
        )
    image_width = analysis.get("image_width")
    image_height = analysis.get("image_height")
    if (
        isinstance(image_width, bool)
        or not isinstance(image_width, int)
        or image_width < 1
        or isinstance(image_height, bool)
        or not isinstance(image_height, int)
        or image_height < 1
    ):
        raise OcrPageGeometryError(
            "Legacy OCR analysis requires positive integer image dimensions."
        )
    return build_ocr_page_snapshot_from_analysis(
        image_png_bytes=image_bytes,
        analysis=analysis,
        viewport_width_css=image_width,
        viewport_height_css=image_height,
        device_scale_factor=1.0,
    )


def _build_static_ocr_evidence(
    *,
    target: OcrTargetSpec,
    resolution: OcrTargetResolution | None,
    snapshot: OcrPageSnapshot,
    image_bytes: bytes,
) -> OcrResolutionEvidence:
    cache_before = OcrEvidenceCacheSnapshot(
        analysis_hits=0,
        analysis_misses=0,
        snapshot_hits=0,
        snapshot_misses=0,
        generation=0,
        last_invalidation_reason=None,
    )
    cache_after = OcrEvidenceCacheSnapshot(
        analysis_hits=0,
        analysis_misses=1,
        snapshot_hits=0,
        snapshot_misses=1,
        generation=0,
        last_invalidation_reason=None,
    )
    return OcrResolutionEvidence(
        target=target,
        resolution=resolution,
        captures=(
            OcrEvidenceCapture(
                image_png_bytes=image_bytes,
                snapshot=snapshot,
                snapshot_cache_hit=False,
                analysis_cache_hit=False,
            ),
        ),
        cache_before=cache_before,
        cache_after=cache_after,
        revalidation_required=False,
        revalidation_attempted=False,
        revalidation_passed=None,
        locate_duration_ms=resolution.elapsed_ms if resolution is not None else 0.0,
        error_code=resolution.error_code if resolution is not None else None,
    )


def _build_ocr_assertion_metadata(
    *,
    normalized: NormalizedOcrAssertPayload,
    evaluation: OcrAssertionEvaluation,
    evidence: OcrResolutionEvidence | None,
) -> dict[str, object]:
    resolution = evaluation.resolution
    if resolution is None:
        metadata: dict[str, object] = {}
    else:
        metadata = build_ocr_result_metadata(
            resolution,
            evidence=evidence,
        )
    ocr_metadata = metadata.setdefault("ocr", {})
    assert isinstance(ocr_metadata, dict)
    ocr_metadata.update(
        {
            "assertion": normalized.assertion,
            "assertion_status": evaluation.status,
            "assertion_scope": normalized.scope,
            "legacy_element_scope": normalized.is_legacy,
        }
    )
    if normalized.expected_count is not None:
        ocr_metadata["expected_count"] = normalized.expected_count
    if evaluation.matched_count is not None:
        ocr_metadata["matched_count"] = evaluation.matched_count
    if resolution is not None and resolution.error_code is not None:
        if evaluation.status == "passed":
            ocr_metadata.pop("error_code", None)
        else:
            ocr_metadata["error_code"] = resolution.error_code.value
    return metadata


def execute_template_assert(
    adapter,
    page,
    *,
    step,
    case_run_id: int,
    template_contexts,
    **_kwargs,
):
    if step.template_id is None or step.template_id not in template_contexts:
        raise ValueError("Template assertion context is missing.")
    payload = step.payload_json or {}
    threshold_override = payload.get("threshold")
    if threshold_override is not None:
        threshold_override = adapter._payload_float(payload, "threshold")
    screenshot_bytes = page.screenshot(type="png", full_page=True)
    outcome = adapter._vision_adapter.assert_template(
        context=template_contexts[step.template_id],
        actual_png_bytes=screenshot_bytes,
        actual_file_name=f"case-run-{case_run_id}-step-{step.step_no}-actual.png",
        threshold_override=threshold_override,
    )
    return _step_execution_outcome(
        status=outcome.status,
        score_value=outcome.score_value,
        error_message=outcome.error_message,
        expected_media_object_id=outcome.expected_media_object_id,
        actual_artifact=outcome.actual_artifact,
        diff_artifact=outcome.diff_artifact,
    )


def execute_scroll(
    adapter,
    page,
    *,
    step,
    case_run_id: int,
    timeout_ms: int,
    template_contexts,
    ocr_session=None,
    **_kwargs,
):
    payload = step.payload_json or {}
    target = adapter._payload_str(payload, "target")
    if target not in {"page", "element"}:
        raise ValueError("scroll `target` must be `page` or `element`.")

    direction = adapter._payload_str(payload, "direction")
    distance = adapter._payload_float(payload, "distance")
    if distance <= 0:
        raise ValueError("scroll `distance` must be greater than 0.")
    behavior = payload.get("behavior", "auto")
    if behavior not in {"auto", "smooth"}:
        raise ValueError("scroll `behavior` must be `auto` or `smooth`.")

    delta_x, delta_y = adapter._scroll_delta(direction, distance)
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
        adapter._settle_scroll(page, behavior)
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
        _invalidate_ocr_session(ocr_session, "scroll")
        return _step_execution_outcome(status="passed", score_value=1.0)

    if adapter._uses_visual_locator(payload):
        loc = adapter._resolve_interaction_target(
            page,
            payload,
            template_contexts=template_contexts,
            ocr_session=ocr_session,
        )
        point = adapter._resolve_visual_anchor_point(payload, loc)
        page.mouse.move(point.x, point.y)
        page.mouse.wheel(delta_x, delta_y)
        adapter._settle_scroll(page, behavior)
        if adapter._is_ocr_locator(payload):
            result_metadata_json, actual_artifact = _build_ocr_action_evidence(
                loc=loc,
                case_run_id=case_run_id,
                step=step,
            )
        else:
            result_metadata_json, actual_artifact = {}, None
        _invalidate_ocr_session(ocr_session, "scroll")
        return _step_execution_outcome(
            status="passed",
            score_value=1.0,
            actual_artifact=actual_artifact,
            result_metadata_json=result_metadata_json,
        )

    selector = adapter._payload_str(payload, "selector")
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
    adapter._settle_scroll(page, behavior)
    after = locator.evaluate(
        "element => ({ left: element.scrollLeft, top: element.scrollTop })"
    )
    if before == after:
        raise RuntimeError(
            "Element scroll did not move; ensure the target element can scroll in the requested direction."
        )
    _invalidate_ocr_session(ocr_session, "scroll")
    return _step_execution_outcome(status="passed", score_value=1.0)


def execute_long_press(
    adapter,
    page,
    *,
    step,
    case_run_id: int,
    timeout_ms: int,
    template_contexts,
    ocr_session=None,
    **_kwargs,
):
    payload = step.payload_json or {}
    duration_ms = adapter._payload_int(payload, "duration_ms")
    if duration_ms <= 0:
        raise ValueError("long_press `duration_ms` must be greater than 0.")
    button = payload.get("button", "left")
    if button != "left":
        raise ValueError("long_press `button` currently only supports `left`.")

    result_metadata_json = {}
    actual_artifact = None
    if adapter._uses_visual_locator(payload):
        loc = adapter._resolve_interaction_target(
            page,
            payload,
            template_contexts=template_contexts,
            ocr_session=ocr_session,
        )
        point = adapter._resolve_visual_anchor_point(payload, loc)
        cx, cy = point.x, point.y
        if adapter._is_ocr_locator(payload):
            result_metadata_json, actual_artifact = _build_ocr_action_evidence(
                loc=loc,
                case_run_id=case_run_id,
                step=step,
            )
    else:
        selector = adapter._payload_str(payload, "selector")
        locator = page.locator(selector)
        locator.wait_for(state="visible", timeout=timeout_ms)
        element = locator.element_handle(timeout=timeout_ms)
        if element is None:
            raise RuntimeError("long_press target element was not found.")
        element.scroll_into_view_if_needed(timeout=timeout_ms)
        box = element.bounding_box()
        if box is None or box["width"] <= 0 or box["height"] <= 0:
            raise RuntimeError("long_press target element has no visible bounding box.")
        cx, cy = box["x"] + (box["width"] / 2), box["y"] + (box["height"] / 2)

    page.mouse.move(cx, cy)
    page.mouse.down(button=button)
    page.wait_for_timeout(duration_ms)
    page.mouse.up(button=button)
    _invalidate_ocr_session(ocr_session, "long_press")
    return _step_execution_outcome(
        status="passed",
        score_value=1.0,
        actual_artifact=actual_artifact,
        result_metadata_json=result_metadata_json,
    )
