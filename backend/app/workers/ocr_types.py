from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OcrMatchMode = Literal["exact", "contains", "regex", "fuzzy"]
OcrTargetScope = Literal["viewport", "page"]
OcrAssertionScope = Literal["viewport", "page", "element_legacy"]
OcrAssertionMode = Literal["present", "absent", "count", "relation"]
OcrLanguageProfile = Literal["auto", "zh_en", "en", "latin", "japan", "korean"]
OcrEngineLanguageProfile = Literal["zh_en", "en", "latin", "japan", "korean"]
OcrElementRole = Literal["any", "text", "button", "input", "menu_item", "label"]
OcrInferredElementRole = Literal["text", "button", "input", "menu_item", "label"]
OcrRelationType = Literal[
    "left_of",
    "right_of",
    "above",
    "below",
    "nearest",
    "same_row",
    "same_column",
    "associated_control",
]
OcrActionPoint = Literal["text_center", "associated_control"]
OcrPreprocessingProfile = Literal["fast", "balanced", "robust"]
OcrResolutionStatus = Literal["resolved", "not_found", "rejected", "error"]

Ratio = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]
PositiveInt = Annotated[int, Field(ge=1)]


class OcrErrorCode(StrEnum):
    OCR_TARGET_NOT_FOUND = "OCR_TARGET_NOT_FOUND"
    OCR_TARGET_AMBIGUOUS = "OCR_TARGET_AMBIGUOUS"
    OCR_CONFIDENCE_LOW = "OCR_CONFIDENCE_LOW"
    OCR_RELATION_NOT_SATISFIED = "OCR_RELATION_NOT_SATISFIED"
    OCR_ROLE_NOT_SATISFIED = "OCR_ROLE_NOT_SATISFIED"
    OCR_PAGE_SCAN_LIMIT = "OCR_PAGE_SCAN_LIMIT"
    OCR_ACTION_REVALIDATION_FAILED = "OCR_ACTION_REVALIDATION_FAILED"
    OCR_ACTION_VERIFICATION_FAILED = "OCR_ACTION_VERIFICATION_FAILED"
    OCR_LANGUAGE_UNSUPPORTED = "OCR_LANGUAGE_UNSUPPORTED"
    OCR_MODEL_UNAVAILABLE = "OCR_MODEL_UNAVAILABLE"
    OCR_ENGINE_UNAVAILABLE = "OCR_ENGINE_UNAVAILABLE"
    OCR_ANALYSIS_FAILED = "OCR_ANALYSIS_FAILED"


class OcrModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OcrStrictModel(OcrModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class OcrPoint(OcrModel):
    x: float
    y: float


class OcrRect(OcrModel):
    x: float
    y: float
    width: NonNegativeFloat
    height: NonNegativeFloat


class OcrRatioRect(OcrModel):
    x: Ratio
    y: Ratio
    width: Ratio
    height: Ratio

    @model_validator(mode="after")
    def validate_bounds(self) -> "OcrRatioRect":
        if self.x + self.width > 1.0 or self.y + self.height > 1.0:
            raise ValueError("OCR ratio rectangles must stay within image bounds.")
        return self


class OcrCoordinateSet(OcrModel):
    pixel_rect: OcrRect
    ratio_rect: OcrRatioRect
    viewport_css_rect: OcrRect
    document_css_rect: OcrRect


class OcrTargetRelationSpec(OcrStrictModel):
    type: OcrRelationType
    anchor_text: str
    max_distance_ratio: Ratio = 0.25

    @field_validator("anchor_text")
    @classmethod
    def validate_anchor_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("OCR relation anchor_text must be non-empty.")
        return normalized


class OcrTargetSpec(OcrStrictModel):
    text: str
    match_mode: OcrMatchMode = "exact"
    case_sensitive: bool = False
    occurrence: PositiveInt = 1
    scope: OcrTargetScope = "viewport"
    language: OcrLanguageProfile = "zh_en"
    role: OcrElementRole = "any"
    min_confidence: Ratio = 0.75
    min_score: Ratio = 0.75
    ambiguity_margin: Ratio = 0.10
    action_point: OcrActionPoint = "text_center"
    relation: OcrTargetRelationSpec | None = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("OCR target text must be non-empty.")
        return normalized

    @model_validator(mode="after")
    def validate_regex(self) -> "OcrTargetSpec":
        if self.match_mode == "regex":
            try:
                re.compile(self.text)
            except re.error as exc:
                raise ValueError(f"OCR target regex is invalid: {exc}") from exc
        return self


class OcrTextBlock(OcrModel):
    block_id: str
    text: str
    confidence: Ratio
    polygon: tuple[OcrPoint, ...]
    coordinates: OcrCoordinateSet
    language: OcrEngineLanguageProfile
    preprocessing_variant: str


class OcrTextLine(OcrModel):
    line_id: str
    text: str
    confidence: Ratio
    block_ids: tuple[str, ...]
    coordinates: OcrCoordinateSet


class OcrTextElement(OcrModel):
    element_id: str
    text: str
    confidence: Ratio
    line_ids: tuple[str, ...]
    coordinates: OcrCoordinateSet
    role: OcrInferredElementRole
    role_confidence: Ratio
    role_evidence: tuple[str, ...] = ()
    associated_control_rect: OcrRect | None = None
    associated_control_candidates: tuple[OcrRect, ...] = ()
    association_confidence: Ratio = 0.0
    association_ambiguous: bool = False


class OcrElementRelation(OcrModel):
    source_element_id: str
    target_element_id: str
    type: OcrRelationType
    distance_ratio: Ratio
    confidence: Ratio


class OcrTargetCandidate(OcrModel):
    element: OcrTextElement
    text_score: Ratio
    confidence_score: Ratio
    role_score: Ratio
    relation_score: Ratio
    distance_score: Ratio
    variant_consistency_score: Ratio
    total_score: Ratio
    matched_relations: tuple[OcrElementRelation, ...] = ()


class OcrPageSnapshot(OcrModel):
    image_width_px: PositiveInt
    image_height_px: PositiveInt
    viewport_width_css: PositiveInt
    viewport_height_css: PositiveInt
    device_scale_factor: Annotated[float, Field(gt=0.0)]
    scroll_x_css: float
    scroll_y_css: float
    language_profiles: tuple[OcrEngineLanguageProfile, ...]
    preprocessing_variants: tuple[str, ...]
    screenshot_checksum_sha256: str
    elapsed_ms: NonNegativeFloat
    blocks: tuple[OcrTextBlock, ...] = ()
    lines: tuple[OcrTextLine, ...] = ()
    elements: tuple[OcrTextElement, ...] = ()
    relations: tuple[OcrElementRelation, ...] = ()


class OcrTargetResolution(OcrModel):
    status: OcrResolutionStatus
    target: OcrTargetSpec
    selected_candidate: OcrTargetCandidate | None = None
    candidates: tuple[OcrTargetCandidate, ...] = ()
    error_code: OcrErrorCode | None = None
    error_message: str | None = None
    scanned_tile_count: Annotated[int, Field(ge=0)] = 0
    elapsed_ms: NonNegativeFloat = 0.0
