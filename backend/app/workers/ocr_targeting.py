from __future__ import annotations

import re
import time
import unicodedata
from collections.abc import Iterable
from difflib import SequenceMatcher

from app.workers.ocr_types import (
    OcrElementRelation,
    OcrErrorCode,
    OcrPageSnapshot,
    OcrTargetCandidate,
    OcrTargetResolution,
    OcrTargetSpec,
    OcrTextElement,
)

_FUZZY_CANDIDATE_FLOOR = 0.45
_SCORE_WEIGHTS = {
    "text": 0.38,
    "confidence": 0.22,
    "role": 0.14,
    "relation": 0.12,
    "distance": 0.07,
    "variant": 0.07,
}


class OcrTargetingError(RuntimeError):
    """A typed, safety-preserving OCR target rejection."""

    def __init__(self, resolution: OcrTargetResolution) -> None:
        if resolution.error_code is None or resolution.error_message is None:
            raise ValueError("OCR targeting errors require an error code and message.")
        self.resolution = resolution
        self.code = resolution.error_code
        self.candidates = resolution.candidates
        super().__init__(
            f"{resolution.error_code.value}: {resolution.error_message}"
        )


def normalize_ocr_text(value: str, *, case_sensitive: bool) -> str:
    """Normalize OCR text using the contract's NFKC and whitespace rules."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = " ".join(normalized.split())
    return normalized if case_sensitive else normalized.casefold()


def resolve_ocr_target(
    snapshot: OcrPageSnapshot,
    target: OcrTargetSpec,
    *,
    scanned_tile_count: int = 1,
) -> OcrTargetResolution:
    """Resolve one target or raise a typed rejection without guessing."""
    started_at = time.perf_counter()
    text_matches = _text_matches(snapshot, target)
    if not text_matches:
        _reject(
            target,
            OcrErrorCode.OCR_TARGET_NOT_FOUND,
            (
                f"No OCR text candidate matched `{target.text}` using "
                f"{target.match_mode} matching."
            ),
            (),
            scanned_tile_count,
            started_at,
        )

    confident_matches = [
        match for match in text_matches if match[0].confidence >= target.min_confidence
    ]
    if not confident_matches:
        highest_confidence = max(element.confidence for element, _ in text_matches)
        _reject(
            target,
            OcrErrorCode.OCR_CONFIDENCE_LOW,
            (
                f"Matched {len(text_matches)} OCR candidate(s), but highest "
                f"confidence {highest_confidence:.4f} is below "
                f"min_confidence {target.min_confidence:.4f}."
            ),
            _score_candidates(snapshot, target, text_matches),
            scanned_tile_count,
            started_at,
        )

    role_matches = confident_matches
    if target.role != "any":
        role_matches = [
            match for match in confident_matches if match[0].role == target.role
        ]
        if not role_matches:
            observed_roles = ", ".join(
                sorted({element.role for element, _ in confident_matches})
            )
            _reject(
                target,
                OcrErrorCode.OCR_ROLE_NOT_SATISFIED,
                (
                    f"Matched {len(confident_matches)} confident candidate(s), "
                    f"but none has role `{target.role}`; observed roles: "
                    f"{observed_roles or 'none'}."
                ),
                _score_candidates(snapshot, target, confident_matches),
                scanned_tile_count,
                started_at,
            )

    relation_matches = _relation_matches(snapshot, target, role_matches)
    if target.relation is not None and not relation_matches:
        _reject(
            target,
            OcrErrorCode.OCR_RELATION_NOT_SATISFIED,
            (
                f"Matched {len(role_matches)} candidate(s), but none satisfies "
                f"relation `{target.relation.type}` to "
                f"`{target.relation.anchor_text}` within distance ratio "
                f"{target.relation.max_distance_ratio:.4f}."
            ),
            _score_candidates(snapshot, target, role_matches),
            scanned_tile_count,
            started_at,
        )

    actionable_matches = relation_matches
    if target.action_point == "associated_control":
        non_ambiguous = [
            match
            for match in actionable_matches
            if not match[0].association_ambiguous
        ]
        if not non_ambiguous:
            _reject(
                target,
                OcrErrorCode.OCR_TARGET_AMBIGUOUS,
                "All matching OCR elements have ambiguous associated controls.",
                _score_candidates(snapshot, target, actionable_matches),
                scanned_tile_count,
                started_at,
            )
        actionable_matches = [
            match
            for match in non_ambiguous
            if match[0].associated_control_rect is not None
        ]
        if not actionable_matches:
            _reject(
                target,
                OcrErrorCode.OCR_RELATION_NOT_SATISFIED,
                "No matching OCR element has a safely associated visual control.",
                _score_candidates(snapshot, target, non_ambiguous),
                scanned_tile_count,
                started_at,
            )

    candidates = _score_candidates(snapshot, target, actionable_matches)
    if target.occurrence > len(candidates):
        _reject(
            target,
            OcrErrorCode.OCR_TARGET_NOT_FOUND,
            (
                f"OCR target matched {len(candidates)} candidate(s), but "
                f"occurrence {target.occurrence} was requested."
            ),
            candidates,
            scanned_tile_count,
            started_at,
        )

    selected = candidates[target.occurrence - 1]
    if selected.total_score < target.min_score:
        _reject(
            target,
            OcrErrorCode.OCR_CONFIDENCE_LOW,
            (
                f"Selected OCR candidate score {selected.total_score:.4f} is "
                f"below min_score {target.min_score:.4f}."
            ),
            candidates,
            scanned_tile_count,
            started_at,
        )

    if target.occurrence == 1 and len(candidates) > 1:
        score_margin = selected.total_score - candidates[1].total_score
        if score_margin < target.ambiguity_margin:
            _reject(
                target,
                OcrErrorCode.OCR_TARGET_AMBIGUOUS,
                (
                    f"Top OCR candidate score margin {score_margin:.4f} is below "
                    f"ambiguity_margin {target.ambiguity_margin:.4f}; set a "
                    "role, relation, or explicit occurrence."
                ),
                candidates,
                scanned_tile_count,
                started_at,
            )

    return OcrTargetResolution(
        status="resolved",
        target=target,
        selected_candidate=selected,
        candidates=candidates,
        scanned_tile_count=scanned_tile_count,
        elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
    )


def _text_matches(
    snapshot: OcrPageSnapshot,
    target: OcrTargetSpec,
) -> list[tuple[OcrTextElement, float]]:
    matches: list[tuple[OcrTextElement, float]] = []
    normalized_target = normalize_ocr_text(
        target.text,
        case_sensitive=target.case_sensitive,
    )
    regex = _compile_regex(target) if target.match_mode == "regex" else None
    for element in snapshot.elements:
        normalized_actual = normalize_ocr_text(
            element.text,
            case_sensitive=target.case_sensitive,
        )
        score = _text_score(
            normalized_actual,
            normalized_target,
            target=target,
            regex=regex,
        )
        if score is not None:
            matches.append((element, score))
    return matches


def _compile_regex(target: OcrTargetSpec) -> re.Pattern[str]:
    pattern = " ".join(unicodedata.normalize("NFKC", target.text).split())
    flags = 0 if target.case_sensitive else re.IGNORECASE
    return re.compile(pattern, flags)


def _text_score(
    actual: str,
    expected: str,
    *,
    target: OcrTargetSpec,
    regex: re.Pattern[str] | None,
) -> float | None:
    if target.match_mode == "exact":
        return 1.0 if actual == expected else None
    if target.match_mode == "contains":
        if expected not in actual:
            return None
        coverage = len(expected) / max(len(actual), 1)
        return _clamp(0.85 + coverage * 0.15)
    if target.match_mode == "regex":
        if regex is None:
            return None
        matched = regex.search(actual)
        if matched is None:
            return None
        coverage = (matched.end() - matched.start()) / max(len(actual), 1)
        return _clamp(0.85 + coverage * 0.15)

    similarity = SequenceMatcher(None, expected, actual, autojunk=False).ratio()
    return similarity if similarity >= _FUZZY_CANDIDATE_FLOOR else None


def _relation_matches(
    snapshot: OcrPageSnapshot,
    target: OcrTargetSpec,
    matches: Iterable[tuple[OcrTextElement, float]],
) -> list[tuple[OcrTextElement, float]]:
    materialized = list(matches)
    if target.relation is None:
        return materialized

    elements_by_id = {element.element_id: element for element in snapshot.elements}
    valid_relations = {
        relation.source_element_id
        for relation in snapshot.relations
        if relation.type == target.relation.type
        and relation.distance_ratio <= target.relation.max_distance_ratio
        and (
            anchor := elements_by_id.get(relation.target_element_id)
        )
        is not None
        and _anchor_matches(anchor.text, target.relation.anchor_text)
    }
    return [
        match for match in materialized if match[0].element_id in valid_relations
    ]


def _anchor_matches(actual: str, expected: str) -> bool:
    normalized_actual = normalize_ocr_text(actual, case_sensitive=False)
    normalized_expected = normalize_ocr_text(expected, case_sensitive=False)
    return (
        normalized_actual == normalized_expected
        or normalized_expected in normalized_actual
    )


def _score_candidates(
    snapshot: OcrPageSnapshot,
    target: OcrTargetSpec,
    matches: Iterable[tuple[OcrTextElement, float]],
) -> tuple[OcrTargetCandidate, ...]:
    candidates = [
        _score_candidate(snapshot, target, element, text_score)
        for element, text_score in matches
    ]
    candidates.sort(key=_candidate_sort_key)
    return tuple(candidates)


def _score_candidate(
    snapshot: OcrPageSnapshot,
    target: OcrTargetSpec,
    element: OcrTextElement,
    text_score: float,
) -> OcrTargetCandidate:
    matched_relations = _matched_relations(snapshot, target, element)
    if target.role == "any":
        role_score = 1.0
    elif element.role == target.role:
        role_score = element.role_confidence
    else:
        role_score = 0.0

    if target.relation is None:
        relation_score = 1.0
        distance_score = 1.0
    elif matched_relations:
        relation_score = max(item.confidence for item in matched_relations)
        distance_score = max(
            0.0,
            1.0
            - min(item.distance_ratio for item in matched_relations)
            / max(target.relation.max_distance_ratio, 1e-9),
        )
    else:
        relation_score = 0.0
        distance_score = 0.0

    variant_score = _variant_consistency(snapshot, element)
    total_score = (
        text_score * _SCORE_WEIGHTS["text"]
        + element.confidence * _SCORE_WEIGHTS["confidence"]
        + role_score * _SCORE_WEIGHTS["role"]
        + relation_score * _SCORE_WEIGHTS["relation"]
        + distance_score * _SCORE_WEIGHTS["distance"]
        + variant_score * _SCORE_WEIGHTS["variant"]
    )
    return OcrTargetCandidate(
        element=element,
        text_score=_clamp(text_score),
        confidence_score=element.confidence,
        role_score=_clamp(role_score),
        relation_score=_clamp(relation_score),
        distance_score=_clamp(distance_score),
        variant_consistency_score=_clamp(variant_score),
        total_score=_clamp(total_score),
        matched_relations=matched_relations,
    )


def _matched_relations(
    snapshot: OcrPageSnapshot,
    target: OcrTargetSpec,
    element: OcrTextElement,
) -> tuple[OcrElementRelation, ...]:
    if target.relation is None:
        return ()
    elements_by_id = {item.element_id: item for item in snapshot.elements}
    relations = [
        relation
        for relation in snapshot.relations
        if relation.source_element_id == element.element_id
        and relation.type == target.relation.type
        and relation.distance_ratio <= target.relation.max_distance_ratio
        and (
            anchor := elements_by_id.get(relation.target_element_id)
        )
        is not None
        and _anchor_matches(anchor.text, target.relation.anchor_text)
    ]
    relations.sort(
        key=lambda item: (
            item.distance_ratio,
            -item.confidence,
            item.target_element_id,
        )
    )
    return tuple(relations)


def _variant_consistency(
    snapshot: OcrPageSnapshot,
    element: OcrTextElement,
) -> float:
    if len(snapshot.preprocessing_variants) <= 1:
        return 1.0
    lines_by_id = {line.line_id: line for line in snapshot.lines}
    block_ids = {
        block_id
        for line_id in element.line_ids
        if (line := lines_by_id.get(line_id)) is not None
        for block_id in line.block_ids
    }
    variants = {
        block.preprocessing_variant
        for block in snapshot.blocks
        if block.block_id in block_ids
    }
    if not variants:
        return 0.5
    return max(0.5, len(variants) / len(snapshot.preprocessing_variants))


def _candidate_sort_key(candidate: OcrTargetCandidate) -> tuple[float, float, float, str]:
    rect = candidate.element.coordinates.document_css_rect
    return (
        -candidate.total_score,
        rect.y,
        rect.x,
        candidate.element.element_id,
    )


def _reject(
    target: OcrTargetSpec,
    code: OcrErrorCode,
    message: str,
    candidates: tuple[OcrTargetCandidate, ...],
    scanned_tile_count: int,
    started_at: float,
) -> None:
    raise OcrTargetingError(
        OcrTargetResolution(
            status="rejected",
            target=target,
            candidates=candidates,
            error_code=code,
            error_message=message,
            scanned_tile_count=scanned_tile_count,
            elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
        )
    )


def _clamp(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)
