from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


@dataclass(slots=True)
class MaskRegionRatio:
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float


@dataclass(slots=True)
class TemplateAssertionContext:
    template_id: int
    template_name: str
    match_strategy: str
    threshold_value: float
    baseline_media_object_id: int
    baseline_file_path: Path
    mask_regions: list[MaskRegionRatio]


@dataclass(slots=True)
class VisionArtifact:
    file_name: str
    content_type: str
    content_bytes: bytes
    artifact_type: str


@dataclass(slots=True)
class VisionAssertionOutcome:
    status: Literal["passed", "failed"]
    score_value: float | None = None
    error_message: str | None = None
    expected_media_object_id: int | None = None
    actual_artifact: VisionArtifact | None = None
    diff_artifact: VisionArtifact | None = None


@dataclass(slots=True)
class OcrLocateResult:
    center_x: float
    center_y: float
    rect_x: int
    rect_y: int
    rect_width: int
    rect_height: int
    matched_text: str
    confidence: float


@dataclass(slots=True)
class TemplateLocateResult:
    center_x: float
    center_y: float
    rect_x: int
    rect_y: int
    rect_width: int
    rect_height: int
    score: float


class VisionAssertionAdapter(Protocol):
    def assert_template(
        self,
        *,
        context: TemplateAssertionContext,
        actual_png_bytes: bytes,
        actual_file_name: str,
        threshold_override: float | None,
    ) -> VisionAssertionOutcome: ...

    def assert_ocr(
        self,
        *,
        image_png_bytes: bytes,
        image_file_name: str,
        expected_text: str,
        match_mode: str,
        case_sensitive: bool,
    ) -> VisionAssertionOutcome: ...

    def analyze_ocr(
        self,
        *,
        image_png_bytes: bytes,
    ) -> dict: ...

    def build_mask_preview(
        self,
        *,
        image_png_bytes: bytes,
        mask_regions: list[MaskRegionRatio],
    ) -> dict: ...

    def locate_by_ocr(
        self,
        *,
        image_png_bytes: bytes,
        target_text: str,
        match_mode: str,
        case_sensitive: bool,
        occurrence: int,
    ) -> OcrLocateResult: ...

    def locate_by_template(
        self,
        *,
        context: TemplateAssertionContext,
        actual_png_bytes: bytes,
        threshold_override: float | None,
    ) -> TemplateLocateResult: ...


def build_vision_assertion_adapter() -> VisionAssertionAdapter:
    return DefaultVisionAssertionAdapter()


class DefaultVisionAssertionAdapter:
    _ocr_engine = None

    def assert_template(
        self,
        *,
        context: TemplateAssertionContext,
        actual_png_bytes: bytes,
        actual_file_name: str,
        threshold_override: float | None,
    ) -> VisionAssertionOutcome:
        cv2 = self._load_cv2()

        baseline_bytes = context.baseline_file_path.read_bytes()
        baseline_image = self._decode_image(cv2, baseline_bytes)
        actual_image = self._decode_image(cv2, actual_png_bytes)
        normalized_expected, normalized_actual = self._normalize_sizes(
            cv2, baseline_image, actual_image
        )
        masked_expected = self._apply_masks(
            normalized_expected, context.mask_regions
        )
        masked_actual = self._apply_masks(normalized_actual, context.mask_regions)

        expected_gray = cv2.cvtColor(masked_expected, cv2.COLOR_BGR2GRAY)
        actual_gray = cv2.cvtColor(masked_actual, cv2.COLOR_BGR2GRAY)
        score = float(
            cv2.matchTemplate(actual_gray, expected_gray, cv2.TM_CCOEFF_NORMED).max()
        )

        threshold = float(
            threshold_override
            if threshold_override is not None
            else context.threshold_value
        )
        actual_display_image = self._render_glass_mask_regions(
            cv2, normalized_actual, context.mask_regions
        )
        actual_artifact = VisionArtifact(
            file_name=actual_file_name,
            content_type="image/png",
            content_bytes=self._encode_png(cv2, actual_display_image),
            artifact_type="actual_screenshot",
        )
        if score >= threshold:
            return VisionAssertionOutcome(
                status="passed",
                score_value=score,
                expected_media_object_id=context.baseline_media_object_id,
                actual_artifact=actual_artifact,
            )

        diff_artifact = VisionArtifact(
            file_name=actual_file_name.replace(".png", "-diff.png"),
            content_type="image/png",
            content_bytes=self._build_diff_png(
                cv2,
                masked_expected,
                masked_actual,
                base_image=normalized_actual,
                mask_regions=context.mask_regions,
            ),
            artifact_type="diff_screenshot",
        )
        return VisionAssertionOutcome(
            status="failed",
            score_value=score,
            error_message=f"Template assertion failed: score {score:.4f} is below threshold {threshold:.4f}.",
            expected_media_object_id=context.baseline_media_object_id,
            actual_artifact=actual_artifact,
            diff_artifact=diff_artifact,
        )

    def assert_ocr(
        self,
        *,
        image_png_bytes: bytes,
        image_file_name: str,
        expected_text: str,
        match_mode: str,
        case_sensitive: bool,
    ) -> VisionAssertionOutcome:
        analysis = self.analyze_ocr(image_png_bytes=image_png_bytes)
        recognized_text = " ".join(
            str(block["text"]).strip()
            for block in analysis["blocks"]
            if str(block["text"]).strip()
        ).strip()
        normalized_expected = self._normalize_ocr_text(expected_text, case_sensitive)
        normalized_actual = self._normalize_ocr_text(recognized_text, case_sensitive)

        if match_mode == "exact":
            passed = normalized_actual == normalized_expected
        else:
            passed = normalized_expected in normalized_actual

        return VisionAssertionOutcome(
            status="passed" if passed else "failed",
            score_value=1.0 if passed else 0.0,
            error_message=None
            if passed
            else f"OCR assertion failed: expected `{expected_text}` but got `{recognized_text}`.",
            actual_artifact=VisionArtifact(
                file_name=image_file_name,
                content_type="image/png",
                content_bytes=image_png_bytes,
                artifact_type="ocr_screenshot",
            ),
        )

    def analyze_ocr(
        self,
        *,
        image_png_bytes: bytes,
    ) -> dict:
        cv2 = self._load_cv2()
        paddle_ocr = self._load_paddle_ocr()
        image = self._decode_image(cv2, image_png_bytes)
        image_height, image_width = image.shape[:2]
        result = paddle_ocr.ocr(image, cls=False)
        blocks: list[dict] = []
        order_no = 1
        for line_group in result or []:
            if not line_group:
                continue
            for line in line_group:
                if len(line) < 2 or not isinstance(line[1], tuple):
                    continue
                if not isinstance(line[0], (list, tuple)) or not line[0]:
                    continue
                text = str(line[1][0]).strip()
                confidence = float(line[1][1]) if len(line[1]) > 1 else 0.0
                polygon_points = [
                    self._normalize_point(point, image_width, image_height)
                    for point in line[0]
                ]
                if not polygon_points:
                    continue
                pixel_rect = self._build_pixel_rect(
                    polygon_points, image_width, image_height
                )
                blocks.append(
                    {
                        "order_no": order_no,
                        "text": text,
                        "confidence": confidence,
                        "polygon_points": polygon_points,
                        "pixel_rect": pixel_rect,
                        "ratio_rect": self._build_ratio_rect(
                            pixel_rect, image_width, image_height
                        ),
                    }
                )
                order_no += 1
        return {
            "engine_name": "paddleocr",
            "image_width": image_width,
            "image_height": image_height,
            "blocks": blocks,
        }

    def build_mask_preview(
        self,
        *,
        image_png_bytes: bytes,
        mask_regions: list[MaskRegionRatio],
    ) -> dict:
        cv2 = self._load_cv2()
        image = self._decode_image(cv2, image_png_bytes)
        image_height, image_width = image.shape[:2]
        overlay_image = self._build_overlay_image(cv2, image, mask_regions)
        processed_image = self._build_processed_preview_image(cv2, image, mask_regions)
        return {
            "image_width": image_width,
            "image_height": image_height,
            "overlay_png_bytes": self._encode_png(cv2, overlay_image),
            "processed_png_bytes": self._encode_png(cv2, processed_image),
        }

    def locate_by_ocr(
        self,
        *,
        image_png_bytes: bytes,
        target_text: str,
        match_mode: str = "contains",
        case_sensitive: bool = False,
        occurrence: int = 1,
    ) -> OcrLocateResult:
        analysis = self.analyze_ocr(image_png_bytes=image_png_bytes)
        normalized_target = self._normalize_ocr_text(target_text, case_sensitive)
        matched_count = 0
        for block in analysis["blocks"]:
            block_text = str(block["text"]).strip()
            normalized_block = self._normalize_ocr_text(block_text, case_sensitive)
            if match_mode == "exact":
                is_match = normalized_block == normalized_target
            else:
                is_match = normalized_target in normalized_block
            if is_match:
                matched_count += 1
                if matched_count == occurrence:
                    rect = block["pixel_rect"]
                    return OcrLocateResult(
                        center_x=rect["x"] + rect["width"] / 2,
                        center_y=rect["y"] + rect["height"] / 2,
                        rect_x=rect["x"],
                        rect_y=rect["y"],
                        rect_width=rect["width"],
                        rect_height=rect["height"],
                        matched_text=block_text,
                        confidence=float(block["confidence"]),
                    )
        if matched_count == 0:
            raise RuntimeError(
                f"OCR locate failed: text `{target_text}` not found on screen."
            )
        raise RuntimeError(
            f"OCR locate failed: text `{target_text}` found {matched_count} time(s), "
            f"but occurrence {occurrence} was requested."
        )

    def locate_by_template(
        self,
        *,
        context: TemplateAssertionContext,
        actual_png_bytes: bytes,
        threshold_override: float | None,
    ) -> TemplateLocateResult:
        cv2 = self._load_cv2()

        baseline_bytes = context.baseline_file_path.read_bytes()
        baseline_image = self._decode_image(cv2, baseline_bytes)
        actual_image = self._decode_image(cv2, actual_png_bytes)
        expected_image = self._apply_masks(baseline_image, context.mask_regions)

        expected_gray = cv2.cvtColor(expected_image, cv2.COLOR_BGR2GRAY)
        actual_gray = cv2.cvtColor(actual_image, cv2.COLOR_BGR2GRAY)
        expected_height, expected_width = expected_gray.shape[:2]
        actual_height, actual_width = actual_gray.shape[:2]
        if expected_width > actual_width or expected_height > actual_height:
            raise RuntimeError(
                "Template locate failed: template image is larger than the current screenshot."
            )
        result = cv2.matchTemplate(actual_gray, expected_gray, cv2.TM_CCOEFF_NORMED)
        _, max_score, _, max_loc = cv2.minMaxLoc(result)

        threshold = float(
            threshold_override
            if threshold_override is not None
            else context.threshold_value
        )
        if float(max_score) < threshold:
            raise RuntimeError(
                f"Template locate failed: score {float(max_score):.4f} is below threshold {threshold:.4f}."
            )

        rect_x, rect_y = int(max_loc[0]), int(max_loc[1])
        rect_height, rect_width = expected_height, expected_width
        return TemplateLocateResult(
            center_x=rect_x + rect_width / 2,
            center_y=rect_y + rect_height / 2,
            rect_x=rect_x,
            rect_y=rect_y,
            rect_width=rect_width,
            rect_height=rect_height,
            score=float(max_score),
        )

    def _load_cv2(self):
        try:
            import cv2
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "OpenCV is not installed. Please install `opencv-python-headless`."
            ) from exc
        return cv2

    def _load_paddle_ocr(self):
        if self.__class__._ocr_engine is not None:
            return self.__class__._ocr_engine
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "PaddleOCR is not installed. Please install `paddleocr`."
            ) from exc
        self.__class__._ocr_engine = PaddleOCR(
            use_angle_cls=False, lang="ch", show_log=False
        )
        return self.__class__._ocr_engine

    def _decode_image(self, cv2, image_bytes: bytes):
        import numpy as np

        image = cv2.imdecode(
            np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        if image is None:
            raise RuntimeError("Failed to decode image bytes.")
        return image

    def _encode_png(self, cv2, image) -> bytes:
        success, encoded = cv2.imencode(".png", image)
        if not success:
            raise RuntimeError("Failed to encode image to PNG.")
        return encoded.tobytes()

    def _normalize_sizes(self, cv2, baseline_image, actual_image):
        baseline_height, baseline_width = baseline_image.shape[:2]
        actual_height, actual_width = actual_image.shape[:2]
        if (baseline_width, baseline_height) == (actual_width, actual_height):
            return baseline_image, actual_image
        resized_actual = cv2.resize(actual_image, (baseline_width, baseline_height))
        return baseline_image, resized_actual

    def _apply_masks(self, image, mask_regions: list[MaskRegionRatio]):
        masked_image = image.copy()
        height, width = masked_image.shape[:2]
        for region in mask_regions:
            bounds = self._build_region_bounds(width, height, region)
            if bounds is None:
                continue
            left, top, right, bottom = bounds
            masked_image[top:bottom, left:right] = 0
        return masked_image

    def _build_processed_preview_image(
        self, cv2, image, mask_regions: list[MaskRegionRatio]
    ):
        return self._render_glass_mask_regions(cv2, image, mask_regions)

    def _build_overlay_image(self, cv2, image, mask_regions: list[MaskRegionRatio]):
        overlay = image.copy()
        layer = image.copy()
        height, width = image.shape[:2]
        for region in mask_regions:
            bounds = self._build_region_bounds(width, height, region)
            if bounds is None:
                continue
            left, top, right, bottom = bounds
            cv2.rectangle(
                layer, (left, top), (right - 1, bottom - 1), (0, 165, 255), thickness=-1
            )
            cv2.rectangle(
                overlay, (left, top), (right - 1, bottom - 1), (0, 90, 255), thickness=2
            )
        overlay = cv2.addWeighted(layer, 0.22, overlay, 0.78, 0)
        return overlay

    def _build_region_bounds(
        self, image_width: int, image_height: int, region: MaskRegionRatio
    ) -> tuple[int, int, int, int] | None:
        left = int(image_width * region.x_ratio)
        top = int(image_height * region.y_ratio)
        right = min(
            image_width,
            max(left + 1, int(image_width * (region.x_ratio + region.width_ratio))),
        )
        bottom = min(
            image_height,
            max(top + 1, int(image_height * (region.y_ratio + region.height_ratio))),
        )
        left = max(0, min(left, image_width))
        top = max(0, min(top, image_height))
        if right <= left or bottom <= top:
            return None
        return left, top, right, bottom

    def _render_glass_mask_regions(
        self,
        cv2,
        image,
        mask_regions: list[MaskRegionRatio],
        *,
        fill_color: tuple[int, int, int] = (255, 245, 215),
        border_color: tuple[int, int, int] = (255, 190, 80),
        fill_alpha: float = 0.32,
        blur_kernel: int = 17,
        border_thickness: int = 2,
    ):
        display_image = image.copy()
        height, width = display_image.shape[:2]
        for region in mask_regions:
            bounds = self._build_region_bounds(width, height, region)
            if bounds is None:
                continue
            left, top, right, bottom = bounds
            region_image = display_image[top:bottom, left:right]
            if region_image.size == 0:
                continue

            glass_region = region_image.copy()
            region_height, region_width = glass_region.shape[:2]
            kernel = min(blur_kernel, region_width, region_height)
            if kernel >= 3:
                if kernel % 2 == 0:
                    kernel -= 1
                glass_region = cv2.GaussianBlur(glass_region, (kernel, kernel), 0)

            tint = glass_region.copy()
            tint[:, :] = fill_color
            glass_region = cv2.addWeighted(
                tint, fill_alpha, glass_region, 1 - fill_alpha, 0
            )
            display_image[top:bottom, left:right] = glass_region
            cv2.rectangle(
                display_image,
                (left, top),
                (right - 1, bottom - 1),
                border_color,
                thickness=max(1, border_thickness),
            )
        return display_image

    def _normalize_point(self, point, image_width: int, image_height: int) -> dict:
        raw_x = float(point[0]) if len(point) > 0 else 0.0
        raw_y = float(point[1]) if len(point) > 1 else 0.0
        x = min(max(int(round(raw_x)), 0), max(image_width - 1, 0))
        y = min(max(int(round(raw_y)), 0), max(image_height - 1, 0))
        return {"x": x, "y": y}

    def _build_pixel_rect(
        self, polygon_points: list[dict], image_width: int, image_height: int
    ) -> dict:
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

    def _build_ratio_rect(
        self, pixel_rect: dict, image_width: int, image_height: int
    ) -> dict:
        if image_width <= 0 or image_height <= 0:
            raise RuntimeError(
                "Image dimensions must be greater than 0 for OCR ratio conversion."
            )
        return {
            "x_ratio": pixel_rect["x"] / image_width,
            "y_ratio": pixel_rect["y"] / image_height,
            "width_ratio": pixel_rect["width"] / image_width,
            "height_ratio": pixel_rect["height"] / image_height,
        }

    def _normalize_ocr_text(self, text: str, case_sensitive: bool) -> str:
        """Normalize OCR text for comparison: NFKC unicode, collapse whitespace."""
        t = unicodedata.normalize("NFKC", text)
        t = re.sub(r"\s+", " ", t).strip()
        return t if case_sensitive else t.lower()

    def _build_diff_png(
        self,
        cv2,
        expected_image,
        actual_image,
        *,
        base_image=None,
        mask_regions: list[MaskRegionRatio] | None = None,
    ) -> bytes:
        diff = cv2.absdiff(expected_image, actual_image)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresholded = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
        highlighted = actual_image.copy() if base_image is None else base_image.copy()
        highlighted[thresholded > 0] = (0, 0, 255)
        if mask_regions:
            highlighted = self._render_glass_mask_regions(
                cv2, highlighted, mask_regions
            )
        return self._encode_png(cv2, highlighted)
