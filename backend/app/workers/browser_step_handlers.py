from __future__ import annotations

from decimal import Decimal


def _step_execution_outcome(**kwargs):
    from app.workers.browser import StepExecutionOutcome

    return StepExecutionOutcome(**kwargs)


def execute_wait(adapter, page, *, step, timeout_ms: int, **_kwargs):
    payload = step.payload_json or {}
    wait_ms = adapter._payload_int(payload, "ms")
    if wait_ms < 0:
        raise ValueError("wait step `ms` must be greater than or equal to 0.")
    page.wait_for_timeout(wait_ms)
    return _step_execution_outcome(status="passed", score_value=1.0)


def execute_navigate(adapter, page, *, step, base_url: str, timeout_ms: int, **_kwargs):
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
    return _step_execution_outcome(status="passed", score_value=1.0)


def execute_click(
    adapter,
    page,
    *,
    step,
    timeout_ms: int,
    template_contexts,
    **_kwargs,
):
    payload = step.payload_json or {}
    if adapter._uses_visual_locator(payload):
        loc = adapter._resolve_interaction_target(
            page, payload, template_contexts=template_contexts
        )
        point = adapter._resolve_visual_anchor_point(payload, loc)
        page.mouse.click(point.x, point.y)
    else:
        selector = adapter._payload_str(payload, "selector")
        page.locator(selector).click(timeout=timeout_ms)
    return _step_execution_outcome(status="passed", score_value=1.0)


def execute_input(
    adapter,
    page,
    *,
    step,
    timeout_ms: int,
    template_contexts,
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
    if adapter._uses_visual_locator(payload):
        loc = adapter._resolve_interaction_target(
            page, payload, template_contexts=template_contexts
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
    return _step_execution_outcome(status="passed", score_value=1.0)


def execute_conditional_branch(
    adapter,
    page,
    *,
    step,
    template_contexts,
    **_kwargs,
):
    selected = adapter._select_matching_branch(
        page,
        payload=step.payload_json or {},
        template_contexts=template_contexts,
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
    **_kwargs,
):
    payload = step.payload_json or {}
    selector = adapter._payload_str(payload, "selector")
    expected_text = adapter._payload_str(payload, "expected_text")
    match_mode = payload.get("match_mode", "contains")
    if match_mode not in {"exact", "contains"}:
        raise ValueError(
            "ocr_assert `match_mode` must be either `exact` or `contains`."
        )
    case_sensitive = payload.get("case_sensitive", False)
    if not isinstance(case_sensitive, bool):
        raise ValueError("ocr_assert `case_sensitive` must be boolean.")
    image_bytes = page.locator(selector).screenshot(type="png", timeout=timeout_ms)
    outcome = adapter._vision_adapter.assert_ocr(
        image_png_bytes=image_bytes,
        image_file_name=f"case-run-{case_run_id}-step-{step.step_no}-ocr.png",
        expected_text=expected_text,
        match_mode=match_mode,
        case_sensitive=case_sensitive,
    )
    return _step_execution_outcome(
        status=outcome.status,
        score_value=outcome.score_value,
        error_message=outcome.error_message,
        actual_artifact=outcome.actual_artifact,
    )


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
    timeout_ms: int,
    template_contexts,
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
        return _step_execution_outcome(status="passed", score_value=1.0)

    if adapter._uses_visual_locator(payload):
        loc = adapter._resolve_interaction_target(
            page, payload, template_contexts=template_contexts
        )
        point = adapter._resolve_visual_anchor_point(payload, loc)
        page.mouse.move(point.x, point.y)
        page.mouse.wheel(delta_x, delta_y)
        adapter._settle_scroll(page, behavior)
        return _step_execution_outcome(status="passed", score_value=1.0)

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
    return _step_execution_outcome(status="passed", score_value=1.0)


def execute_long_press(
    adapter,
    page,
    *,
    step,
    timeout_ms: int,
    template_contexts,
    **_kwargs,
):
    payload = step.payload_json or {}
    duration_ms = adapter._payload_int(payload, "duration_ms")
    if duration_ms <= 0:
        raise ValueError("long_press `duration_ms` must be greater than 0.")
    button = payload.get("button", "left")
    if button != "left":
        raise ValueError("long_press `button` currently only supports `left`.")

    if adapter._uses_visual_locator(payload):
        loc = adapter._resolve_interaction_target(
            page, payload, template_contexts=template_contexts
        )
        point = adapter._resolve_visual_anchor_point(payload, loc)
        cx, cy = point.x, point.y
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
    return _step_execution_outcome(status="passed", score_value=1.0)
