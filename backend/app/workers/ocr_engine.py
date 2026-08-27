from __future__ import annotations

import math
import time
import unicodedata
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from numbers import Real
from pathlib import Path
from threading import RLock
from typing import Any

from app.workers.ocr_types import (
    OcrEngineLanguageProfile,
    OcrErrorCode,
    OcrLanguageProfile,
    OcrPreprocessingProfile,
)

PADDLE_LANGUAGE_BY_PROFILE: dict[OcrEngineLanguageProfile, str] = {
    "zh_en": "ch",
    "en": "en",
    "latin": "latin",
    "japan": "japan",
    "korean": "korean",
}

_IDENTITY_TRANSFORM = (
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
)
_MAX_UPSCALED_EDGE = 3200
_MAX_UPSCALED_PIXELS = 6_000_000
_EARLY_STOP_MIN_AVERAGE_CONFIDENCE = 0.92
_EARLY_STOP_HIGH_CONFIDENCE_FLOOR = 0.90
_EARLY_STOP_MIN_HIGH_CONFIDENCE_RATIO = 0.80


class OcrEngineError(RuntimeError):
    def __init__(self, code: OcrErrorCode, message: str) -> None:
        self.code = code
        super().__init__(f"{code.value}: {message}")


@dataclass(frozen=True, slots=True)
class OcrPreprocessVariant:
    name: str
    image: Any
    to_original_transform: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ] = _IDENTITY_TRANSFORM

    def map_polygon_to_original(
        self,
        polygon: Sequence[Sequence[float]],
    ) -> list[tuple[float, float]]:
        mapped: list[tuple[float, float]] = []
        matrix = self.to_original_transform
        for point in polygon:
            if len(point) < 2:
                continue
            x = float(point[0])
            y = float(point[1])
            denominator = (
                matrix[2][0] * x + matrix[2][1] * y + matrix[2][2]
            )
            if math.isclose(denominator, 0.0):
                continue
            mapped.append(
                (
                    (matrix[0][0] * x + matrix[0][1] * y + matrix[0][2])
                    / denominator,
                    (matrix[1][0] * x + matrix[1][1] * y + matrix[1][2])
                    / denominator,
                )
            )
        return mapped


class OcrPreprocessor:
    def __init__(
        self,
        *,
        profile: OcrPreprocessingProfile,
        max_variants: int,
    ) -> None:
        if max_variants < 1:
            raise ValueError("OCR preprocessing requires at least one variant.")
        self.profile = profile
        self.max_variants = max_variants

    def build_variants(self, image: Any) -> tuple[OcrPreprocessVariant, ...]:
        cv2 = _load_cv2()
        if image is None or len(image.shape) < 2:
            raise OcrEngineError(
                OcrErrorCode.OCR_ANALYSIS_FAILED,
                "OCR preprocessing received an invalid image.",
            )

        variants = [OcrPreprocessVariant(name="original", image=image)]
        if self.profile == "fast":
            scale = self._small_text_scale(cv2, image)
            if scale > 1.0:
                variants.append(self._build_scaled_variant(cv2, image, scale))
            return tuple(variants[: self.max_variants])

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        scale = self._small_text_scale(cv2, image)
        if scale > 1.0:
            variants.append(self._build_scaled_variant(cv2, image, scale))

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        variants.append(
            OcrPreprocessVariant(
                name="clahe",
                image=cv2.cvtColor(clahe, cv2.COLOR_GRAY2BGR),
            )
        )

        deskew_angle = self._estimate_deskew_angle(cv2, gray)
        if deskew_angle is not None:
            variants.append(
                self._build_deskew_variant(cv2, image, deskew_angle)
            )

        denoised = cv2.fastNlMeansDenoising(gray, None, h=7)
        variants.append(
            OcrPreprocessVariant(
                name="denoise",
                image=cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR),
            )
        )

        if self.profile in {"balanced", "robust"}:
            binary = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,
                11,
            )
            variants.append(
                OcrPreprocessVariant(
                    name="adaptive_threshold",
                    image=cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR),
                )
            )

        return tuple(variants[: self.max_variants])

    def _small_text_scale(self, cv2: Any, image: Any) -> float:
        import numpy as np

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
        )
        _, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
        heights = [
            int(row[cv2.CC_STAT_HEIGHT])
            for row in stats[1:]
            if 3 <= int(row[cv2.CC_STAT_HEIGHT]) <= 80
            and int(row[cv2.CC_STAT_AREA]) >= 6
            and int(row[cv2.CC_STAT_WIDTH]) >= 2
        ]
        if not heights:
            return 1.0
        median_height = float(np.median(heights))
        desired_scale = 1.0
        if median_height < 12.0:
            desired_scale = 2.0
        elif median_height < 20.0:
            desired_scale = 1.5
        height, width = image.shape[:2]
        for candidate_scale in (
            (desired_scale, 1.5)
            if desired_scale == 2.0
            else (desired_scale,)
        ):
            if (
                candidate_scale > 1.0
                and max(width, height) * candidate_scale
                <= _MAX_UPSCALED_EDGE
                and width * height * candidate_scale * candidate_scale
                <= _MAX_UPSCALED_PIXELS
            ):
                return candidate_scale
        return 1.0

    def _build_scaled_variant(
        self,
        cv2: Any,
        image: Any,
        scale: float,
    ) -> OcrPreprocessVariant:
        resized = cv2.resize(
            image,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC,
        )
        inverse_scale = 1.0 / scale
        return OcrPreprocessVariant(
            name=f"upscale_{scale:g}x",
            image=resized,
            to_original_transform=(
                (inverse_scale, 0.0, 0.0),
                (0.0, inverse_scale, 0.0),
                (0.0, 0.0, 1.0),
            ),
        )

    def _estimate_deskew_angle(
        self,
        cv2: Any,
        gray: Any,
    ) -> float | None:
        import numpy as np

        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        minimum_line_length = max(30, int(gray.shape[1] * 0.12))
        lines = cv2.HoughLinesP(
            edges,
            1,
            np.pi / 180.0,
            threshold=60,
            minLineLength=minimum_line_length,
            maxLineGap=20,
        )
        if lines is not None:
            line_angles: list[tuple[float, float]] = []
            for raw_line in lines.reshape(-1, 4):
                x1, y1, x2, y2 = (float(value) for value in raw_line)
                angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
                if 0.5 <= abs(angle) <= 10.0:
                    line_angles.append(
                        (math.hypot(x2 - x1, y2 - y1), angle)
                    )
            if line_angles:
                strongest_angles = [
                    angle
                    for _, angle in sorted(
                        line_angles,
                        key=lambda item: item[0],
                        reverse=True,
                    )[:12]
                ]
                correction = -float(np.median(strongest_angles))
                if abs(correction) >= 1.5:
                    return correction

        _, binary = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
        )
        points = np.column_stack(np.where(binary > 0))
        if len(points) < 20:
            return None
        angle = float(cv2.minAreaRect(points[:, ::-1].astype("float32"))[-1])
        if angle > 45.0:
            orientation = angle - 90.0
        elif angle < -45.0:
            orientation = angle + 90.0
        else:
            orientation = angle
        correction = -orientation
        if abs(correction) < 0.5 or abs(correction) > 10.0:
            return None
        return correction

    def _build_deskew_variant(
        self,
        cv2: Any,
        image: Any,
        angle: float,
    ) -> OcrPreprocessVariant:
        height, width = image.shape[:2]
        rotation = cv2.getRotationMatrix2D(
            (width / 2.0, height / 2.0),
            angle,
            1.0,
        )
        deskewed = cv2.warpAffine(
            image,
            rotation,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        inverse = cv2.invertAffineTransform(rotation)
        return OcrPreprocessVariant(
            name=f"deskew_{angle:+.2f}deg",
            image=deskewed,
            to_original_transform=(
                (
                    float(inverse[0][0]),
                    float(inverse[0][1]),
                    float(inverse[0][2]),
                ),
                (
                    float(inverse[1][0]),
                    float(inverse[1][1]),
                    float(inverse[1][2]),
                ),
                (0.0, 0.0, 1.0),
            ),
        )


class OcrEnginePool:
    def __init__(
        self,
        *,
        allowed_language_profiles: Sequence[OcrEngineLanguageProfile],
        model_root: Path,
        allow_model_download: bool,
        cache_size: int,
        engine_factory: Callable[..., Any] | None = None,
    ) -> None:
        if cache_size < 1:
            raise ValueError("OCR engine cache size must be positive.")
        if not allowed_language_profiles:
            raise ValueError("At least one OCR language profile must be allowed.")
        self.allowed_language_profiles = tuple(allowed_language_profiles)
        self.model_root = model_root
        self.allow_model_download = allow_model_download
        self.cache_size = cache_size
        self._engine_factory = engine_factory or _build_paddle_engine
        self._engines: OrderedDict[OcrEngineLanguageProfile, Any] = OrderedDict()
        self._lock = RLock()

    @property
    def cached_profiles(self) -> tuple[OcrEngineLanguageProfile, ...]:
        with self._lock:
            return tuple(self._engines)

    def resolve_profiles(
        self,
        language_profile: OcrLanguageProfile,
    ) -> tuple[OcrEngineLanguageProfile, ...]:
        if language_profile == "auto":
            return self.allowed_language_profiles
        if language_profile not in self.allowed_language_profiles:
            raise OcrEngineError(
                OcrErrorCode.OCR_LANGUAGE_UNSUPPORTED,
                f"Language profile `{language_profile}` is not allowed.",
            )
        return (language_profile,)

    def get_engine(self, language_profile: OcrEngineLanguageProfile) -> Any:
        self.resolve_profiles(language_profile)
        with self._lock:
            cached = self._engines.get(language_profile)
            if cached is not None:
                self._engines.move_to_end(language_profile)
                return cached

            det_model_dir, rec_model_dir = self._model_directories(language_profile)
            if not self.allow_model_download:
                missing = [
                    path
                    for path in (det_model_dir, rec_model_dir)
                    if not _contains_model_files(path)
                ]
                if missing:
                    missing_names = ", ".join(str(path) for path in missing)
                    raise OcrEngineError(
                        OcrErrorCode.OCR_MODEL_UNAVAILABLE,
                        (
                            f"Models for `{language_profile}` are unavailable at "
                            f"{missing_names}; runtime downloads are disabled."
                        ),
                    )

            try:
                engine = self._engine_factory(
                    profile=language_profile,
                    paddle_language=PADDLE_LANGUAGE_BY_PROFILE[language_profile],
                    det_model_dir=det_model_dir,
                    rec_model_dir=rec_model_dir,
                    allow_download=self.allow_model_download,
                )
            except OcrEngineError:
                raise
            except ImportError as exc:
                raise OcrEngineError(
                    OcrErrorCode.OCR_ENGINE_UNAVAILABLE,
                    "PaddleOCR is not installed.",
                ) from exc
            except Exception as exc:
                raise OcrEngineError(
                    OcrErrorCode.OCR_ENGINE_UNAVAILABLE,
                    f"Failed to initialize `{language_profile}` OCR engine: {exc}",
                ) from exc

            self._engines[language_profile] = engine
            while len(self._engines) > self.cache_size:
                _, evicted = self._engines.popitem(last=False)
                close = getattr(evicted, "close", None)
                if callable(close):
                    close()
            return engine

    def warmup(
        self,
        language_profiles: Sequence[OcrEngineLanguageProfile] | None = None,
        *,
        strict: bool = False,
    ) -> dict[OcrEngineLanguageProfile, str | None]:
        profiles = tuple(language_profiles or self.allowed_language_profiles)
        outcomes: dict[OcrEngineLanguageProfile, str | None] = {}
        for profile in profiles:
            try:
                self.get_engine(profile)
                outcomes[profile] = None
            except OcrEngineError as exc:
                outcomes[profile] = exc.code.value
                if strict:
                    raise
        return outcomes

    def clear(self) -> None:
        with self._lock:
            while self._engines:
                _, engine = self._engines.popitem(last=False)
                close = getattr(engine, "close", None)
                if callable(close):
                    close()

    def _model_directories(
        self,
        language_profile: OcrEngineLanguageProfile,
    ) -> tuple[Path, Path]:
        profile_root = self.model_root / language_profile
        return profile_root / "det", profile_root / "rec"


@dataclass(slots=True)
class _RecognizedBlock:
    text: str
    confidence: float
    polygon: list[tuple[float, float]]
    language: OcrEngineLanguageProfile
    preprocessing_variant: str

    @property
    def rect(self) -> tuple[float, float, float, float]:
        xs = [point[0] for point in self.polygon]
        ys = [point[1] for point in self.polygon]
        return min(xs), min(ys), max(xs), max(ys)


@dataclass(slots=True)
class _BlockCluster:
    members: list[_RecognizedBlock] = field(default_factory=list)

    def accepts(self, candidate: _RecognizedBlock) -> bool:
        for member in self.members:
            text_similarity = SequenceMatcher(
                None,
                _normalize_text(member.text),
                _normalize_text(candidate.text),
            ).ratio()
            if text_similarity < 0.80:
                continue
            if _rect_iou(member.rect, candidate.rect) >= 0.30:
                return True
            if _normalized_center_distance(member.rect, candidate.rect) <= 0.25:
                return True
        return False

    def add(self, candidate: _RecognizedBlock) -> None:
        self.members.append(candidate)

    def to_block(
        self,
        *,
        order_no: int,
        image_width: int,
        image_height: int,
    ) -> dict[str, Any]:
        primary = max(self.members, key=lambda member: member.confidence)
        confidence_weight = sum(member.confidence for member in self.members)
        if confidence_weight <= 0:
            confidence = 0.0
        else:
            confidence = sum(
                member.confidence * member.confidence for member in self.members
            ) / confidence_weight

        compatible_members = [
            member
            for member in self.members
            if len(member.polygon) == len(primary.polygon)
        ]
        polygon: list[tuple[float, float]] = []
        for point_index in range(len(primary.polygon)):
            point_weight = sum(
                max(member.confidence, 0.01) for member in compatible_members
            )
            polygon.append(
                (
                    sum(
                        member.polygon[point_index][0]
                        * max(member.confidence, 0.01)
                        for member in compatible_members
                    )
                    / point_weight,
                    sum(
                        member.polygon[point_index][1]
                        * max(member.confidence, 0.01)
                        for member in compatible_members
                    )
                    / point_weight,
                )
            )

        normalized_polygon = [
            {
                "x": min(
                    max(int(round(point[0])), 0),
                    max(image_width - 1, 0),
                ),
                "y": min(
                    max(int(round(point[1])), 0),
                    max(image_height - 1, 0),
                ),
            }
            for point in polygon
        ]
        pixel_rect = _pixel_rect(
            normalized_polygon,
            image_width=image_width,
            image_height=image_height,
        )
        sources = sorted(
            (
                {
                    "language": member.language,
                    "preprocessing_variant": member.preprocessing_variant,
                    "confidence": member.confidence,
                }
                for member in self.members
            ),
            key=lambda source: (
                -float(source["confidence"]),
                str(source["language"]),
                str(source["preprocessing_variant"]),
            ),
        )
        return {
            "order_no": order_no,
            "text": primary.text,
            "confidence": min(max(confidence, 0.0), 1.0),
            "polygon_points": normalized_polygon,
            "pixel_rect": pixel_rect,
            "ratio_rect": {
                "x_ratio": pixel_rect["x"] / image_width,
                "y_ratio": pixel_rect["y"] / image_height,
                "width_ratio": pixel_rect["width"] / image_width,
                "height_ratio": pixel_rect["height"] / image_height,
            },
            "language": primary.language,
            "preprocessing_variant": primary.preprocessing_variant,
            "languages": sorted({member.language for member in self.members}),
            "preprocessing_variants": sorted(
                {member.preprocessing_variant for member in self.members}
            ),
            "sources": sources,
        }


class OcrRecognitionPipeline:
    def __init__(
        self,
        *,
        engine_pool: OcrEnginePool,
        preprocessing_profile: OcrPreprocessingProfile,
        max_preprocess_variants: int,
        minimum_confidence: float,
    ) -> None:
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("OCR minimum confidence must be between 0 and 1.")
        self.engine_pool = engine_pool
        self.preprocessor = OcrPreprocessor(
            profile=preprocessing_profile,
            max_variants=max_preprocess_variants,
        )
        self.minimum_confidence = minimum_confidence

    def analyze(
        self,
        *,
        image: Any,
        language_profile: OcrLanguageProfile,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        image_height, image_width = image.shape[:2]
        profiles = self.engine_pool.resolve_profiles(language_profile)
        variants = self.preprocessor.build_variants(image)
        recognized: list[_RecognizedBlock] = []
        executed_variants: list[str] = []
        early_stopped_profiles: list[OcrEngineLanguageProfile] = []

        for profile in profiles:
            engine = self.engine_pool.get_engine(profile)
            profile_recognized: list[_RecognizedBlock] = []
            for variant in variants:
                if variant.name not in executed_variants:
                    executed_variants.append(variant.name)
                try:
                    result = engine.ocr(variant.image, cls=False)
                except Exception as exc:
                    raise OcrEngineError(
                        OcrErrorCode.OCR_ANALYSIS_FAILED,
                        (
                            f"OCR failed for language `{profile}` and preprocessing "
                            f"variant `{variant.name}`: {exc}"
                        ),
                    ) from exc
                for polygon, text, confidence in _iter_paddle_lines(result):
                    if confidence < self.minimum_confidence or not text.strip():
                        continue
                    mapped_polygon = variant.map_polygon_to_original(polygon)
                    if len(mapped_polygon) < 3:
                        continue
                    block = _RecognizedBlock(
                        text=text.strip(),
                        confidence=min(max(confidence, 0.0), 1.0),
                        polygon=mapped_polygon,
                        language=profile,
                        preprocessing_variant=variant.name,
                    )
                    recognized.append(block)
                    profile_recognized.append(block)
                if (
                    variant.name == "original"
                    and self._can_early_stop(profile_recognized)
                ):
                    early_stopped_profiles.append(profile)
                    break

        clusters: list[_BlockCluster] = []
        for candidate in sorted(
            recognized,
            key=lambda block: (-block.confidence, block.rect[1], block.rect[0]),
        ):
            cluster = next(
                (item for item in clusters if item.accepts(candidate)),
                None,
            )
            if cluster is None:
                clusters.append(_BlockCluster(members=[candidate]))
            else:
                cluster.add(candidate)

        unordered_blocks = [
            cluster.to_block(
                order_no=0,
                image_width=image_width,
                image_height=image_height,
            )
            for cluster in clusters
        ]
        unordered_blocks.sort(
            key=lambda block: (
                block["pixel_rect"]["y"],
                block["pixel_rect"]["x"],
                block["text"],
            )
        )
        for order_no, block in enumerate(unordered_blocks, start=1):
            block["order_no"] = order_no

        return {
            "engine_name": "paddleocr",
            "image_width": image_width,
            "image_height": image_height,
            "language_profile": language_profile,
            "language_profiles": list(profiles),
            "preprocessing_variants": executed_variants,
            "preprocessing_early_stopped_profiles": early_stopped_profiles,
            "elapsed_ms": (time.perf_counter() - started_at) * 1000.0,
            "blocks": unordered_blocks,
        }

    def _can_early_stop(
        self,
        recognized: Sequence[_RecognizedBlock],
    ) -> bool:
        if self.preprocessor.profile == "robust" or not recognized:
            return False
        confidences = [block.confidence for block in recognized]
        average_confidence = sum(confidences) / len(confidences)
        high_confidence_ratio = sum(
            confidence >= _EARLY_STOP_HIGH_CONFIDENCE_FLOOR
            for confidence in confidences
        ) / len(confidences)
        return (
            average_confidence >= _EARLY_STOP_MIN_AVERAGE_CONFIDENCE
            and high_confidence_ratio
            >= _EARLY_STOP_MIN_HIGH_CONFIDENCE_RATIO
        )


def _build_paddle_engine(
    *,
    profile: OcrEngineLanguageProfile,
    paddle_language: str,
    det_model_dir: Path,
    rec_model_dir: Path,
    allow_download: bool,
) -> Any:
    _ = (profile, allow_download)
    from paddleocr import PaddleOCR

    return PaddleOCR(
        use_angle_cls=False,
        lang=paddle_language,
        show_log=False,
        det_model_dir=str(det_model_dir),
        rec_model_dir=str(rec_model_dir),
    )


def _load_cv2() -> Any:
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover
        raise OcrEngineError(
            OcrErrorCode.OCR_ENGINE_UNAVAILABLE,
            "OpenCV is not installed.",
        ) from exc
    return cv2


def _contains_model_files(path: Path) -> bool:
    if not path.is_dir():
        return False
    file_names = {item.name for item in path.rglob("*") if item.is_file()}
    return {"inference.pdmodel", "inference.pdiparams"} <= file_names


def _iter_paddle_lines(
    result: Any,
) -> list[tuple[Sequence[Sequence[float]], str, float]]:
    lines: list[tuple[Sequence[Sequence[float]], str, float]] = []
    if not isinstance(result, (list, tuple)):
        return lines
    for group in result:
        candidates = [group] if _is_paddle_line(group) else group
        if not isinstance(candidates, (list, tuple)):
            continue
        for line in candidates:
            if not _is_paddle_line(line):
                continue
            polygon = line[0]
            recognition = line[1]
            try:
                text = str(recognition[0])
                confidence = float(recognition[1])
            except (IndexError, TypeError, ValueError):
                continue
            lines.append((polygon, text, confidence))
    return lines


def _is_paddle_line(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and isinstance(value[0], (list, tuple))
        and len(value[0]) >= 3
        and isinstance(value[1], (list, tuple))
        and len(value[1]) >= 1
        and all(
            isinstance(point, (list, tuple))
            and len(point) >= 2
            and isinstance(point[0], Real)
            and isinstance(point[1], Real)
            for point in value[0]
        )
    )


def _normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _rect_iou(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    intersection_width = max(
        0.0,
        min(first[2], second[2]) - max(first[0], second[0]),
    )
    intersection_height = max(
        0.0,
        min(first[3], second[3]) - max(first[1], second[1]),
    )
    intersection = intersection_width * intersection_height
    first_area = max(0.0, first[2] - first[0]) * max(
        0.0, first[3] - first[1]
    )
    second_area = max(0.0, second[2] - second[0]) * max(
        0.0, second[3] - second[1]
    )
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def _normalized_center_distance(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    first_center = ((first[0] + first[2]) / 2.0, (first[1] + first[3]) / 2.0)
    second_center = (
        (second[0] + second[2]) / 2.0,
        (second[1] + second[3]) / 2.0,
    )
    distance = math.dist(first_center, second_center)
    scale = max(
        first[2] - first[0],
        first[3] - first[1],
        second[2] - second[0],
        second[3] - second[1],
        1.0,
    )
    return distance / scale


def _pixel_rect(
    polygon_points: list[dict[str, int]],
    *,
    image_width: int,
    image_height: int,
) -> dict[str, int]:
    xs = [point["x"] for point in polygon_points]
    ys = [point["y"] for point in polygon_points]
    left = min(xs)
    top = min(ys)
    right = min(max(xs) + 1, image_width)
    bottom = min(max(ys) + 1, image_height)
    return {
        "x": left,
        "y": top,
        "width": max(1, right - left),
        "height": max(1, bottom - top),
    }
