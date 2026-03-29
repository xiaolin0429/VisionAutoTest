from __future__ import annotations

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
        expected_image, actual_image = self._normalize_sizes(cv2, baseline_image, actual_image)
        expected_image = self._apply_masks(expected_image, context.mask_regions)
        actual_image = self._apply_masks(actual_image, context.mask_regions)

        expected_gray = cv2.cvtColor(expected_image, cv2.COLOR_BGR2GRAY)
        actual_gray = cv2.cvtColor(actual_image, cv2.COLOR_BGR2GRAY)
        score = float(cv2.matchTemplate(actual_gray, expected_gray, cv2.TM_CCOEFF_NORMED).max())

        threshold = float(threshold_override if threshold_override is not None else context.threshold_value)
        actual_artifact = VisionArtifact(
            file_name=actual_file_name,
            content_type="image/png",
            content_bytes=self._encode_png(cv2, actual_image),
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
            content_bytes=self._build_diff_png(cv2, expected_image, actual_image),
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
        recognized_text = self._run_ocr(image_png_bytes)
        normalized_expected = expected_text if case_sensitive else expected_text.lower()
        normalized_actual = recognized_text if case_sensitive else recognized_text.lower()

        if match_mode == "exact":
            passed = normalized_actual == normalized_expected
        else:
            passed = normalized_expected in normalized_actual

        return VisionAssertionOutcome(
            status="passed" if passed else "failed",
            score_value=1.0 if passed else 0.0,
            error_message=None if passed else f"OCR assertion failed: expected `{expected_text}` but got `{recognized_text}`.",
            actual_artifact=VisionArtifact(
                file_name=image_file_name,
                content_type="image/png",
                content_bytes=image_png_bytes,
                artifact_type="ocr_screenshot",
            ),
        )

    def _run_ocr(self, image_png_bytes: bytes) -> str:
        cv2 = self._load_cv2()
        paddle_ocr = self._load_paddle_ocr()
        image = self._decode_image(cv2, image_png_bytes)
        result = paddle_ocr.ocr(image, cls=False)
        texts: list[str] = []
        for line_group in result or []:
            if not line_group:
                continue
            for line in line_group:
                if len(line) < 2 or not isinstance(line[1], tuple):
                    continue
                text = str(line[1][0]).strip()
                if text:
                    texts.append(text)
        return " ".join(texts).strip()

    def _load_cv2(self):
        try:
            import cv2
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("OpenCV is not installed. Please install `opencv-python-headless`.") from exc
        return cv2

    def _load_paddle_ocr(self):
        if self.__class__._ocr_engine is not None:
            return self.__class__._ocr_engine
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("PaddleOCR is not installed. Please install `paddleocr`.") from exc
        self.__class__._ocr_engine = PaddleOCR(use_angle_cls=False, lang="ch", show_log=False)
        return self.__class__._ocr_engine

    def _decode_image(self, cv2, image_bytes: bytes):
        import numpy as np

        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
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
            left = int(width * region.x_ratio)
            top = int(height * region.y_ratio)
            right = min(width, max(left + 1, int(width * (region.x_ratio + region.width_ratio))))
            bottom = min(height, max(top + 1, int(height * (region.y_ratio + region.height_ratio))))
            masked_image[top:bottom, left:right] = 0
        return masked_image

    def _build_diff_png(self, cv2, expected_image, actual_image) -> bytes:
        diff = cv2.absdiff(expected_image, actual_image)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresholded = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
        highlighted = actual_image.copy()
        highlighted[thresholded > 0] = (0, 0, 255)
        return self._encode_png(cv2, highlighted)
