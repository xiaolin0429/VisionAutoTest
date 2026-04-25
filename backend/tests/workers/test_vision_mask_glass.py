from __future__ import annotations

from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from app.workers.vision import (
    DefaultVisionAssertionAdapter,
    MaskRegionRatio,
    TemplateAssertionContext,
)

pytestmark = pytest.mark.vision


MASK_REGION = MaskRegionRatio(
    x_ratio=0.25,
    y_ratio=0.25,
    width_ratio=0.4,
    height_ratio=0.38,
)


def _encode_png(image) -> bytes:
    success, encoded = cv2.imencode(".png", image)
    assert success
    return encoded.tobytes()


def _decode_png(image_bytes: bytes):
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    return image


def _make_base_image():
    height, width = 60, 80
    image = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            image[y, x] = (
                (x * 3 + y) % 256,
                (y * 4 + x) % 256,
                (x * 2 + y * 3) % 256,
            )
    cv2.rectangle(image, (8, 8), (70, 50), (230, 230, 230), thickness=1)
    cv2.line(image, (0, 30), (79, 30), (20, 180, 240), thickness=1)
    return image


def _write_baseline(tmp_path: Path, image) -> Path:
    path = tmp_path / "baseline.png"
    path.write_bytes(_encode_png(image))
    return path


def _assertion_context(tmp_path: Path, baseline_image) -> TemplateAssertionContext:
    return TemplateAssertionContext(
        template_id=1,
        template_name="glass-mask-template",
        match_strategy="template",
        threshold_value=0.999,
        baseline_media_object_id=1001,
        baseline_file_path=_write_baseline(tmp_path, baseline_image),
        mask_regions=[MASK_REGION],
    )


def _mask_bounds(
    adapter: DefaultVisionAssertionAdapter, image
) -> tuple[int, int, int, int]:
    height, width = image.shape[:2]
    bounds = adapter._build_region_bounds(width, height, MASK_REGION)
    assert bounds is not None
    return bounds


def _paint_mask_region(adapter: DefaultVisionAssertionAdapter, image) -> None:
    left, top, right, bottom = _mask_bounds(adapter, image)
    for y in range(top, bottom):
        for x in range(left, right):
            image[y, x] = (
                (x * 7) % 256,
                255 - ((y * 5) % 180),
                (x * 3 + y * 11) % 256,
            )


def _red_pixel_count(image) -> int:
    red_pixels = (
        (image[:, :, 2] > 220) & (image[:, :, 1] < 60) & (image[:, :, 0] < 60)
    )
    return int(red_pixels.sum())


def test_template_assertion_actual_artifact_renders_glass_mask(tmp_path: Path):
    adapter = DefaultVisionAssertionAdapter()
    baseline = _make_base_image()
    actual = baseline.copy()
    _paint_mask_region(adapter, actual)

    outcome = adapter.assert_template(
        context=_assertion_context(tmp_path, baseline),
        actual_png_bytes=_encode_png(actual),
        actual_file_name="actual.png",
        threshold_override=None,
    )

    assert outcome.status == "passed"
    assert outcome.actual_artifact is not None
    actual_display = _decode_png(outcome.actual_artifact.content_bytes)
    left, top, right, bottom = _mask_bounds(adapter, actual_display)
    mask_roi = actual_display[top:bottom, left:right]
    black_ratio = float(np.all(mask_roi < 8, axis=2).mean())

    assert black_ratio < 0.05
    assert float(mask_roi.std()) > 8.0
    assert not np.array_equal(mask_roi, actual[top:bottom, left:right])


def test_template_assertion_diff_ignores_mask_but_marks_outside_change(
    tmp_path: Path,
):
    adapter = DefaultVisionAssertionAdapter()
    baseline = _make_base_image()
    actual = baseline.copy()
    _paint_mask_region(adapter, actual)
    actual[42:56, 52:76] = (0, 0, 0)

    outcome = adapter.assert_template(
        context=_assertion_context(tmp_path, baseline),
        actual_png_bytes=_encode_png(actual),
        actual_file_name="actual.png",
        threshold_override=None,
    )

    assert outcome.status == "failed"
    assert outcome.diff_artifact is not None
    diff_display = _decode_png(outcome.diff_artifact.content_bytes)
    left, top, right, bottom = _mask_bounds(adapter, diff_display)

    assert _red_pixel_count(diff_display) > 0
    assert _red_pixel_count(diff_display[top:bottom, left:right]) == 0


def test_processed_preview_uses_glass_mask_without_touching_outside_region():
    adapter = DefaultVisionAssertionAdapter()
    source = _make_base_image()

    preview = adapter.build_mask_preview(
        image_png_bytes=_encode_png(source),
        mask_regions=[MASK_REGION],
    )

    processed = _decode_png(preview["processed_png_bytes"])
    left, top, right, bottom = _mask_bounds(adapter, processed)
    mask_roi = processed[top:bottom, left:right]

    assert float(np.all(mask_roi < 8, axis=2).mean()) < 0.05
    assert float(mask_roi.std()) > 8.0
    assert np.array_equal(processed[0:8, 0:8], source[0:8, 0:8])
