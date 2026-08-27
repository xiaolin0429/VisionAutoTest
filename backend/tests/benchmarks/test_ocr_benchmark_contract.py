from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pytest

from tests.benchmarks.ocr_metrics import (
    CharacterErrorCounts,
    Detection,
    DetectionCounts,
    Rect,
    character_error_counts,
    detection_counts,
    percentile,
)
from tests.benchmarks.ocr_runner import build_result

pytestmark = [pytest.mark.ocr_benchmark, pytest.mark.ocr_fake]

CORPUS_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "ocr_benchmark" / "v1"
)
MANIFEST_PATH = CORPUS_ROOT / "manifest.json"
REFERENCE_RESULT_PATH = (
    Path(__file__).resolve().parent
    / "results"
    / "task10-reference.json"
)


def _load_manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_versioned_manifest_covers_the_approved_task10_matrix() -> None:
    manifest = _load_manifest()

    assert manifest["schema_version"] == 1
    assert manifest["corpus_version"] == "1.0.0"
    assert manifest["random_seed"] == 20260816
    coverage = manifest["coverage"]
    assert isinstance(coverage, dict)
    assert {tuple(item) for item in coverage["viewports_css"]} == {
        (1280, 720),
        (1440, 900),
        (1920, 1080),
        (390, 844),
    }
    assert coverage["device_scale_factors"] == [1, 2]
    assert set(coverage["languages"]) == {"zh", "en", "zh_en", "ja", "ko"}
    assert {"button", "placeholder", "label_input", "menu", "text"} <= set(
        coverage["roles"]
    )
    assert len(coverage["fonts"]) >= 5
    assert len(coverage["font_sizes_px"]) >= 3
    assert {
        "light_theme",
        "dark_theme",
        "low_contrast",
        "texture",
        "blur_0.45px",
        "tilt_plus_10deg",
        "tilt_minus_10deg",
        "partial_occlusion",
    } <= set(coverage["effects"])

    fixtures = manifest["fixtures"]
    assert isinstance(fixtures, list)
    assert {
        (tuple(item["viewport_css"]), item["device_scale_factor"])
        for item in fixtures
    } == {
        ((width, height), dpr)
        for width, height in (
            (1280, 720),
            (1440, 900),
            (1920, 1080),
            (390, 844),
        )
        for dpr in (1, 2)
    }


def test_manifest_hashes_dimensions_and_annotations_are_frozen() -> None:
    manifest = _load_manifest()
    source = manifest["source"]
    assert isinstance(source, dict)
    source_path = CORPUS_ROOT / source["file"]
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == source["sha256"]

    fixtures = manifest["fixtures"]
    assert isinstance(fixtures, list)
    for fixture in fixtures:
        image_bytes = (CORPUS_ROOT / fixture["file"]).read_bytes()
        assert hashlib.sha256(image_bytes).hexdigest() == fixture["sha256"]
        assert image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        assert list(struct.unpack(">II", image_bytes[16:24])) == fixture[
            "screenshot_px"
        ]

        annotations = fixture["annotations"]
        assert annotations
        assert len({item["id"] for item in annotations}) == len(annotations)
        image_width, image_height = fixture["screenshot_px"]
        for annotation in annotations:
            rect = annotation["text_rect_px"]
            assert rect["width"] > 0
            assert rect["height"] > 0
            assert 0 <= rect["x"] < image_width
            assert 0 <= rect["y"] < image_height
            assert rect["x"] + rect["width"] <= image_width + 1
            assert rect["y"] + rect["height"] <= image_height + 1
            assert annotation["target"] in {"unique", "ambiguous"}


def test_detection_f1_and_cer_are_computed_from_real_counts() -> None:
    expected = (
        Detection("Submit", Rect(10, 10, 100, 30)),
        Detection("Ready", Rect(10, 60, 80, 30)),
    )
    predicted = (
        Detection("Submit", Rect(12, 11, 96, 28)),
        Detection("Reedy", Rect(12, 61, 76, 28)),
        Detection("Noise", Rect(300, 300, 50, 20)),
    )

    detection = detection_counts(expected, predicted)
    character = character_error_counts(expected, predicted)

    assert detection == DetectionCounts(
        true_positive=2,
        false_positive=1,
        false_negative=0,
    )
    assert detection.precision == pytest.approx(2 / 3)
    assert detection.recall == 1.0
    assert detection.f1 == pytest.approx(0.8)
    assert character == CharacterErrorCounts(
        edit_distance=1,
        character_count=11,
    )
    assert character.cer == pytest.approx(1 / 11)


def test_p95_uses_nearest_rank_without_synthetic_samples() -> None:
    samples = [float(value) for value in range(1, 21)]

    assert percentile(samples, 0.95) == 19.0
    with pytest.raises(ValueError):
        percentile([], 0.95)


def test_checked_in_reference_result_is_real_and_traceable() -> None:
    manifest = _load_manifest()
    result = json.loads(REFERENCE_RESULT_PATH.read_text(encoding="utf-8"))

    assert result["result_kind"] == "real_paddleocr"
    assert result["corpus"]["version"] == manifest["corpus_version"]
    assert result["corpus"]["manifest_sha256"] == hashlib.sha256(
        MANIFEST_PATH.read_bytes()
    ).hexdigest()
    assert result["runtime"]["warmup"] == {
        "en": None,
        "japan": None,
        "korean": None,
        "zh_en": None,
    }
    assert len(result["environment"]["models"]) >= 8
    assert result["web_e2e"]["case_count"] == 4
    assert result["web_e2e"]["step_attempts"] == 28
    assert result["thresholds"]["passed"] is True
    assert result["command"][0] == "python"
    assert "hardware_profile" in result["environment"]
    assert "model_root" not in result["environment"]
    assert "git_dirty" not in result["environment"]
    serialized = json.dumps(result, ensure_ascii=False)
    assert str(Path.home()) not in serialized
    assert "/Users/" not in serialized


def test_generated_benchmark_metadata_never_exposes_absolute_home_paths(
    tmp_path: Path,
) -> None:
    manifest = _load_manifest()
    result = build_result(
        manifest=manifest,
        model_root=tmp_path / "private-model-root",
        preprocessing_profile="balanced",
        max_preprocess_variants=5,
        minimum_confidence=0.4,
        warmup={"en": None},
        accuracy={},
        performance={"chrome_version": "test-chrome"},
        web_e2e={},
        thresholds={"passed": True},
        command=(
            str(Path.home() / "private-venv" / "bin" / "python"),
            str(Path.home() / "private-repo" / "run_ocr_benchmark.py"),
            "--model-root",
            str(Path.home() / "private-model-root"),
        ),
    )

    serialized = json.dumps(result, ensure_ascii=False)
    assert str(Path.home()) not in serialized
    assert str(tmp_path) not in serialized
    assert result["command"] == [
        "python",
        "run_ocr_benchmark.py",
        "--model-root",
        "private-model-root",
    ]
