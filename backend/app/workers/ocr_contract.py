from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.workers.ocr_types import (
    OcrAssertionMode,
    OcrAssertionScope,
    OcrTargetScope,
    OcrTargetSpec,
)


class OcrContractError(ValueError):
    """Raised when an OCR payload cannot be normalized safely."""


@dataclass(frozen=True, slots=True)
class NormalizedOcrAssertPayload:
    target: OcrTargetSpec
    scope: OcrAssertionScope
    assertion: OcrAssertionMode
    expected_count: int | None
    selector: str | None
    is_legacy: bool


@dataclass(frozen=True, slots=True)
class NormalizedSelectOptionPayload:
    field_target: OcrTargetSpec
    option_target: OcrTargetSpec
    verify_selected: bool


_SELECT_OPTION_FALLBACK_FIELDS = frozenset(
    {
        "locator",
        "selector",
        "template_id",
        "threshold",
        "anchor_x_ratio",
        "anchor_y_ratio",
        "ocr_target",
        "ocr_text",
        "ocr_match_mode",
        "ocr_case_sensitive",
        "ocr_occurrence",
    }
)


def normalize_ocr_target_payload(payload: Mapping[str, object]) -> OcrTargetSpec:
    """Normalize nested or legacy locator fields into one target contract.

    A present ``ocr_target`` key is authoritative, including when its value is
    invalid. Legacy fields are only considered when the nested key is absent.
    """
    if "ocr_target" in payload:
        nested = payload["ocr_target"]
        if not isinstance(nested, Mapping):
            raise OcrContractError("ocr_target must be an object.")
        return _parse_target(dict(nested))

    legacy_text = payload.get("ocr_text")
    if not isinstance(legacy_text, str) or not legacy_text.strip():
        raise OcrContractError(
            "OCR locator requires ocr_target.text or legacy ocr_text."
        )

    legacy_target: dict[str, object] = {
        "text": legacy_text,
        "match_mode": payload.get("ocr_match_mode", "contains"),
        "case_sensitive": payload.get("ocr_case_sensitive", False),
        "occurrence": payload.get("ocr_occurrence", 1),
        "scope": "viewport",
    }
    return _parse_target(legacy_target)


def normalize_select_option_payload(
    payload: Mapping[str, object],
) -> NormalizedSelectOptionPayload:
    """Validate a select action that is exclusively driven by two OCR targets."""
    fallback_fields = sorted(_SELECT_OPTION_FALLBACK_FIELDS.intersection(payload))
    if fallback_fields:
        raise OcrContractError(
            "select_option does not allow selector or template fallback fields: "
            f"{', '.join(fallback_fields)}."
        )

    field_target = payload.get("field_target")
    if not isinstance(field_target, Mapping):
        raise OcrContractError("select_option field_target must be an object.")
    option_target = payload.get("option_target")
    if not isinstance(option_target, Mapping):
        raise OcrContractError("select_option option_target must be an object.")

    verify_selected = payload.get("verify_selected", True)
    if not isinstance(verify_selected, bool):
        raise OcrContractError("select_option verify_selected must be boolean.")

    return NormalizedSelectOptionPayload(
        field_target=_parse_target(dict(field_target)),
        option_target=_parse_target(dict(option_target)),
        verify_selected=verify_selected,
    )


def normalize_ocr_assert_payload(
    payload: Mapping[str, object],
) -> NormalizedOcrAssertPayload:
    """Normalize pure OCR and selector-based legacy assertion payloads."""
    selector = _optional_non_empty_string(payload.get("selector"), field="selector")
    nested_target: Mapping[str, object] | None = None
    if "ocr_target" in payload:
        nested = payload["ocr_target"]
        if not isinstance(nested, Mapping):
            raise OcrContractError("ocr_target must be an object.")
        nested_target = nested

    raw_scope = payload.get("scope")
    if raw_scope is None:
        if selector is not None:
            scope: OcrAssertionScope = "element_legacy"
        elif nested_target is not None and nested_target.get("scope") == "page":
            scope = "page"
        else:
            scope = "viewport"
    elif raw_scope in {"viewport", "page", "element_legacy"}:
        scope = raw_scope
    else:
        raise OcrContractError(
            "OCR assertion scope must be viewport, page, or element_legacy."
        )

    if scope == "element_legacy" and selector is None:
        raise OcrContractError(
            "OCR assertion scope element_legacy requires selector."
        )

    assertion = _normalize_assertion(payload.get("assertion"))
    expected_count = _normalize_expected_count(
        payload.get("expected_count"),
        assertion=assertion,
    )

    if nested_target is not None:
        target_data = dict(nested_target)
        target_scope = _target_scope_for_assertion(scope)
        nested_scope = target_data.get("scope")
        if nested_scope is not None and nested_scope != target_scope:
            raise OcrContractError(
                "OCR assertion scope conflicts with ocr_target.scope."
            )
        target_data.setdefault("scope", target_scope)
        target = _parse_target(target_data)
        _validate_assertion_target(assertion, target)
        return NormalizedOcrAssertPayload(
            target=target,
            scope=scope,
            assertion=assertion,
            expected_count=expected_count,
            selector=selector,
            is_legacy=scope == "element_legacy",
        )

    if scope != "element_legacy":
        raise OcrContractError(
            "Pure OCR assertion requires an ocr_target object."
        )

    expected_text = payload.get("expected_text")
    if not isinstance(expected_text, str) or not expected_text.strip():
        raise OcrContractError(
            "Legacy OCR assertion requires expected_text."
        )
    match_mode = payload.get("match_mode", "contains")
    if match_mode not in {"exact", "contains"}:
        raise OcrContractError(
            "Legacy OCR assertion match_mode must be exact or contains."
        )
    target = _parse_target(
        {
            "text": expected_text,
            "match_mode": match_mode,
            "case_sensitive": payload.get("case_sensitive", False),
            "scope": "viewport",
        }
    )
    _validate_assertion_target(assertion, target)
    return NormalizedOcrAssertPayload(
        target=target,
        scope=scope,
        assertion=assertion,
        expected_count=expected_count,
        selector=selector,
        is_legacy=True,
    )


def normalize_ocr_branch_condition(
    condition: Mapping[str, object],
) -> OcrTargetSpec:
    """Normalize new and legacy ``ocr_text_visible`` condition targets."""
    if "ocr_target" in condition or "ocr_text" in condition:
        return normalize_ocr_target_payload(condition)

    expected_text = condition.get("expected_text")
    if not isinstance(expected_text, str) or not expected_text.strip():
        raise OcrContractError(
            "ocr_text_visible requires ocr_target or legacy expected_text."
        )
    return normalize_ocr_target_payload(
        {
            "ocr_text": expected_text,
            "ocr_match_mode": condition.get("match_mode", "contains"),
            "ocr_case_sensitive": condition.get("case_sensitive", False),
            "ocr_occurrence": 1,
        }
    )


def _target_scope_for_assertion(scope: OcrAssertionScope) -> OcrTargetScope:
    if scope == "page":
        return "page"
    return "viewport"


def _optional_non_empty_string(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise OcrContractError(f"{field} must be a non-empty string.")
    return value.strip()


def _normalize_assertion(value: object) -> OcrAssertionMode:
    if value is None:
        return "present"
    if value not in {"present", "absent", "count", "relation"}:
        raise OcrContractError(
            "OCR assertion must be present, absent, count, or relation."
        )
    return value


def _normalize_expected_count(
    value: object,
    *,
    assertion: OcrAssertionMode,
) -> int | None:
    if assertion != "count":
        if value is not None:
            raise OcrContractError(
                "expected_count is only supported for count assertions."
            )
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OcrContractError(
            "Count OCR assertion requires a non-negative integer expected_count."
        )
    return value


def _validate_assertion_target(
    assertion: OcrAssertionMode,
    target: OcrTargetSpec,
) -> None:
    if assertion == "relation" and target.relation is None:
        raise OcrContractError(
            "Relation OCR assertion requires ocr_target.relation."
        )


def _parse_target(target_data: Mapping[str, Any]) -> OcrTargetSpec:
    try:
        return OcrTargetSpec.model_validate(dict(target_data))
    except ValidationError as exc:
        raise OcrContractError(_format_validation_error(exc)) from exc


def _format_validation_error(exc: ValidationError) -> str:
    first_error = exc.errors(include_url=False)[0]
    location = ".".join(str(part) for part in first_error["loc"])
    message = str(first_error["msg"])
    return f"Invalid OCR target field {location}: {message}"
