"""Regenerate the checked-in OCR image fixtures.

This script is not used by pytest. The generated PNG files and manifest are
checked in so test results do not depend on host fonts or random state.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUTPUT_ROOT = Path(__file__).resolve().parent
RANDOM_SEED = 20260816

FONT_PATHS = {
    "arial": Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    "arial_bold": Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    "arial_unicode": Path(
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
    ),
    "courier": Path("/System/Library/Fonts/Supplemental/Courier New.ttf"),
    "hiragino": Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
    "korean": Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    "times": Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf"),
}


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_PATHS[name]
    if not path.is_file():
        raise RuntimeError(f"Fixture font is unavailable: {path}")
    return ImageFont.truetype(path, size)


def save(image: Image.Image, name: str) -> None:
    image.save(OUTPUT_ROOT / name, format="PNG", optimize=True)


def clear_multilingual() -> None:
    image = Image.new("RGB", (1280, 720), "#f7f9fc")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((70, 70, 1210, 650), 24, fill="white", outline="#cad3e0")
    draw.text((120, 115), "VisionAutoTest OCR", font=font("arial_bold", 42), fill="#172033")
    draw.text((120, 205), "提交成功 / Submit succeeded", font=font("arial_unicode", 34), fill="#20304a")
    draw.text((120, 285), "日本語メニュー", font=font("hiragino", 34), fill="#20304a")
    draw.text((120, 365), "한국어 메뉴", font=font("korean", 36), fill="#20304a")
    draw.rounded_rectangle((120, 480, 360, 560), 14, fill="#1769e0")
    draw.text((180, 498), "Submit", font=font("arial_bold", 30), fill="white")
    save(image, "clear_multilingual_1280x720.png")


def multifont_small_text() -> None:
    image = Image.new("RGB", (1920, 1080), "#ffffff")
    draw = ImageDraw.Draw(image)
    draw.text((80, 70), "Small text and multiple fonts", font=font("arial_bold", 38), fill="#111827")
    rows = [
        ("Arial 12px: account status ready", "arial", 12),
        ("Courier 14px: request id VAT-2048", "courier", 14),
        ("Times 16px: visual automation report", "times", 16),
        ("Arial Bold 18px: Confirm operation", "arial_bold", 18),
        ("Unicode 20px: 用户名 Username", "arial_unicode", 20),
    ]
    for index, (text, family, size) in enumerate(rows):
        y = 180 + index * 120
        draw.rectangle((70, y - 20, 1840, y + 70), fill="#f8fafc", outline="#d7dee8")
        draw.text((110, y), text, font=font(family, size), fill="#263247")
    save(image, "multifont_small_text_1920x1080.png")


def noisy_tilted() -> None:
    rng = np.random.default_rng(RANDOM_SEED)
    height, width = 900, 1440
    base = np.full((height, width, 3), (172, 180, 188), dtype=np.int16)
    low_resolution_noise = rng.normal(128, 20, size=(90, 144)).astype(
        np.uint8
    )
    noise_image = Image.fromarray(low_resolution_noise, mode="L").resize(
        (width, height),
        resample=Image.Resampling.BILINEAR,
    )
    noise = np.asarray(noise_image, dtype=np.int16) - 128
    texture = (np.indices((height, width)).sum(axis=0) % 23 < 2).astype(
        np.int16
    )
    base += noise[:, :, None]
    base[:, :, 1] += texture * 8
    base = np.clip(base, 0, 255).astype(np.uint8)
    image = Image.fromarray(base, mode="RGB")

    text_layer = Image.new("RGBA", (1000, 220), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)
    draw.rounded_rectangle((20, 20, 980, 200), 22, fill=(198, 203, 209, 235))
    draw.text(
        (80, 72),
        "Low contrast 倾斜文本 OCR",
        font=font("arial_unicode", 42),
        fill=(90, 98, 108, 255),
    )
    rotated = text_layer.rotate(
        8,
        resample=Image.Resampling.BICUBIC,
        expand=True,
    )
    image.paste(rotated, (210, 300), rotated)
    save(image, "noisy_tilted_1440x900.png")


def occluded_mobile() -> None:
    image = Image.new("RGB", (390, 844), "#111827")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 80, 370, 760), 22, fill="#1f2937", outline="#4b5563")
    draw.text((45, 125), "Mobile OCR", font=font("arial_bold", 28), fill="#f9fafb")
    draw.text((45, 220), "用户名", font=font("arial_unicode", 24), fill="#d1d5db")
    draw.rounded_rectangle((45, 265, 345, 330), 12, fill="#374151", outline="#6b7280")
    draw.text((65, 281), "输入账号", font=font("arial_unicode", 22), fill="#9ca3af")
    draw.rounded_rectangle((45, 410, 345, 480), 12, fill="#2563eb")
    draw.text((145, 428), "继续", font=font("arial_unicode", 25), fill="white")
    draw.rectangle((190, 420, 275, 458), fill="#27364f")
    draw.text((45, 590), "Partially visible text", font=font("arial", 20), fill="#d1d5db")
    draw.rectangle((205, 585, 295, 620), fill="#1f2937")
    save(image, "occluded_mobile_390x844.png")


def write_manifest() -> None:
    fixtures = [
        {
            "file": "clear_multilingual_1280x720.png",
            "size": [1280, 720],
            "languages": ["zh_en", "en", "japan", "korean"],
            "fonts": ["Arial", "Arial Unicode", "Hiragino Sans GB", "Apple SD Gothic Neo"],
            "effects": ["clear"],
        },
        {
            "file": "multifont_small_text_1920x1080.png",
            "size": [1920, 1080],
            "languages": ["zh_en", "en", "latin"],
            "fonts": ["Arial", "Courier New", "Times New Roman", "Arial Bold", "Arial Unicode"],
            "effects": ["small_text", "multiple_font_sizes"],
        },
        {
            "file": "noisy_tilted_1440x900.png",
            "size": [1440, 900],
            "languages": ["zh_en", "en"],
            "fonts": ["Arial Unicode"],
            "effects": ["noise", "texture", "low_contrast", "tilt_8deg"],
        },
        {
            "file": "occluded_mobile_390x844.png",
            "size": [390, 844],
            "languages": ["zh_en", "en"],
            "fonts": ["Arial", "Arial Unicode"],
            "effects": ["dark_theme", "partial_occlusion"],
        },
    ]
    for fixture in fixtures:
        fixture_path = OUTPUT_ROOT / str(fixture["file"])
        fixture["sha256"] = hashlib.sha256(fixture_path.read_bytes()).hexdigest()

    manifest = {
        "version": 1,
        "random_seed": RANDOM_SEED,
        "fixtures": fixtures,
    }
    (OUTPUT_ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    clear_multilingual()
    multifont_small_text()
    noisy_tilted()
    occluded_mobile()
    write_manifest()


if __name__ == "__main__":
    main()
