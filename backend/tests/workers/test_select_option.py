from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.services.execution_readiness import inspect_execution_step_issues
from app.services.step_payload_validator import validate_step_payload
from app.workers.browser_ocr_actions import (
    OcrActionVerificationError,
    execute_ocr_select_option,
)
from app.workers.browser_step_registry import get_step_handler
from app.workers.ocr_engine import OcrEngineError
from app.workers.ocr_targeting import OcrTargetingError
from app.workers.ocr_types import (
    OcrCoordinateSet,
    OcrErrorCode,
    OcrPoint,
    OcrRatioRect,
    OcrRect,
    OcrTargetCandidate,
    OcrTargetResolution,
    OcrTargetSpec,
    OcrTextElement,
)

pytestmark = pytest.mark.ocr_fake


def _target_payload(
    text: str,
    *,
    role: str,
    action_point: str = "text_center",
    occurrence: int = 1,
) -> dict[str, object]:
    return {
        "text": text,
        "role": role,
        "action_point": action_point,
        "occurrence": occurrence,
        "language": "en",
        "min_confidence": 0.5,
        "min_score": 0.5,
    }


def _payload(
    *,
    occurrence: int = 1,
    verify_selected: bool = True,
) -> dict[str, object]:
    return {
        "field_target": _target_payload(
            "Country",
            role="input",
            action_point="associated_control",
        ),
        "option_target": _target_payload(
            "China",
            role="menu_item",
            occurrence=occurrence,
        ),
        "verify_selected": verify_selected,
    }


def _coordinates(rect: OcrRect) -> OcrCoordinateSet:
    return OcrCoordinateSet(
        pixel_rect=rect,
        ratio_rect=OcrRatioRect(
            x=rect.x / 1000.0,
            y=rect.y / 1000.0,
            width=rect.width / 1000.0,
            height=rect.height / 1000.0,
        ),
        viewport_css_rect=rect,
        document_css_rect=rect,
    )


def _resolution(
    target: OcrTargetSpec,
    *,
    text: str,
    rect: OcrRect,
    associated_control_rect: OcrRect | None = None,
) -> OcrTargetResolution:
    element = OcrTextElement(
        element_id=f"{text}-{rect.y}",
        text=text,
        confidence=0.98,
        line_ids=(),
        coordinates=_coordinates(rect),
        role="input" if associated_control_rect is not None else "menu_item",
        role_confidence=0.98,
        associated_control_rect=associated_control_rect,
        association_confidence=0.98 if associated_control_rect is not None else 0.0,
    )
    candidate = OcrTargetCandidate(
        element=element,
        text_score=1.0,
        confidence_score=0.98,
        role_score=1.0,
        relation_score=1.0,
        distance_score=1.0,
        variant_consistency_score=1.0,
        total_score=0.99,
    )
    return OcrTargetResolution(
        status="resolved",
        target=target,
        selected_candidate=candidate,
        candidates=(candidate,),
        scanned_tile_count=1,
        elapsed_ms=2.0,
    )


def _targeting_error(target: OcrTargetSpec) -> OcrTargetingError:
    return OcrTargetingError(
        OcrTargetResolution(
            status="rejected",
            target=target,
            error_code=OcrErrorCode.OCR_TARGET_NOT_FOUND,
            error_message="Target did not appear.",
            scanned_tile_count=1,
        )
    )


@dataclass
class _Mouse:
    clicks: list[tuple[float, float]] = field(default_factory=list)

    def click(self, x: float, y: float) -> None:
        self.clicks.append((x, y))


@dataclass
class _Page:
    mouse: _Mouse = field(default_factory=_Mouse)
    waits: list[float] = field(default_factory=list)

    def wait_for_timeout(self, timeout_ms: float) -> None:
        self.waits.append(timeout_ms)


class _Session:
    def __init__(
        self,
        *,
        action_results: list[OcrTargetResolution | Exception],
        verification_error: Exception | None = None,
        verification_resolution: OcrTargetResolution | None = None,
    ) -> None:
        self.action_results = action_results
        self.verification_error = verification_error
        self.verification_resolution = verification_resolution
        self.action_targets: list[OcrTargetSpec] = []
        self.verification_targets: list[OcrTargetSpec] = []
        self.invalidations: list[str] = []

    def resolve_for_action(self, target: OcrTargetSpec) -> OcrTargetResolution:
        self.action_targets.append(target)
        result = self.action_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def resolve(self, target: OcrTargetSpec) -> OcrTargetResolution:
        self.verification_targets.append(target)
        if self.verification_error is not None:
            raise self.verification_error
        if self.verification_resolution is not None:
            return self.verification_resolution.model_copy(update={"target": target})
        return _resolution(
            target,
            text=target.text,
            rect=OcrRect(x=130, y=25, width=80, height=20),
        )

    def invalidate(self, reason: str) -> None:
        self.invalidations.append(reason)


def _action_results(
    payload: dict[str, object],
) -> list[OcrTargetResolution]:
    field_target = OcrTargetSpec.model_validate(payload["field_target"])
    option_target = OcrTargetSpec.model_validate(payload["option_target"])
    return [
        _resolution(
            field_target,
            text="Country",
            rect=OcrRect(x=20, y=20, width=60, height=20),
            associated_control_rect=OcrRect(x=100, y=15, width=180, height=40),
        ),
        _resolution(
            option_target,
            text="China",
            rect=OcrRect(x=110, y=90, width=120, height=30),
        ),
    ]


def test_validator_accepts_only_two_pure_ocr_targets() -> None:
    payload = _payload()

    validate_step_payload(
        cast(Session, None),
        workspace_id=1,
        item={
            "step_type": "select_option",
            "template_id": None,
            "payload_json": payload,
        },
        allow_component_call=False,
    )

    assert "selector" not in payload
    assert "template_id" not in payload
    assert get_step_handler("select_option") is not None


def test_readiness_accepts_valid_select_and_blocks_fallback_payload() -> None:
    valid_step = SimpleNamespace(
        step_type="select_option",
        step_name="Select country",
        template_id=None,
        payload_json=_payload(),
    )
    invalid_step = SimpleNamespace(
        step_type="select_option",
        step_name="Unsafe select",
        template_id=None,
        payload_json=_payload() | {"selector": "#country"},
    )

    assert (
        inspect_execution_step_issues(
            cast(Session, None),
            workspace_id=1,
            step=valid_step,
            route_path="/cases",
        )
        == []
    )
    issues = inspect_execution_step_issues(
        cast(Session, None),
        workspace_id=1,
        step=invalid_step,
        route_path="/cases",
    )

    assert [issue["code"] for issue in issues] == ["STEP_CONFIGURATION_INVALID"]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.pop("field_target"),
        lambda payload: payload.update({"selector": "#country"}),
        lambda payload: payload.update({"locator": "selector"}),
        lambda payload: payload.update({"template_id": 3}),
        lambda payload: payload["option_target"].update({"selector": ".option"}),
        lambda payload: payload.update({"verify_selected": "yes"}),
    ],
)
def test_validator_rejects_missing_or_fallback_select_payloads(
    mutation: Callable[[dict], object],
) -> None:
    payload = _payload()
    mutation(payload)

    with pytest.raises(ApiError) as exc_info:
        validate_step_payload(
            cast(Session, None),
            workspace_id=1,
            item={
                "step_type": "select_option",
                "template_id": None,
                "payload_json": payload,
            },
            allow_component_call=False,
        )

    assert exc_info.value.code == "STEP_CONFIGURATION_INVALID"


def test_validator_rejects_top_level_template_fallback() -> None:
    with pytest.raises(ApiError) as exc_info:
        validate_step_payload(
            cast(Session, None),
            workspace_id=1,
            item={
                "step_type": "select_option",
                "template_id": 7,
                "payload_json": _payload(),
            },
            allow_component_call=False,
        )

    assert exc_info.value.code == "STEP_CONFIGURATION_INVALID"


def test_select_option_clicks_field_then_option_and_verifies_visible_text() -> None:
    payload = _payload()
    page = _Page()
    session = _Session(action_results=_action_results(payload))

    result = execute_ocr_select_option(
        page,
        ocr_session=session,
        payload=payload,
        timeout_ms=15000,
    )

    assert page.mouse.clicks == [(190.0, 35.0), (170.0, 105.0)]
    assert session.invalidations == [
        "select_option_field_click",
        "select_option_option_click",
    ]
    assert [target.text for target in session.action_targets] == ["Country", "China"]
    assert session.verification_targets[0].scope == "viewport"
    assert session.verification_targets[0].text == "China"
    assert result.verification_resolution is not None
    assert result.field_verification_rect == OcrRect(
        x=100,
        y=15,
        width=180,
        height=40,
    )


def test_select_option_uses_explicit_occurrence_for_repeated_options() -> None:
    payload = _payload(occurrence=2, verify_selected=False)
    page = _Page()
    session = _Session(action_results=_action_results(payload))

    result = execute_ocr_select_option(
        page,
        ocr_session=session,
        payload=payload,
        timeout_ms=15000,
    )

    assert session.action_targets[1].occurrence == 2
    assert result.verification_resolution is None


def test_select_option_stops_when_menu_option_does_not_appear() -> None:
    payload = _payload()
    results = _action_results(payload)
    option_target = OcrTargetSpec.model_validate(payload["option_target"])
    session = _Session(
        action_results=[results[0], _targeting_error(option_target)]
    )
    page = _Page()

    with pytest.raises(OcrTargetingError) as exc_info:
        execute_ocr_select_option(
            page,
            ocr_session=session,
            payload=payload,
            timeout_ms=15000,
        )

    assert exc_info.value.code == OcrErrorCode.OCR_TARGET_NOT_FOUND
    assert page.mouse.clicks == [(190.0, 35.0)]


def test_select_option_field_revalidation_failure_performs_no_click() -> None:
    payload = _payload()
    field_target = OcrTargetSpec.model_validate(payload["field_target"])
    session = _Session(
        action_results=[
            OcrTargetingError(
                OcrTargetResolution(
                    status="rejected",
                    target=field_target,
                    error_code=OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED,
                    error_message="Field changed before its action.",
                )
            )
        ]
    )
    page = _Page()

    with pytest.raises(OcrTargetingError) as exc_info:
        execute_ocr_select_option(
            page,
            ocr_session=session,
            payload=payload,
            timeout_ms=15000,
        )

    assert exc_info.value.code == OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED
    assert page.mouse.clicks == []


def test_select_option_option_revalidation_failure_performs_no_option_click() -> None:
    payload = _payload()
    results = _action_results(payload)
    option_target = OcrTargetSpec.model_validate(payload["option_target"])
    session = _Session(
        action_results=[
            results[0],
            OcrTargetingError(
                OcrTargetResolution(
                    status="rejected",
                    target=option_target,
                    error_code=OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED,
                    error_message="Option changed before its action.",
                )
            ),
        ]
    )
    page = _Page()

    with pytest.raises(OcrTargetingError) as exc_info:
        execute_ocr_select_option(
            page,
            ocr_session=session,
            payload=payload,
            timeout_ms=15000,
        )

    assert exc_info.value.code == OcrErrorCode.OCR_ACTION_REVALIDATION_FAILED
    assert page.mouse.clicks == [(190.0, 35.0)]


def test_select_option_verification_accepts_only_field_region_candidate() -> None:
    payload = _payload()
    verification_target = OcrTargetSpec.model_validate(payload["option_target"])
    field_candidate = _resolution(
        verification_target,
        text="China",
        rect=OcrRect(x=135, y=25, width=70, height=20),
    ).selected_candidate
    menu_candidate = _resolution(
        verification_target,
        text="China",
        rect=OcrRect(x=120, y=92, width=70, height=20),
    ).selected_candidate
    assert field_candidate is not None
    assert menu_candidate is not None
    verification_resolution = OcrTargetResolution(
        status="resolved",
        target=verification_target,
        selected_candidate=menu_candidate,
        candidates=(menu_candidate, field_candidate),
        scanned_tile_count=1,
        elapsed_ms=2.0,
    )
    session = _Session(
        action_results=_action_results(payload),
        verification_resolution=verification_resolution,
    )

    result = execute_ocr_select_option(
        _Page(),
        ocr_session=session,
        payload=payload,
        timeout_ms=15000,
    )

    assert result.verification_resolution is not None
    assert (
        result.verification_resolution.selected_candidate
        == field_candidate
    )
    assert result.verification_resolution.candidates == (field_candidate,)


def test_select_option_verification_rejects_menu_and_other_field_text() -> None:
    payload = _payload()
    verification_target = OcrTargetSpec.model_validate(payload["option_target"])
    menu_candidate = _resolution(
        verification_target,
        text="China",
        rect=OcrRect(x=120, y=92, width=70, height=20),
    ).selected_candidate
    other_field_candidate = _resolution(
        verification_target,
        text="China",
        rect=OcrRect(x=430, y=25, width=70, height=20),
    ).selected_candidate
    assert menu_candidate is not None
    assert other_field_candidate is not None
    verification_resolution = OcrTargetResolution(
        status="resolved",
        target=verification_target,
        selected_candidate=menu_candidate,
        candidates=(menu_candidate, other_field_candidate),
        scanned_tile_count=1,
        elapsed_ms=2.0,
    )
    session = _Session(
        action_results=_action_results(payload),
        verification_resolution=verification_resolution,
    )

    with pytest.raises(OcrActionVerificationError) as exc_info:
        execute_ocr_select_option(
            _Page(),
            ocr_session=session,
            payload=payload,
            timeout_ms=15000,
        )

    assert exc_info.value.code == OcrErrorCode.OCR_ACTION_VERIFICATION_FAILED


def test_select_option_maps_post_click_ocr_failure_to_verification_code() -> None:
    payload = _payload()
    option_target = OcrTargetSpec.model_validate(payload["option_target"])
    session = _Session(
        action_results=_action_results(payload),
        verification_error=_targeting_error(option_target),
    )

    with pytest.raises(OcrActionVerificationError) as exc_info:
        execute_ocr_select_option(
            _Page(),
            ocr_session=session,
            payload=payload,
            timeout_ms=15000,
        )

    assert exc_info.value.code == OcrErrorCode.OCR_ACTION_VERIFICATION_FAILED


def test_select_option_preserves_engine_failure_during_verification() -> None:
    payload = _payload()
    session = _Session(
        action_results=_action_results(payload),
        verification_error=OcrEngineError(
            OcrErrorCode.OCR_MODEL_UNAVAILABLE,
            "OCR model is unavailable.",
        ),
    )

    with pytest.raises(OcrEngineError) as exc_info:
        execute_ocr_select_option(
            _Page(),
            ocr_session=session,
            payload=payload,
            timeout_ms=15000,
        )

    assert exc_info.type is OcrEngineError
    assert exc_info.value.code == OcrErrorCode.OCR_MODEL_UNAVAILABLE
