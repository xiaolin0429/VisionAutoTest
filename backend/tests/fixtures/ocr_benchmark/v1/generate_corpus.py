"""Render the versioned OCR benchmark corpus with a real Chromium engine.

DOM geometry is used only while generating frozen ground-truth annotations.
The OCR benchmark and product target resolver consume only PNG pixels and the
checked-in manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

RANDOM_SEED = 20260816
CORPUS_VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parent
SOURCE_HTML = ROOT / "corpus.html"
DEFAULT_CHROME = Path(
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)

SCENES: tuple[dict[str, Any], ...] = (
    {
        "id": "clear_zh_en",
        "viewport": (1280, 720),
        "language_profile": "zh_en",
        "quality": "clear",
        "effects": ("light_theme",),
        "fonts": (
            "Arial",
            "PingFang SC",
            "Trebuchet MS",
            "Georgia",
            "Courier New",
            "Times New Roman",
        ),
        "font_sizes_px": (18, 20, 22, 26, 34),
    },
    {
        "id": "clear_en_dark",
        "viewport": (1920, 1080),
        "language_profile": "en",
        "quality": "clear",
        "effects": ("dark_theme",),
        "fonts": (
            "Arial",
            "Trebuchet MS",
            "Times New Roman",
            "Courier New",
            "Georgia",
        ),
        "font_sizes_px": (16, 20, 22, 28, 32),
    },
    {
        "id": "disturbed_japanese",
        "viewport": (1440, 900),
        "language_profile": "japan",
        "quality": "disturbed",
        "effects": (
            "texture",
            "low_contrast",
            "blur_0.45px",
            "tilt_plus_10deg",
            "tilt_minus_10deg",
        ),
        "fonts": (
            "Hiragino Kaku Gothic ProN",
            "Yu Gothic",
            "Yu Mincho",
            "Hiragino Mincho ProN",
        ),
        "font_sizes_px": (20, 22, 24, 30),
    },
    {
        "id": "disturbed_korean_mobile",
        "viewport": (390, 844),
        "language_profile": "korean",
        "quality": "disturbed",
        "effects": (
            "dark_theme",
            "texture",
            "low_contrast",
            "partial_occlusion",
        ),
        "fonts": ("Apple SD Gothic Neo",),
        "font_sizes_px": (17, 18, 20, 26),
    },
)

ANNOTATION_SCRIPT = """
() => {
  const round = value => Math.round(Number(value) * 1000) / 1000;
  const rectObject = rect => ({
    x: round(rect.x),
    y: round(rect.y),
    width: round(rect.width),
    height: round(rect.height)
  });
  const inputTextRect = element => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d");
    context.font = style.font;
    const text = element.dataset.text;
    const metrics = context.measureText(text);
    const fontSize = Number.parseFloat(style.fontSize);
    const lineHeight = Number.parseFloat(style.lineHeight) || fontSize * 1.2;
    const borderLeft = Number.parseFloat(style.borderLeftWidth) || 0;
    const paddingLeft = Number.parseFloat(style.paddingLeft) || 0;
    return {
      x: round(rect.x + borderLeft + paddingLeft),
      y: round(rect.y + (rect.height - lineHeight) / 2),
      width: round(metrics.width),
      height: round(lineHeight)
    };
  };
  return Array.from(
    document.querySelectorAll(".scene.active [data-benchmark-id]")
  ).map(element => {
    const textRect = element.dataset.inputText === "true"
      ? inputTextRect(element)
      : rectObject(element.getBoundingClientRect());
    const actionElement = element.dataset.actionId
      ? document.getElementById(element.dataset.actionId)
      : null;
    return {
      id: element.dataset.benchmarkId,
      text: element.dataset.text,
      language: element.dataset.language,
      role: element.dataset.role,
      target: element.dataset.target,
      match_mode: element.dataset.matchMode || null,
      ambiguity_group: element.dataset.ambiguityGroup || null,
      action_point: element.dataset.actionPoint || "text_center",
      text_rect_css: textRect,
      action_rect_css: actionElement
        ? rectObject(actionElement.getBoundingClientRect())
        : textRect
    };
  });
}
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Regenerate the checked-in OCR benchmark corpus."
    )
    parser.add_argument(
        "--chrome-executable",
        type=Path,
        default=DEFAULT_CHROME,
        help="Chrome/Chromium executable used for deterministic rendering.",
    )
    return parser.parse_args()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_dimensions(image_bytes: bytes) -> tuple[int, int]:
    if len(image_bytes) < 24 or not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Benchmark renderer did not return a valid PNG.")
    return struct.unpack(">II", image_bytes[16:24])


def _scale_rect(
    rect: Mapping[str, object],
    *,
    device_scale_factor: int,
) -> dict[str, float]:
    return {
        key: round(float(rect[key]) * device_scale_factor, 3)
        for key in ("x", "y", "width", "height")
    }


def _normalize_annotations(
    raw_annotations: object,
    *,
    device_scale_factor: int,
    quality: str,
) -> list[dict[str, object]]:
    if not isinstance(raw_annotations, Sequence) or isinstance(
        raw_annotations, (str, bytes, bytearray)
    ):
        raise RuntimeError("Benchmark annotation extraction returned invalid data.")

    annotations: list[dict[str, object]] = []
    for raw in raw_annotations:
        if not isinstance(raw, Mapping):
            raise RuntimeError("Benchmark annotation must be an object.")
        text_rect = raw["text_rect_css"]
        action_rect = raw["action_rect_css"]
        if not isinstance(text_rect, Mapping) or not isinstance(
            action_rect, Mapping
        ):
            raise RuntimeError("Benchmark annotation rectangles must be objects.")
        annotations.append(
            {
                "id": str(raw["id"]),
                "text": str(raw["text"]),
                "language": str(raw["language"]),
                "role": str(raw["role"]),
                "quality": quality,
                "include_detection": True,
                "include_cer": quality == "clear",
                "target": str(raw["target"]),
                "match_mode": (
                    str(raw["match_mode"])
                    if raw.get("match_mode")
                    else ("fuzzy" if quality == "disturbed" else "exact")
                ),
                "ambiguity_group": raw.get("ambiguity_group"),
                "action_point": str(raw["action_point"]),
                "text_rect_css": dict(text_rect),
                "text_rect_px": _scale_rect(
                    text_rect,
                    device_scale_factor=device_scale_factor,
                ),
                "action_rect_css": dict(action_rect),
                "action_rect_px": _scale_rect(
                    action_rect,
                    device_scale_factor=device_scale_factor,
                ),
            }
        )
    return annotations


def _coverage(fixtures: Sequence[Mapping[str, object]]) -> dict[str, object]:
    annotations = [
        annotation
        for fixture in fixtures
        for annotation in fixture["annotations"]  # type: ignore[index]
    ]
    return {
        "viewports_css": sorted(
            {
                tuple(fixture["viewport_css"])  # type: ignore[arg-type]
                for fixture in fixtures
            }
        ),
        "device_scale_factors": sorted(
            {fixture["device_scale_factor"] for fixture in fixtures}
        ),
        "language_profiles": sorted(
            {fixture["language_profile"] for fixture in fixtures}
        ),
        "languages": sorted(
            {annotation["language"] for annotation in annotations}
        ),
        "roles": sorted({annotation["role"] for annotation in annotations}),
        "fonts": sorted(
            {
                font
                for fixture in fixtures
                for font in fixture["fonts"]  # type: ignore[union-attr]
            }
        ),
        "font_sizes_px": sorted(
            {
                size
                for fixture in fixtures
                for size in fixture["font_sizes_px"]  # type: ignore[union-attr]
            }
        ),
        "effects": sorted(
            {
                effect
                for fixture in fixtures
                for effect in fixture["effects"]  # type: ignore[union-attr]
            }
        ),
        "annotation_count": len(annotations),
        "unique_target_count": sum(
            annotation["target"] == "unique" for annotation in annotations
        ),
        "ambiguous_group_count": len(
            {
                annotation["ambiguity_group"]
                for annotation in annotations
                if annotation["ambiguity_group"] is not None
            }
        ),
    }


def generate(chrome_executable: Path) -> None:
    if not chrome_executable.is_file():
        raise RuntimeError(f"Chrome executable is unavailable: {chrome_executable}")

    from playwright.sync_api import sync_playwright

    source_hash = _sha256(SOURCE_HTML)
    fixtures: list[dict[str, object]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=str(chrome_executable),
        )
        try:
            for scene in SCENES:
                viewport_width, viewport_height = scene["viewport"]
                for device_scale_factor in (1, 2):
                    context = browser.new_context(
                        viewport={
                            "width": viewport_width,
                            "height": viewport_height,
                        },
                        device_scale_factor=device_scale_factor,
                        locale="en-US",
                        timezone_id="UTC",
                        color_scheme="light",
                        reduced_motion="reduce",
                    )
                    try:
                        page = context.new_page()
                        page.goto(
                            f"{SOURCE_HTML.as_uri()}?scene={scene['id']}",
                            wait_until="load",
                        )
                        page.wait_for_function(
                            "() => document.documentElement.dataset.ready === 'true'"
                        )
                        page.evaluate("() => document.fonts.ready")
                        raw_annotations = page.evaluate(ANNOTATION_SCRIPT)
                        file_name = (
                            f"{scene['id']}_{viewport_width}x{viewport_height}"
                            f"_dpr{device_scale_factor}.png"
                        )
                        image_path = ROOT / file_name
                        image_bytes = page.screenshot(
                            type="png",
                            full_page=False,
                            scale="device",
                            animations="disabled",
                            caret="hide",
                        )
                        image_path.write_bytes(image_bytes)
                        image_width, image_height = _png_dimensions(image_bytes)
                        expected_size = (
                            viewport_width * device_scale_factor,
                            viewport_height * device_scale_factor,
                        )
                        if (image_width, image_height) != expected_size:
                            raise RuntimeError(
                                f"{file_name} size {(image_width, image_height)} "
                                f"does not match {expected_size}."
                            )
                        fixtures.append(
                            {
                                "id": (
                                    f"{scene['id']}-"
                                    f"{viewport_width}x{viewport_height}-"
                                    f"dpr{device_scale_factor}"
                                ),
                                "scene": scene["id"],
                                "file": file_name,
                                "viewport_css": [
                                    viewport_width,
                                    viewport_height,
                                ],
                                "device_scale_factor": device_scale_factor,
                                "screenshot_px": [
                                    image_width,
                                    image_height,
                                ],
                                "language_profile": scene["language_profile"],
                                "quality": scene["quality"],
                                "effects": list(scene["effects"]),
                                "fonts": list(scene["fonts"]),
                                "font_sizes_px": list(scene["font_sizes_px"]),
                                "sha256": hashlib.sha256(image_bytes).hexdigest(),
                                "annotations": _normalize_annotations(
                                    raw_annotations,
                                    device_scale_factor=device_scale_factor,
                                    quality=str(scene["quality"]),
                                ),
                            }
                        )
                    finally:
                        context.close()
        finally:
            renderer_version = browser.version
            browser.close()

    manifest = {
        "schema_version": 1,
        "corpus_id": "visionautotest-ocr-task10",
        "corpus_version": CORPUS_VERSION,
        "random_seed": RANDOM_SEED,
        "source": {
            "file": SOURCE_HTML.name,
            "sha256": source_hash,
        },
        "renderer": {
            "name": "Google Chrome",
            "version": renderer_version,
            "executable_name": chrome_executable.name,
            "screenshot_scale": "device",
            "locale": "en-US",
            "timezone": "UTC",
        },
        "thresholds": {
            "clear_detection_f1_min": 0.95,
            "clear_zh_en_cer_max": 0.05,
            "disturbed_target_success_min": 0.90,
            "unique_interaction_success_min": 0.95,
            "wrong_operation_rate_max_exclusive": 0.005,
            "ambiguity_rejection_rate_min": 1.0,
            "viewport_p95_ms_max": 2000.0,
            "three_viewport_page_p95_ms_max": 6000.0,
        },
        "coverage": _coverage(fixtures),
        "fixtures": fixtures,
    }
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = _parse_args()
    generate(args.chrome_executable.resolve())


if __name__ == "__main__":
    main()
