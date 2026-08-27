from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from statistics import median
from typing import Any, cast

from app.workers.ocr_types import (
    OcrCoordinateSet,
    OcrElementRelation,
    OcrEngineLanguageProfile,
    OcrErrorCode,
    OcrPageSnapshot,
    OcrPoint,
    OcrRatioRect,
    OcrRect,
    OcrRelationType,
    OcrTextBlock,
    OcrTextElement,
    OcrTextLine,
)


class OcrPageGeometryError(ValueError):
    """Raised when screenshot geometry cannot produce safe CSS coordinates."""


class OcrAssociationError(RuntimeError):
    """Raised when an associated control cannot be selected safely."""

    def __init__(self, code: OcrErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class OcrCoordinateMapper:
    image_width_px: int
    image_height_px: int
    viewport_width_css: int
    viewport_height_css: int
    device_scale_factor: float
    scroll_x_css: float = 0.0
    scroll_y_css: float = 0.0

    def __post_init__(self) -> None:
        if self.image_width_px <= 0 or self.image_height_px <= 0:
            raise OcrPageGeometryError("OCR screenshot dimensions must be positive.")
        if self.viewport_width_css <= 0 or self.viewport_height_css <= 0:
            raise OcrPageGeometryError("OCR viewport dimensions must be positive.")
        if self.device_scale_factor <= 0:
            raise OcrPageGeometryError("OCR device scale factor must be positive.")

        expected_width = self.viewport_width_css * self.device_scale_factor
        expected_height = self.viewport_height_css * self.device_scale_factor
        if not math.isclose(
            self.image_width_px, expected_width, rel_tol=0.0, abs_tol=1.0
        ) or not math.isclose(
            self.image_height_px, expected_height, rel_tol=0.0, abs_tol=1.0
        ):
            raise OcrPageGeometryError(
                "OCR screenshot pixels must match CSS viewport dimensions multiplied "
                "by device scale factor."
            )

    def pixel_rect_to_coordinates(self, rect: OcrRect) -> OcrCoordinateSet:
        pixel_rect = self._clip_pixel_rect(rect)
        viewport_rect = OcrRect(
            x=pixel_rect.x / self.device_scale_factor,
            y=pixel_rect.y / self.device_scale_factor,
            width=pixel_rect.width / self.device_scale_factor,
            height=pixel_rect.height / self.device_scale_factor,
        )
        document_rect = OcrRect(
            x=viewport_rect.x + self.scroll_x_css,
            y=viewport_rect.y + self.scroll_y_css,
            width=viewport_rect.width,
            height=viewport_rect.height,
        )
        return OcrCoordinateSet(
            pixel_rect=pixel_rect,
            ratio_rect=self.pixel_rect_to_ratio(pixel_rect),
            viewport_css_rect=viewport_rect,
            document_css_rect=document_rect,
        )

    def pixel_rect_to_ratio(self, rect: OcrRect) -> OcrRatioRect:
        pixel_rect = self._clip_pixel_rect(rect)
        left = pixel_rect.x / self.image_width_px
        top = pixel_rect.y / self.image_height_px
        right = (pixel_rect.x + pixel_rect.width) / self.image_width_px
        bottom = (pixel_rect.y + pixel_rect.height) / self.image_height_px
        return OcrRatioRect(
            x=left,
            y=top,
            width=max(0.0, min(1.0 - left, right - left)),
            height=max(0.0, min(1.0 - top, bottom - top)),
        )

    def ratio_rect_to_pixel(self, rect: OcrRatioRect) -> OcrRect:
        return self._clip_pixel_rect(
            OcrRect(
                x=rect.x * self.image_width_px,
                y=rect.y * self.image_height_px,
                width=rect.width * self.image_width_px,
                height=rect.height * self.image_height_px,
            )
        )

    def viewport_css_rect_to_pixel(self, rect: OcrRect) -> OcrRect:
        return self._clip_pixel_rect(
            OcrRect(
                x=rect.x * self.device_scale_factor,
                y=rect.y * self.device_scale_factor,
                width=rect.width * self.device_scale_factor,
                height=rect.height * self.device_scale_factor,
            )
        )

    def document_css_rect_to_pixel(self, rect: OcrRect) -> OcrRect:
        return self.viewport_css_rect_to_pixel(
            OcrRect(
                x=rect.x - self.scroll_x_css,
                y=rect.y - self.scroll_y_css,
                width=rect.width,
                height=rect.height,
            )
        )

    def pixel_point_to_viewport_css(self, point: OcrPoint) -> OcrPoint:
        return OcrPoint(
            x=point.x / self.device_scale_factor,
            y=point.y / self.device_scale_factor,
        )

    def viewport_point_to_document_css(self, point: OcrPoint) -> OcrPoint:
        return OcrPoint(
            x=point.x + self.scroll_x_css,
            y=point.y + self.scroll_y_css,
        )

    def document_point_to_viewport_css(self, point: OcrPoint) -> OcrPoint:
        return OcrPoint(
            x=point.x - self.scroll_x_css,
            y=point.y - self.scroll_y_css,
        )

    def viewport_point_to_pixel(self, point: OcrPoint) -> OcrPoint:
        return OcrPoint(
            x=point.x * self.device_scale_factor,
            y=point.y * self.device_scale_factor,
        )

    def _clip_pixel_rect(self, rect: OcrRect) -> OcrRect:
        if rect.width <= 0 or rect.height <= 0:
            raise OcrPageGeometryError("OCR rectangles must have positive dimensions.")
        left = min(max(float(rect.x), 0.0), float(self.image_width_px))
        top = min(max(float(rect.y), 0.0), float(self.image_height_px))
        right = min(
            max(float(rect.x + rect.width), 0.0), float(self.image_width_px)
        )
        bottom = min(
            max(float(rect.y + rect.height), 0.0), float(self.image_height_px)
        )
        if right <= left or bottom <= top:
            raise OcrPageGeometryError(
                "OCR rectangle does not intersect the screenshot."
            )
        return OcrRect(
            x=left,
            y=top,
            width=right - left,
            height=bottom - top,
        )


@dataclass(slots=True)
class _LineGroup:
    blocks: list[OcrTextBlock]


@dataclass(slots=True)
class _ElementDraft:
    element_id: str
    text: str
    confidence: float
    line_ids: tuple[str, ...]
    pixel_rect: OcrRect
    role: str = "text"
    role_confidence: float = 0.6
    role_evidence: tuple[str, ...] = ("ocr_text",)
    associated_control_rect: OcrRect | None = None
    associated_control_candidates: tuple[OcrRect, ...] = ()
    association_confidence: float = 0.0
    association_ambiguous: bool = False
    associated_region_id: int | None = None


@dataclass(frozen=True, slots=True)
class _VisualRegion:
    region_id: int
    pixel_rect: OcrRect


def build_ocr_page_snapshot(
    *,
    image_png_bytes: bytes,
    blocks: Sequence[OcrTextBlock],
    viewport_width_css: int,
    viewport_height_css: int,
    device_scale_factor: float,
    scroll_x_css: float = 0.0,
    scroll_y_css: float = 0.0,
    language_profiles: Sequence[OcrEngineLanguageProfile] | None = None,
    preprocessing_variants: Sequence[str] | None = None,
    elapsed_ms: float = 0.0,
) -> OcrPageSnapshot:
    """Build a page snapshot using only OCR output and screenshot geometry."""
    image, image_width, image_height = _decode_png(image_png_bytes)
    mapper = OcrCoordinateMapper(
        image_width_px=image_width,
        image_height_px=image_height,
        viewport_width_css=viewport_width_css,
        viewport_height_css=viewport_height_css,
        device_scale_factor=device_scale_factor,
        scroll_x_css=scroll_x_css,
        scroll_y_css=scroll_y_css,
    )
    normalized_blocks = _normalize_blocks(blocks, mapper)
    line_groups = _group_blocks_into_lines(normalized_blocks)
    lines = _build_lines(line_groups, mapper)
    drafts = _build_element_drafts(line_groups, lines, device_scale_factor)
    regions = _detect_visual_regions(image, mapper)
    _infer_roles_and_associations(drafts, regions, mapper)
    elements = tuple(_materialize_element(draft, mapper) for draft in drafts)
    relations = _build_relations(drafts, elements, mapper)

    actual_languages = language_profiles or tuple(
        dict.fromkeys(block.language for block in normalized_blocks)
    )
    actual_variants = preprocessing_variants or tuple(
        dict.fromkeys(block.preprocessing_variant for block in normalized_blocks)
    )
    return OcrPageSnapshot(
        image_width_px=image_width,
        image_height_px=image_height,
        viewport_width_css=viewport_width_css,
        viewport_height_css=viewport_height_css,
        device_scale_factor=device_scale_factor,
        scroll_x_css=scroll_x_css,
        scroll_y_css=scroll_y_css,
        language_profiles=tuple(actual_languages),
        preprocessing_variants=tuple(actual_variants),
        screenshot_checksum_sha256=hashlib.sha256(image_png_bytes).hexdigest(),
        elapsed_ms=elapsed_ms,
        blocks=normalized_blocks,
        lines=lines,
        elements=elements,
        relations=relations,
    )


def build_ocr_page_snapshot_from_analysis(
    *,
    image_png_bytes: bytes,
    analysis: Mapping[str, object],
    viewport_width_css: int,
    viewport_height_css: int,
    device_scale_factor: float,
    scroll_x_css: float = 0.0,
    scroll_y_css: float = 0.0,
) -> OcrPageSnapshot:
    """Adapt the OCR engine's compatibility dictionary into a typed snapshot."""
    image_width = _positive_analysis_int(analysis.get("image_width"), "image_width")
    image_height = _positive_analysis_int(
        analysis.get("image_height"), "image_height"
    )
    raw_blocks = analysis.get("blocks")
    if not isinstance(raw_blocks, Sequence) or isinstance(
        raw_blocks, (str, bytes, bytearray)
    ):
        raise OcrPageGeometryError("OCR analysis blocks must be an array.")

    raw_mapper = OcrCoordinateMapper(
        image_width_px=image_width,
        image_height_px=image_height,
        viewport_width_css=image_width,
        viewport_height_css=image_height,
        device_scale_factor=1.0,
    )
    default_languages = _analysis_language_profiles(analysis)
    blocks = tuple(
        _block_from_analysis(
            raw_block,
            index=index,
            mapper=raw_mapper,
            default_language=(
                default_languages[0] if default_languages else "zh_en"
            ),
        )
        for index, raw_block in enumerate(raw_blocks, start=1)
    )
    variants = _analysis_string_sequence(
        analysis.get("preprocessing_variants"),
        field="preprocessing_variants",
    )
    elapsed_value = analysis.get("elapsed_ms", 0.0)
    if isinstance(elapsed_value, bool) or not isinstance(
        elapsed_value, (int, float)
    ):
        raise OcrPageGeometryError("OCR analysis elapsed_ms must be numeric.")

    snapshot = build_ocr_page_snapshot(
        image_png_bytes=image_png_bytes,
        blocks=blocks,
        viewport_width_css=viewport_width_css,
        viewport_height_css=viewport_height_css,
        device_scale_factor=device_scale_factor,
        scroll_x_css=scroll_x_css,
        scroll_y_css=scroll_y_css,
        language_profiles=default_languages or None,
        preprocessing_variants=variants or None,
        elapsed_ms=float(elapsed_value),
    )
    if (
        snapshot.image_width_px != image_width
        or snapshot.image_height_px != image_height
    ):
        raise OcrPageGeometryError(
            "OCR analysis dimensions do not match the screenshot."
        )
    return snapshot


def resolve_associated_control_rect(element: OcrTextElement) -> OcrRect:
    if element.association_ambiguous:
        raise OcrAssociationError(
            OcrErrorCode.OCR_TARGET_AMBIGUOUS,
            f"OCR element `{element.text}` has multiple similarly ranked controls.",
        )
    if element.associated_control_rect is None:
        raise OcrAssociationError(
            OcrErrorCode.OCR_RELATION_NOT_SATISFIED,
            f"OCR element `{element.text}` has no associated visual control.",
        )
    return element.associated_control_rect


def related_elements(
    snapshot: OcrPageSnapshot,
    *,
    source_element_id: str,
    relation_type: OcrRelationType,
) -> tuple[OcrTextElement, ...]:
    elements_by_id = {element.element_id: element for element in snapshot.elements}
    return tuple(
        elements_by_id[relation.target_element_id]
        for relation in snapshot.relations
        if relation.source_element_id == source_element_id
        and relation.type == relation_type
        and relation.target_element_id in elements_by_id
    )


def _decode_png(image_png_bytes: bytes) -> tuple[Any, int, int]:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "OpenCV and numpy are required to build OCR page snapshots."
        ) from exc

    image = cv2.imdecode(
        np.frombuffer(image_png_bytes, dtype=np.uint8), cv2.IMREAD_COLOR
    )
    if image is None:
        raise OcrPageGeometryError("Failed to decode OCR screenshot PNG bytes.")
    image_height, image_width = image.shape[:2]
    return image, int(image_width), int(image_height)


def _block_from_analysis(
    raw_block: object,
    *,
    index: int,
    mapper: OcrCoordinateMapper,
    default_language: OcrEngineLanguageProfile,
) -> OcrTextBlock:
    if not isinstance(raw_block, Mapping):
        raise OcrPageGeometryError(
            f"OCR analysis block {index} must be an object."
        )
    text = raw_block.get("text")
    if not isinstance(text, str) or not text.strip():
        raise OcrPageGeometryError(
            f"OCR analysis block {index} text must be non-empty."
        )
    confidence = raw_block.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise OcrPageGeometryError(
            f"OCR analysis block {index} confidence must be numeric."
        )
    raw_rect = raw_block.get("pixel_rect")
    if not isinstance(raw_rect, Mapping):
        raise OcrPageGeometryError(
            f"OCR analysis block {index} pixel_rect must be an object."
        )
    pixel_rect = OcrRect(
        x=_analysis_number(raw_rect.get("x"), f"blocks[{index}].pixel_rect.x"),
        y=_analysis_number(raw_rect.get("y"), f"blocks[{index}].pixel_rect.y"),
        width=_analysis_number(
            raw_rect.get("width"), f"blocks[{index}].pixel_rect.width"
        ),
        height=_analysis_number(
            raw_rect.get("height"), f"blocks[{index}].pixel_rect.height"
        ),
    )
    coordinates = mapper.pixel_rect_to_coordinates(pixel_rect)
    polygon = _analysis_polygon(
        raw_block.get("polygon_points"),
        index=index,
        fallback_rect=coordinates.pixel_rect,
    )

    raw_language = raw_block.get("language", default_language)
    if raw_language not in {"zh_en", "en", "latin", "japan", "korean"}:
        raise OcrPageGeometryError(
            f"OCR analysis block {index} has an unsupported language."
        )
    language = cast(OcrEngineLanguageProfile, raw_language)
    variant = raw_block.get("preprocessing_variant", "original")
    if not isinstance(variant, str) or not variant.strip():
        raise OcrPageGeometryError(
            f"OCR analysis block {index} preprocessing_variant must be non-empty."
        )
    raw_block_id = raw_block.get("block_id")
    if raw_block_id is None:
        raw_order = raw_block.get("order_no", index)
        block_id = f"block-{raw_order}"
    elif isinstance(raw_block_id, str) and raw_block_id.strip():
        block_id = raw_block_id.strip()
    else:
        raise OcrPageGeometryError(
            f"OCR analysis block {index} block_id must be non-empty."
        )
    return OcrTextBlock(
        block_id=block_id,
        text=text.strip(),
        confidence=float(confidence),
        polygon=polygon,
        coordinates=coordinates,
        language=language,
        preprocessing_variant=variant.strip(),
    )


def _analysis_polygon(
    value: object,
    *,
    index: int,
    fallback_rect: OcrRect,
) -> tuple[OcrPoint, ...]:
    if value is None:
        return (
            OcrPoint(x=fallback_rect.x, y=fallback_rect.y),
            OcrPoint(
                x=fallback_rect.x + fallback_rect.width,
                y=fallback_rect.y,
            ),
            OcrPoint(
                x=fallback_rect.x + fallback_rect.width,
                y=fallback_rect.y + fallback_rect.height,
            ),
            OcrPoint(
                x=fallback_rect.x,
                y=fallback_rect.y + fallback_rect.height,
            ),
        )
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise OcrPageGeometryError(
            f"OCR analysis block {index} polygon_points must be an array."
        )
    points: list[OcrPoint] = []
    for point_index, raw_point in enumerate(value, start=1):
        if isinstance(raw_point, Mapping):
            raw_x = raw_point.get("x")
            raw_y = raw_point.get("y")
        elif isinstance(raw_point, Sequence) and not isinstance(
            raw_point, (str, bytes, bytearray)
        ):
            if len(raw_point) < 2:
                raise OcrPageGeometryError(
                    f"OCR analysis block {index} polygon point {point_index} "
                    "requires x and y."
                )
            raw_x, raw_y = raw_point[0], raw_point[1]
        else:
            raise OcrPageGeometryError(
                f"OCR analysis block {index} polygon point {point_index} "
                "must be an object or pair."
            )
        points.append(
            OcrPoint(
                x=_analysis_number(
                    raw_x, f"blocks[{index}].polygon[{point_index}].x"
                ),
                y=_analysis_number(
                    raw_y, f"blocks[{index}].polygon[{point_index}].y"
                ),
            )
        )
    if len(points) < 3:
        raise OcrPageGeometryError(
            f"OCR analysis block {index} polygon requires at least three points."
        )
    return tuple(points)


def _analysis_language_profiles(
    analysis: Mapping[str, object],
) -> tuple[OcrEngineLanguageProfile, ...]:
    values = _analysis_string_sequence(
        analysis.get("language_profiles"),
        field="language_profiles",
    )
    profiles: list[OcrEngineLanguageProfile] = []
    for value in values:
        if value not in {"zh_en", "en", "latin", "japan", "korean"}:
            raise OcrPageGeometryError(
                f"OCR analysis has unsupported language profile `{value}`."
            )
        profiles.append(cast(OcrEngineLanguageProfile, value))
    return tuple(profiles)


def _analysis_string_sequence(
    value: object,
    *,
    field: str,
) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise OcrPageGeometryError(f"OCR analysis {field} must be an array.")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise OcrPageGeometryError(
            f"OCR analysis {field} values must be non-empty strings."
        )
    return tuple(cast(str, item).strip() for item in value)


def _positive_analysis_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise OcrPageGeometryError(
            f"OCR analysis {field} must be a positive integer."
        )
    return value


def _analysis_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OcrPageGeometryError(f"OCR analysis {field} must be numeric.")
    if not math.isfinite(float(value)):
        raise OcrPageGeometryError(f"OCR analysis {field} must be finite.")
    return float(value)


def _normalize_blocks(
    blocks: Sequence[OcrTextBlock],
    mapper: OcrCoordinateMapper,
) -> tuple[OcrTextBlock, ...]:
    normalized: list[OcrTextBlock] = []
    seen_ids: set[str] = set()
    for block in blocks:
        text = block.text.strip()
        if not text:
            continue
        if block.block_id in seen_ids:
            raise OcrPageGeometryError(
                f"Duplicate OCR block id `{block.block_id}`."
            )
        seen_ids.add(block.block_id)
        pixel_rect = block.coordinates.pixel_rect
        coordinates = mapper.pixel_rect_to_coordinates(pixel_rect)
        polygon = tuple(
            OcrPoint(
                x=min(max(point.x, 0.0), float(mapper.image_width_px)),
                y=min(max(point.y, 0.0), float(mapper.image_height_px)),
            )
            for point in block.polygon
        )
        normalized.append(
            OcrTextBlock(
                block_id=block.block_id,
                text=text,
                confidence=block.confidence,
                polygon=polygon,
                coordinates=coordinates,
                language=block.language,
                preprocessing_variant=block.preprocessing_variant,
            )
        )
    return tuple(normalized)


def _group_blocks_into_lines(
    blocks: Sequence[OcrTextBlock],
) -> tuple[_LineGroup, ...]:
    groups: list[_LineGroup] = []
    for block in sorted(
        blocks,
        key=lambda item: (
            _center(item.coordinates.pixel_rect)[1],
            item.coordinates.pixel_rect.x,
        ),
    ):
        block_rect = block.coordinates.pixel_rect
        best_group: _LineGroup | None = None
        best_delta = math.inf
        for group in groups:
            group_rect = _union_rect(
                item.coordinates.pixel_rect for item in group.blocks
            )
            center_delta = abs(_center(block_rect)[1] - _center(group_rect)[1])
            overlap = _axis_overlap_ratio(
                block_rect.y,
                block_rect.height,
                group_rect.y,
                group_rect.height,
            )
            tolerance = max(block_rect.height, group_rect.height) * 0.55
            if (overlap >= 0.45 or center_delta <= tolerance) and center_delta < best_delta:
                best_group = group
                best_delta = center_delta
        if best_group is None:
            groups.append(_LineGroup(blocks=[block]))
        else:
            best_group.blocks.append(block)

    groups.sort(
        key=lambda group: (
            _union_rect(
                block.coordinates.pixel_rect for block in group.blocks
            ).y,
            min(block.coordinates.pixel_rect.x for block in group.blocks),
        )
    )
    for group in groups:
        group.blocks.sort(key=lambda block: block.coordinates.pixel_rect.x)
    return tuple(groups)


def _build_lines(
    groups: Sequence[_LineGroup],
    mapper: OcrCoordinateMapper,
) -> tuple[OcrTextLine, ...]:
    lines: list[OcrTextLine] = []
    for index, group in enumerate(groups, start=1):
        rect = _union_rect(
            block.coordinates.pixel_rect for block in group.blocks
        )
        lines.append(
            OcrTextLine(
                line_id=f"line-{index:04d}",
                text=_join_text(block.text for block in group.blocks),
                confidence=_weighted_confidence(group.blocks),
                block_ids=tuple(block.block_id for block in group.blocks),
                coordinates=mapper.pixel_rect_to_coordinates(rect),
            )
        )
    return tuple(lines)


def _build_element_drafts(
    groups: Sequence[_LineGroup],
    lines: Sequence[OcrTextLine],
    device_scale_factor: float,
) -> list[_ElementDraft]:
    drafts: list[_ElementDraft] = []
    for group, line in zip(groups, lines, strict=True):
        heights = [
            block.coordinates.pixel_rect.height for block in group.blocks
        ]
        split_gap = max(4.0 * device_scale_factor, median(heights) * 0.85)
        chunks: list[list[OcrTextBlock]] = []
        for block in group.blocks:
            if not chunks:
                chunks.append([block])
                continue
            previous = chunks[-1][-1].coordinates.pixel_rect
            current = block.coordinates.pixel_rect
            gap = current.x - (previous.x + previous.width)
            if gap > split_gap:
                chunks.append([block])
            else:
                chunks[-1].append(block)

        for chunk in chunks:
            drafts.append(
                _ElementDraft(
                    element_id=f"element-{len(drafts) + 1:04d}",
                    text=_join_text(block.text for block in chunk),
                    confidence=_weighted_confidence(chunk),
                    line_ids=(line.line_id,),
                    pixel_rect=_union_rect(
                        block.coordinates.pixel_rect for block in chunk
                    ),
                )
            )
    return drafts


def _detect_visual_regions(
    image: Any,
    mapper: OcrCoordinateMapper,
) -> tuple[_VisualRegion, ...]:
    import cv2

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    masks = [cv2.Canny(blurred, 40, 120)]
    for mode in (cv2.THRESH_BINARY, cv2.THRESH_BINARY_INV):
        _, thresholded = cv2.threshold(
            blurred, 0, 255, mode | cv2.THRESH_OTSU
        )
        masks.append(thresholded)

    candidates: list[OcrRect] = []
    min_width = max(18.0, 18.0 * mapper.device_scale_factor)
    min_height = max(12.0, 12.0 * mapper.device_scale_factor)
    image_area = mapper.image_width_px * mapper.image_height_px
    for mask in masks:
        contours, _ = cv2.findContours(
            mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
        )
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            if width < min_width or height < min_height:
                continue
            if width * height >= image_area * 0.92:
                continue
            aspect = width / max(height, 1)
            if aspect < 0.75 or aspect > 30.0:
                continue
            contour_area = abs(float(cv2.contourArea(contour)))
            if contour_area / max(width * height, 1) < 0.45:
                continue
            perimeter = cv2.arcLength(contour, True)
            approximation = cv2.approxPolyDP(contour, 0.03 * perimeter, True)
            if len(approximation) < 4 or len(approximation) > 10:
                continue
            candidates.append(
                OcrRect(
                    x=float(x),
                    y=float(y),
                    width=float(width),
                    height=float(height),
                )
            )

    deduplicated: list[OcrRect] = []
    for candidate in sorted(candidates, key=_rect_area):
        if any(_rect_iou(candidate, existing) >= 0.70 for existing in deduplicated):
            continue
        deduplicated.append(candidate)
    return tuple(
        _VisualRegion(region_id=index, pixel_rect=rect)
        for index, rect in enumerate(deduplicated, start=1)
    )


def _infer_roles_and_associations(
    drafts: list[_ElementDraft],
    regions: Sequence[_VisualRegion],
    mapper: OcrCoordinateMapper,
) -> None:
    enclosing: dict[str, _VisualRegion] = {}
    for draft in drafts:
        matches = [
            region
            for region in regions
            if _region_encloses_text(region.pixel_rect, draft.pixel_rect, mapper)
        ]
        if matches:
            enclosing[draft.element_id] = min(
                matches, key=lambda region: _rect_area(region.pixel_rect)
            )

    menu_ids = _infer_menu_item_ids(drafts, regions, mapper)
    input_regions: dict[int, _ElementDraft] = {}
    for draft in drafts:
        region = enclosing.get(draft.element_id)
        if draft.element_id in menu_ids:
            draft.role = "menu_item"
            draft.role_confidence = 0.86
            draft.role_evidence = ("vertical_menu_geometry", "shared_enclosure")
            if region is not None:
                draft.associated_control_rect = _viewport_rect(
                    region.pixel_rect, mapper
                )
                draft.association_confidence = 0.82
                draft.associated_region_id = region.region_id
            continue
        if region is None:
            continue

        relative_x = (
            _center(draft.pixel_rect)[0] - region.pixel_rect.x
        ) / region.pixel_rect.width
        aspect = region.pixel_rect.width / max(region.pixel_rect.height, 1.0)
        is_input = aspect >= 2.5 and relative_x <= 0.46
        draft.role = "input" if is_input else "button"
        draft.role_confidence = 0.9 if is_input else 0.88
        draft.role_evidence = (
            "enclosed_rect",
            "wide_left_aligned_text" if is_input else "centered_text",
        )
        draft.associated_control_rect = _viewport_rect(region.pixel_rect, mapper)
        draft.associated_control_candidates = (draft.associated_control_rect,)
        draft.association_confidence = draft.role_confidence
        draft.associated_region_id = region.region_id
        if is_input:
            input_regions[region.region_id] = draft

    candidate_input_regions = [
        region
        for region in regions
        if _is_input_shaped_region(region.pixel_rect, mapper)
        and not any(
            other.role in {"button", "menu_item"}
            and other.associated_region_id == region.region_id
            for other in drafts
        )
    ]
    for draft in drafts:
        if draft.role != "text":
            continue
        candidates = _association_candidates(
            draft, candidate_input_regions, mapper
        )
        if not candidates:
            continue

        best_score, best_region = candidates[0]
        candidate_rects = tuple(
            _viewport_rect(region.pixel_rect, mapper)
            for _, region in candidates[:3]
        )
        is_ambiguous = (
            len(candidates) > 1
            and best_score - candidates[1][0] < 0.12
        )
        draft.role = "label"
        draft.role_confidence = 0.58 if is_ambiguous else min(0.95, best_score)
        draft.role_evidence = (
            "nearby_input_geometry",
            "association_ambiguous" if is_ambiguous else "unique_nearest_control",
        )
        draft.associated_control_candidates = candidate_rects
        draft.association_ambiguous = is_ambiguous
        draft.association_confidence = best_score
        if not is_ambiguous:
            draft.associated_control_rect = candidate_rects[0]
            draft.associated_region_id = best_region.region_id

    for draft in drafts:
        if draft.role != "label" or draft.associated_region_id is None:
            continue
        target = input_regions.get(draft.associated_region_id)
        if target is not None and target.element_id == draft.element_id:
            draft.associated_region_id = None


def _infer_menu_item_ids(
    drafts: Sequence[_ElementDraft],
    regions: Sequence[_VisualRegion],
    mapper: OcrCoordinateMapper,
) -> set[str]:
    menu_ids: set[str] = set()
    for region in regions:
        contained = [
            draft
            for draft in drafts
            if _contains_center(region.pixel_rect, draft.pixel_rect)
        ]
        if len(contained) < 3:
            continue
        contained.sort(key=lambda draft: _center(draft.pixel_rect)[1])
        text_heights = [draft.pixel_rect.height for draft in contained]
        if region.pixel_rect.height < median(text_heights) * 3.0:
            continue
        left_positions = [draft.pixel_rect.x for draft in contained]
        if max(left_positions) - min(left_positions) > max(
            12.0 * mapper.device_scale_factor,
            region.pixel_rect.width * 0.18,
        ):
            continue
        center_deltas = [
            _center(current.pixel_rect)[1] - _center(previous.pixel_rect)[1]
            for previous, current in zip(contained, contained[1:])
        ]
        if any(delta < median(text_heights) * 0.7 for delta in center_deltas):
            continue
        menu_ids.update(draft.element_id for draft in contained)
    return menu_ids


def _association_candidates(
    draft: _ElementDraft,
    regions: Sequence[_VisualRegion],
    mapper: OcrCoordinateMapper,
) -> list[tuple[float, _VisualRegion]]:
    text_rect = _viewport_rect(draft.pixel_rect, mapper)
    viewport_diagonal = math.hypot(
        mapper.viewport_width_css, mapper.viewport_height_css
    )
    candidates: list[tuple[float, _VisualRegion]] = []
    for region in regions:
        control_rect = _viewport_rect(region.pixel_rect, mapper)
        if _contains_center(control_rect, text_rect):
            continue
        text_center = _center(text_rect)
        control_center = _center(control_rect)
        distance_ratio = _rect_gap_distance(text_rect, control_rect) / viewport_diagonal
        if distance_ratio > 0.28:
            continue

        vertical_alignment = max(
            0.0,
            1.0
            - abs(text_center[1] - control_center[1])
            / max(text_rect.height, control_rect.height, 1.0),
        )
        horizontal_alignment = max(
            0.0,
            1.0
            - abs(text_center[0] - control_center[0])
            / max(text_rect.width, control_rect.width, 1.0),
        )
        is_right = control_rect.x >= text_rect.x + text_rect.width - 2.0
        is_below = control_rect.y >= text_rect.y + text_rect.height - 2.0
        if is_right and vertical_alignment >= 0.25:
            alignment = vertical_alignment
        elif is_below and horizontal_alignment >= 0.25:
            alignment = horizontal_alignment
        else:
            continue
        proximity = max(0.0, 1.0 - distance_ratio / 0.28)
        score = alignment * 0.62 + proximity * 0.38
        if score >= 0.48:
            candidates.append((score, region))
    candidates.sort(key=lambda item: (-item[0], _rect_area(item[1].pixel_rect)))
    return candidates


def _materialize_element(
    draft: _ElementDraft,
    mapper: OcrCoordinateMapper,
) -> OcrTextElement:
    return OcrTextElement(
        element_id=draft.element_id,
        text=draft.text,
        confidence=draft.confidence,
        line_ids=draft.line_ids,
        coordinates=mapper.pixel_rect_to_coordinates(draft.pixel_rect),
        role=draft.role,
        role_confidence=draft.role_confidence,
        role_evidence=draft.role_evidence,
        associated_control_rect=draft.associated_control_rect,
        associated_control_candidates=draft.associated_control_candidates,
        association_confidence=draft.association_confidence,
        association_ambiguous=draft.association_ambiguous,
    )


def _build_relations(
    drafts: Sequence[_ElementDraft],
    elements: Sequence[OcrTextElement],
    mapper: OcrCoordinateMapper,
) -> tuple[OcrElementRelation, ...]:
    relations: list[OcrElementRelation] = []
    viewport_diagonal = math.hypot(
        mapper.viewport_width_css, mapper.viewport_height_css
    )
    rects = {
        element.element_id: element.coordinates.viewport_css_rect
        for element in elements
    }
    for source in elements:
        source_rect = rects[source.element_id]
        source_center = _center(source_rect)
        for target in elements:
            if source.element_id == target.element_id:
                continue
            target_rect = rects[target.element_id]
            target_center = _center(target_rect)
            distance_ratio = min(
                1.0, math.dist(source_center, target_center) / viewport_diagonal
            )
            confidence = max(0.0, 1.0 - distance_ratio)
            if source_center[0] < target_center[0]:
                relations.append(
                    _relation(
                        source, target, "left_of", distance_ratio, confidence
                    )
                )
            elif source_center[0] > target_center[0]:
                relations.append(
                    _relation(
                        source, target, "right_of", distance_ratio, confidence
                    )
                )
            if source_center[1] < target_center[1]:
                relations.append(
                    _relation(source, target, "above", distance_ratio, confidence)
                )
            elif source_center[1] > target_center[1]:
                relations.append(
                    _relation(source, target, "below", distance_ratio, confidence)
                )
            if _axis_overlap_ratio(
                source_rect.y,
                source_rect.height,
                target_rect.y,
                target_rect.height,
            ) >= 0.5:
                relations.append(
                    _relation(
                        source,
                        target,
                        "same_row",
                        distance_ratio,
                        confidence,
                    )
                )
            if _axis_overlap_ratio(
                source_rect.x,
                source_rect.width,
                target_rect.x,
                target_rect.width,
            ) >= 0.5:
                relations.append(
                    _relation(
                        source,
                        target,
                        "same_column",
                        distance_ratio,
                        confidence,
                    )
                )

    for source in elements:
        source_center = _center(rects[source.element_id])
        ranked = sorted(
            [
                (
                math.dist(source_center, _center(rects[target.element_id])),
                target,
                )
                for target in elements
                if target.element_id != source.element_id
            ],
            key=lambda item: (item[0], item[1].element_id),
        )
        if not ranked:
            continue
        if len(ranked) > 1 and ranked[1][0] - ranked[0][0] <= 2.0:
            continue
        distance, target = ranked[0]
        distance_ratio = min(1.0, distance / viewport_diagonal)
        relations.append(
            _relation(
                source,
                target,
                "nearest",
                distance_ratio,
                max(0.0, 1.0 - distance_ratio),
            )
        )

    drafts_by_id = {draft.element_id: draft for draft in drafts}
    input_by_region = {
        draft.associated_region_id: draft
        for draft in drafts
        if draft.role == "input" and draft.associated_region_id is not None
    }
    elements_by_id = {element.element_id: element for element in elements}
    for source in elements:
        source_draft = drafts_by_id[source.element_id]
        if source_draft.role != "label" or source_draft.association_ambiguous:
            continue
        target_draft = input_by_region.get(source_draft.associated_region_id)
        if target_draft is None:
            continue
        target = elements_by_id[target_draft.element_id]
        distance_ratio = min(
            1.0,
            math.dist(
                _center(rects[source.element_id]),
                _center(rects[target.element_id]),
            )
            / viewport_diagonal,
        )
        relations.append(
            _relation(
                source,
                target,
                "associated_control",
                distance_ratio,
                source.association_confidence,
            )
        )
    return tuple(relations)


def _relation(
    source: OcrTextElement,
    target: OcrTextElement,
    relation_type: OcrRelationType,
    distance_ratio: float,
    confidence: float,
) -> OcrElementRelation:
    return OcrElementRelation(
        source_element_id=source.element_id,
        target_element_id=target.element_id,
        type=relation_type,
        distance_ratio=min(max(distance_ratio, 0.0), 1.0),
        confidence=min(max(confidence, 0.0), 1.0),
    )


def _region_encloses_text(
    region: OcrRect,
    text: OcrRect,
    mapper: OcrCoordinateMapper,
) -> bool:
    margin = max(1.0, mapper.device_scale_factor)
    return (
        region.x <= text.x - margin
        and region.y <= text.y - margin
        and region.x + region.width >= text.x + text.width + margin
        and region.y + region.height >= text.y + text.height + margin
        and region.width <= mapper.image_width_px * 0.9
        and region.height <= mapper.image_height_px * 0.6
    )


def _is_input_shaped_region(
    rect: OcrRect,
    mapper: OcrCoordinateMapper,
) -> bool:
    width_css = rect.width / mapper.device_scale_factor
    height_css = rect.height / mapper.device_scale_factor
    return (
        width_css >= 60.0
        and 18.0 <= height_css <= 80.0
        and width_css / max(height_css, 1.0) >= 2.0
    )


def _viewport_rect(
    pixel_rect: OcrRect,
    mapper: OcrCoordinateMapper,
) -> OcrRect:
    return mapper.pixel_rect_to_coordinates(pixel_rect).viewport_css_rect


def _contains_center(container: OcrRect, item: OcrRect) -> bool:
    center_x, center_y = _center(item)
    return (
        container.x <= center_x <= container.x + container.width
        and container.y <= center_y <= container.y + container.height
    )


def _weighted_confidence(blocks: Sequence[OcrTextBlock]) -> float:
    weights = [max(1, len(block.text.strip())) for block in blocks]
    return sum(
        block.confidence * weight for block, weight in zip(blocks, weights, strict=True)
    ) / sum(weights)


def _join_text(parts: Iterable[str]) -> str:
    result = ""
    for raw_part in parts:
        part = str(raw_part).strip()
        if not part:
            continue
        if result and _needs_space(result[-1], part[0]):
            result += " "
        result += part
    return result


def _needs_space(previous: str, current: str) -> bool:
    return previous.isascii() and current.isascii() and (
        previous.isalnum() or previous in ")]}"
    ) and (current.isalnum() or current in "([{")


def _union_rect(rects: Iterable[OcrRect]) -> OcrRect:
    materialized = tuple(rects)
    if not materialized:
        raise OcrPageGeometryError("Cannot merge an empty OCR rectangle set.")
    left = min(rect.x for rect in materialized)
    top = min(rect.y for rect in materialized)
    right = max(rect.x + rect.width for rect in materialized)
    bottom = max(rect.y + rect.height for rect in materialized)
    return OcrRect(x=left, y=top, width=right - left, height=bottom - top)


def _center(rect: OcrRect) -> tuple[float, float]:
    return rect.x + rect.width / 2.0, rect.y + rect.height / 2.0


def _rect_gap_distance(first: OcrRect, second: OcrRect) -> float:
    horizontal_gap = max(
        first.x - (second.x + second.width),
        second.x - (first.x + first.width),
        0.0,
    )
    vertical_gap = max(
        first.y - (second.y + second.height),
        second.y - (first.y + first.height),
        0.0,
    )
    return math.hypot(horizontal_gap, vertical_gap)


def _axis_overlap_ratio(
    first_start: float,
    first_length: float,
    second_start: float,
    second_length: float,
) -> float:
    overlap = max(
        0.0,
        min(first_start + first_length, second_start + second_length)
        - max(first_start, second_start),
    )
    return overlap / max(min(first_length, second_length), 1.0)


def _rect_area(rect: OcrRect) -> float:
    return rect.width * rect.height


def _rect_iou(first: OcrRect, second: OcrRect) -> float:
    intersection_width = max(
        0.0,
        min(first.x + first.width, second.x + second.width)
        - max(first.x, second.x),
    )
    intersection_height = max(
        0.0,
        min(first.y + first.height, second.y + second.height)
        - max(first.y, second.y),
    )
    intersection = intersection_width * intersection_height
    union = _rect_area(first) + _rect_area(second) - intersection
    return intersection / union if union > 0 else 0.0
