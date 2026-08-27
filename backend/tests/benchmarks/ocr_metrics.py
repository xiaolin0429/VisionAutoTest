from __future__ import annotations

import math
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "Rect":
        return cls(
            x=float(value["x"]),
            y=float(value["y"]),
            width=float(value["width"]),
            height=float(value["height"]),
        )

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def area(self) -> float:
        return max(self.width, 0.0) * max(self.height, 0.0)

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2.0, self.y + self.height / 2.0)

    def contains(self, point: tuple[float, float], *, tolerance: float = 0.0) -> bool:
        x, y = point
        return (
            self.x - tolerance <= x <= self.right + tolerance
            and self.y - tolerance <= y <= self.bottom + tolerance
        )


@dataclass(frozen=True, slots=True)
class Detection:
    text: str
    rect: Rect


@dataclass(frozen=True, slots=True)
class DetectionCounts:
    true_positive: int
    false_positive: int
    false_negative: int

    def __add__(self, other: "DetectionCounts") -> "DetectionCounts":
        return DetectionCounts(
            true_positive=self.true_positive + other.true_positive,
            false_positive=self.false_positive + other.false_positive,
            false_negative=self.false_negative + other.false_negative,
        )

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 1.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 1.0

    @property
    def f1(self) -> float:
        denominator = self.precision + self.recall
        return (
            2.0 * self.precision * self.recall / denominator
            if denominator
            else 0.0
        )


@dataclass(frozen=True, slots=True)
class CharacterErrorCounts:
    edit_distance: int
    character_count: int

    def __add__(self, other: "CharacterErrorCounts") -> "CharacterErrorCounts":
        return CharacterErrorCounts(
            edit_distance=self.edit_distance + other.edit_distance,
            character_count=self.character_count + other.character_count,
        )

    @property
    def cer(self) -> float:
        if self.character_count == 0:
            return 0.0 if self.edit_distance == 0 else 1.0
        return self.edit_distance / self.character_count


def normalize_benchmark_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def intersection_over_union(left: Rect, right: Rect) -> float:
    intersection_width = max(0.0, min(left.right, right.right) - max(left.x, right.x))
    intersection_height = max(
        0.0,
        min(left.bottom, right.bottom) - max(left.y, right.y),
    )
    intersection = intersection_width * intersection_height
    union = left.area + right.area - intersection
    return intersection / union if union > 0 else 0.0


def detection_counts(
    expected: Sequence[Detection],
    predicted: Sequence[Detection],
    *,
    minimum_iou: float = 0.30,
) -> DetectionCounts:
    """Compute geometry-only OCR detection counts with one-to-one box matching."""
    if not 0.0 < minimum_iou <= 1.0:
        raise ValueError("minimum_iou must be greater than zero and at most one.")

    pairs = sorted(
        (
            (intersection_over_union(expected_item.rect, predicted_item.rect), i, j)
            for i, expected_item in enumerate(expected)
            for j, predicted_item in enumerate(predicted)
        ),
        reverse=True,
    )
    matched_expected: set[int] = set()
    matched_predicted: set[int] = set()
    for overlap, expected_index, predicted_index in pairs:
        if overlap < minimum_iou:
            break
        if expected_index in matched_expected or predicted_index in matched_predicted:
            continue
        matched_expected.add(expected_index)
        matched_predicted.add(predicted_index)

    return DetectionCounts(
        true_positive=len(matched_expected),
        false_positive=len(predicted) - len(matched_predicted),
        false_negative=len(expected) - len(matched_expected),
    )


def character_error_counts(
    expected: Sequence[Detection],
    predicted: Sequence[Detection],
) -> CharacterErrorCounts:
    """Pair text by spatial overlap and count missing text as full deletions."""
    used_predictions: set[int] = set()
    edit_distance = 0
    character_count = 0
    for expected_item in expected:
        normalized_expected = normalize_benchmark_text(expected_item.text)
        character_count += len(normalized_expected)
        candidates = sorted(
            (
                (
                    intersection_over_union(expected_item.rect, predicted_item.rect),
                    predicted_index,
                )
                for predicted_index, predicted_item in enumerate(predicted)
                if predicted_index not in used_predictions
            ),
            reverse=True,
        )
        if not candidates or candidates[0][0] <= 0.0:
            edit_distance += len(normalized_expected)
            continue
        _, prediction_index = candidates[0]
        used_predictions.add(prediction_index)
        normalized_prediction = normalize_benchmark_text(
            predicted[prediction_index].text
        )
        edit_distance += levenshtein_distance(
            normalized_expected,
            normalized_prediction,
        )
    return CharacterErrorCounts(
        edit_distance=edit_distance,
        character_count=character_count,
    )


def levenshtein_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1]
                    + (left_character != right_character),
                )
            )
        previous = current
    return previous[-1]


def percentile(values: Sequence[float], quantile: float) -> float:
    """Return the nearest-rank percentile used by the acceptance budgets."""
    if not values:
        raise ValueError("percentile requires at least one value.")
    if not 0.0 < quantile <= 1.0:
        raise ValueError("quantile must be greater than zero and at most one.")
    ordered = sorted(float(value) for value in values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def analysis_detections(analysis: Mapping[str, object]) -> tuple[Detection, ...]:
    raw_blocks = analysis.get("blocks")
    if not isinstance(raw_blocks, Sequence) or isinstance(
        raw_blocks, (str, bytes, bytearray)
    ):
        raise ValueError("OCR analysis blocks must be an array.")
    detections: list[Detection] = []
    for raw_block in raw_blocks:
        if not isinstance(raw_block, Mapping):
            raise ValueError("OCR analysis block must be an object.")
        raw_rect = raw_block.get("pixel_rect")
        if not isinstance(raw_rect, Mapping):
            raise ValueError("OCR analysis block pixel_rect must be an object.")
        detections.append(
            Detection(
                text=str(raw_block.get("text", "")),
                rect=Rect.from_mapping(raw_rect),
            )
        )
    return tuple(detections)


def manifest_detections(
    fixture: Mapping[str, object],
    *,
    include_cer: bool = False,
) -> tuple[Detection, ...]:
    raw_annotations = fixture.get("annotations")
    if not isinstance(raw_annotations, Sequence) or isinstance(
        raw_annotations, (str, bytes, bytearray)
    ):
        raise ValueError("Benchmark fixture annotations must be an array.")
    detections: list[Detection] = []
    for annotation in raw_annotations:
        if not isinstance(annotation, Mapping):
            raise ValueError("Benchmark annotation must be an object.")
        include_key = "include_cer" if include_cer else "include_detection"
        if annotation.get(include_key) is not True:
            continue
        raw_rect = annotation.get("text_rect_px")
        if not isinstance(raw_rect, Mapping):
            raise ValueError("Benchmark annotation text_rect_px must be an object.")
        detections.append(
            Detection(
                text=str(annotation.get("text", "")),
                rect=Rect.from_mapping(raw_rect),
            )
        )
    return tuple(detections)


def ratio(numerator: int, denominator: int) -> float:
    if denominator < 0 or numerator < 0:
        raise ValueError("Metric counts must not be negative.")
    return numerator / denominator if denominator else 0.0


def rounded_metric(value: float) -> float:
    return round(float(value), 6)


def to_metric_dict(
    detection: DetectionCounts,
    character: CharacterErrorCounts,
) -> dict[str, Any]:
    return {
        "detection": {
            "true_positive": detection.true_positive,
            "false_positive": detection.false_positive,
            "false_negative": detection.false_negative,
            "precision": rounded_metric(detection.precision),
            "recall": rounded_metric(detection.recall),
            "f1": rounded_metric(detection.f1),
        },
        "recognition": {
            "edit_distance": character.edit_distance,
            "character_count": character.character_count,
            "cer": rounded_metric(character.cer),
        },
    }
