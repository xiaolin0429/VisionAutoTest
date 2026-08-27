from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from app.workers.ocr_engine import (
    PADDLE_LANGUAGE_BY_PROFILE,
    OcrEngineError,
    OcrEnginePool,
    OcrPreprocessor,
    OcrRecognitionPipeline,
)
from app.workers.ocr_types import OcrEngineLanguageProfile, OcrErrorCode
from app.workers.vision import DefaultVisionAssertionAdapter

pytestmark = [pytest.mark.vision, pytest.mark.ocr_fake]

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ocr"


class FakeEngine:
    def __init__(
        self,
        profile: OcrEngineLanguageProfile,
        *,
        include_low_confidence_block: bool = False,
        fail: bool = False,
        position_index: int = 0,
    ) -> None:
        self.profile = profile
        self.include_low_confidence_block = include_low_confidence_block
        self.fail = fail
        self.position_index = position_index
        self.closed = False
        self.calls = 0

    def ocr(self, image: Any, *, cls: bool) -> list[list[list[Any]]]:
        assert cls is False
        self.calls += 1
        if self.fail:
            raise RuntimeError("fake recognition failure")
        height, width = image.shape[:2]
        left_ratio = 0.05 + (self.position_index * 0.17)
        polygon = [
            [width * left_ratio, height * 0.20],
            [width * (left_ratio + 0.12), height * 0.20],
            [width * (left_ratio + 0.12), height * 0.28],
            [width * left_ratio, height * 0.28],
        ]
        texts = {
            "zh_en": "提交 Submit",
            "en": "Submit",
            "latin": "Confirmación",
            "japan": "送信",
            "korean": "제출",
        }
        lines: list[list[Any]] = [[polygon, (texts[self.profile], 0.94)]]
        if self.include_low_confidence_block:
            lines.append(
                [
                    [
                        [width * 0.70, height * 0.70],
                        [width * 0.80, height * 0.70],
                        [width * 0.80, height * 0.75],
                        [width * 0.70, height * 0.75],
                    ],
                    ("occluded guess", 0.30),
                ]
            )
        return [lines]

    def close(self) -> None:
        self.closed = True


def load_fixture(name: str) -> Any:
    image = cv2.imread(str(FIXTURE_ROOT / name), cv2.IMREAD_COLOR)
    assert image is not None
    return image


def make_factory(
    created: dict[OcrEngineLanguageProfile, list[FakeEngine]],
    *,
    include_low_confidence_block: bool = False,
    fail_profile: OcrEngineLanguageProfile | None = None,
) -> Any:
    profile_order = {
        "zh_en": 0,
        "en": 1,
        "latin": 2,
        "japan": 3,
        "korean": 4,
    }

    def factory(**kwargs: Any) -> FakeEngine:
        profile = kwargs["profile"]
        engine = FakeEngine(
            profile,
            include_low_confidence_block=include_low_confidence_block,
            fail=profile == fail_profile,
            position_index=profile_order[profile],
        )
        created.setdefault(profile, []).append(engine)
        return engine

    return factory


def test_fixed_fixture_corpus_is_versioned_and_covers_task2_matrix() -> None:
    manifest = json.loads(
        (FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["version"] == 1
    assert manifest["random_seed"] == 20260816
    fixtures = manifest["fixtures"]
    assert {tuple(item["size"]) for item in fixtures} == {
        (1280, 720),
        (1920, 1080),
        (1440, 900),
        (390, 844),
    }
    assert set().union(*(set(item["languages"]) for item in fixtures)) == {
        "zh_en",
        "en",
        "latin",
        "japan",
        "korean",
    }
    assert len(set().union(*(set(item["fonts"]) for item in fixtures))) >= 5
    effects = set().union(*(set(item["effects"]) for item in fixtures))
    assert {
        "small_text",
        "noise",
        "low_contrast",
        "tilt_8deg",
        "partial_occlusion",
    } <= effects

    for fixture in fixtures:
        fixture_path = FIXTURE_ROOT / fixture["file"]
        fixture_bytes = fixture_path.read_bytes()
        assert hashlib.sha256(fixture_bytes).hexdigest() == fixture["sha256"]
        image = cv2.imdecode(
            np.frombuffer(fixture_bytes, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        assert image is not None
        assert (image.shape[1], image.shape[0]) == tuple(fixture["size"])
        assert float(image.std()) > 5.0


def test_preprocessor_builds_controlled_variants_from_fixed_fixtures() -> None:
    small_text = load_fixture("multifont_small_text_1920x1080.png")
    noisy_tilted = load_fixture("noisy_tilted_1440x900.png")
    preprocessor = OcrPreprocessor(profile="robust", max_variants=8)

    small_names = {
        variant.name for variant in preprocessor.build_variants(small_text)
    }
    tilted_names = {
        variant.name for variant in preprocessor.build_variants(noisy_tilted)
    }

    assert "original" in small_names
    assert any(name.startswith("upscale_") for name in small_names)
    assert {"clahe", "denoise", "adaptive_threshold"} <= small_names
    assert any(name.startswith("deskew_") for name in tilted_names)
    scaled = next(
        variant
        for variant in preprocessor.build_variants(small_text)
        if variant.name.startswith("upscale_")
    )
    assert max(scaled.image.shape[:2]) <= 3200
    assert scaled.image.shape[0] * scaled.image.shape[1] <= 6_000_000

    limited = OcrPreprocessor(
        profile="robust",
        max_variants=3,
    ).build_variants(small_text)
    assert len(limited) == 3
    assert limited[0].name == "original"


def test_balanced_profile_includes_binary_candidate() -> None:
    image = load_fixture("clear_multilingual_1280x720.png")

    names = {
        variant.name
        for variant in OcrPreprocessor(
            profile="balanced",
            max_variants=8,
        ).build_variants(image)
    }

    assert {"original", "clahe", "denoise", "adaptive_threshold"} <= names


def test_scaled_variant_maps_coordinates_back_to_original_image() -> None:
    image = load_fixture("multifont_small_text_1920x1080.png")
    variants = OcrPreprocessor(
        profile="robust",
        max_variants=8,
    ).build_variants(image)
    scaled = next(
        variant for variant in variants if variant.name.startswith("upscale_")
    )
    scale = scaled.image.shape[1] / image.shape[1]

    mapped = scaled.map_polygon_to_original(
        [
            (100.0 * scale, 50.0 * scale),
            (200.0 * scale, 50.0 * scale),
            (200.0 * scale, 100.0 * scale),
        ]
    )

    assert mapped == pytest.approx(
        [(100.0, 50.0), (200.0, 50.0), (200.0, 100.0)]
    )


@pytest.mark.parametrize(
    ("profile", "paddle_language"),
    [
        ("zh_en", "ch"),
        ("en", "en"),
        ("latin", "latin"),
        ("japan", "japan"),
        ("korean", "korean"),
    ],
)
def test_language_profiles_map_to_explicit_paddle_models(
    profile: OcrEngineLanguageProfile,
    paddle_language: str,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, Any]] = []

    def factory(**kwargs: Any) -> FakeEngine:
        calls.append(kwargs)
        return FakeEngine(kwargs["profile"])

    pool = OcrEnginePool(
        allowed_language_profiles=(profile,),
        model_root=tmp_path,
        allow_model_download=True,
        cache_size=1,
        engine_factory=factory,
    )

    assert pool.get_engine(profile) is pool.get_engine(profile)
    assert len(calls) == 1
    assert calls[0]["paddle_language"] == paddle_language
    assert calls[0]["paddle_language"] == PADDLE_LANGUAGE_BY_PROFILE[profile]


def test_engine_pool_is_lazy_lru_bounded_and_can_prewarm(
    tmp_path: Path,
) -> None:
    created: dict[OcrEngineLanguageProfile, list[FakeEngine]] = {}
    pool = OcrEnginePool(
        allowed_language_profiles=("zh_en", "en", "japan"),
        model_root=tmp_path,
        allow_model_download=True,
        cache_size=2,
        engine_factory=make_factory(created),
    )

    assert pool.cached_profiles == ()
    zh_engine = pool.get_engine("zh_en")
    en_engine = pool.get_engine("en")
    assert pool.get_engine("zh_en") is zh_engine
    pool.get_engine("japan")

    assert pool.cached_profiles == ("zh_en", "japan")
    assert en_engine.closed is True
    assert pool.warmup(("zh_en",), strict=True) == {"zh_en": None}


def test_model_and_language_gates_do_not_fallback(
    tmp_path: Path,
) -> None:
    factory_calls: list[dict[str, Any]] = []
    pool = OcrEnginePool(
        allowed_language_profiles=("zh_en", "japan"),
        model_root=tmp_path,
        allow_model_download=False,
        cache_size=2,
        engine_factory=lambda **kwargs: factory_calls.append(kwargs),
    )

    with pytest.raises(OcrEngineError) as model_error:
        pool.get_engine("japan")
    assert model_error.value.code == OcrErrorCode.OCR_MODEL_UNAVAILABLE
    assert factory_calls == []
    assert pool.cached_profiles == ()

    with pytest.raises(OcrEngineError) as language_error:
        pool.resolve_profiles("korean")
    assert language_error.value.code == OcrErrorCode.OCR_LANGUAGE_UNSUPPORTED
    assert pool.cached_profiles == ()


def test_installed_model_directories_pass_download_gate(
    tmp_path: Path,
) -> None:
    for model_type in ("det", "rec"):
        model_dir = tmp_path / "japan" / model_type
        model_dir.mkdir(parents=True)
        (model_dir / "inference.pdmodel").write_bytes(b"fixed-model")
        (model_dir / "inference.pdiparams").write_bytes(b"fixed-parameters")
    calls: list[dict[str, Any]] = []

    def factory(**kwargs: Any) -> FakeEngine:
        calls.append(kwargs)
        return FakeEngine("japan")

    pool = OcrEnginePool(
        allowed_language_profiles=("japan",),
        model_root=tmp_path,
        allow_model_download=False,
        cache_size=1,
        engine_factory=factory,
    )

    pool.get_engine("japan")

    assert len(calls) == 1
    assert calls[0]["allow_download"] is False


def test_auto_uses_only_allowed_language_engines_and_records_profiles(
    tmp_path: Path,
) -> None:
    profiles: tuple[OcrEngineLanguageProfile, ...] = (
        "zh_en",
        "en",
        "latin",
        "japan",
        "korean",
    )
    created: dict[OcrEngineLanguageProfile, list[FakeEngine]] = {}
    pipeline = OcrRecognitionPipeline(
        engine_pool=OcrEnginePool(
            allowed_language_profiles=profiles,
            model_root=tmp_path,
            allow_model_download=True,
            cache_size=5,
            engine_factory=make_factory(created),
        ),
        preprocessing_profile="fast",
        max_preprocess_variants=1,
        minimum_confidence=0.50,
    )

    analysis = pipeline.analyze(
        image=load_fixture("clear_multilingual_1280x720.png"),
        language_profile="auto",
    )

    assert tuple(analysis["language_profiles"]) == profiles
    assert set(created) == set(profiles)
    assert {block["language"] for block in analysis["blocks"]} == set(profiles)


def test_balanced_pipeline_stops_after_high_confidence_original(
    tmp_path: Path,
) -> None:
    created: dict[OcrEngineLanguageProfile, list[FakeEngine]] = {}
    pipeline = OcrRecognitionPipeline(
        engine_pool=OcrEnginePool(
            allowed_language_profiles=("en",),
            model_root=tmp_path,
            allow_model_download=True,
            cache_size=1,
            engine_factory=make_factory(created),
        ),
        preprocessing_profile="balanced",
        max_preprocess_variants=5,
        minimum_confidence=0.50,
    )

    analysis = pipeline.analyze(
        image=load_fixture("clear_multilingual_1280x720.png"),
        language_profile="en",
    )

    assert analysis["preprocessing_variants"] == ["original"]
    assert analysis["preprocessing_early_stopped_profiles"] == ["en"]
    assert created["en"][0].calls == 1


def test_balanced_pipeline_keeps_fallbacks_for_low_confidence_original(
    tmp_path: Path,
) -> None:
    class LowConfidenceEngine(FakeEngine):
        def ocr(self, image: Any, *, cls: bool) -> list[list[list[Any]]]:
            result = super().ocr(image, cls=cls)
            result[0][0][1] = (result[0][0][1][0], 0.85)
            return result

    engine = LowConfidenceEngine("en")
    pipeline = OcrRecognitionPipeline(
        engine_pool=OcrEnginePool(
            allowed_language_profiles=("en",),
            model_root=tmp_path,
            allow_model_download=True,
            cache_size=1,
            engine_factory=lambda **_kwargs: engine,
        ),
        preprocessing_profile="balanced",
        max_preprocess_variants=5,
        minimum_confidence=0.50,
    )

    analysis = pipeline.analyze(
        image=load_fixture("clear_multilingual_1280x720.png"),
        language_profile="en",
    )

    assert len(analysis["preprocessing_variants"]) > 1
    assert analysis["preprocessing_early_stopped_profiles"] == []
    assert engine.calls == len(analysis["preprocessing_variants"])


def test_vision_adapter_passes_explicit_language_to_pipeline(
    tmp_path: Path,
) -> None:
    created: dict[OcrEngineLanguageProfile, list[FakeEngine]] = {}
    pipeline = OcrRecognitionPipeline(
        engine_pool=OcrEnginePool(
            allowed_language_profiles=("zh_en", "japan"),
            model_root=tmp_path,
            allow_model_download=True,
            cache_size=2,
            engine_factory=make_factory(created),
        ),
        preprocessing_profile="fast",
        max_preprocess_variants=1,
        minimum_confidence=0.50,
    )
    adapter = DefaultVisionAssertionAdapter(ocr_pipeline=pipeline)

    analysis = adapter.analyze_ocr(
        image_png_bytes=(
            FIXTURE_ROOT / "clear_multilingual_1280x720.png"
        ).read_bytes(),
        language_profile="japan",
    )

    assert analysis["language_profiles"] == ["japan"]
    assert set(created) == {"japan"}


def test_multivariant_results_are_remapped_fused_and_keep_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: dict[OcrEngineLanguageProfile, list[FakeEngine]] = {}
    pipeline = OcrRecognitionPipeline(
        engine_pool=OcrEnginePool(
            allowed_language_profiles=("en",),
            model_root=tmp_path,
            allow_model_download=True,
            cache_size=1,
            engine_factory=make_factory(
                created,
                include_low_confidence_block=True,
            ),
        ),
        preprocessing_profile="robust",
        max_preprocess_variants=8,
        minimum_confidence=0.75,
    )
    monkeypatch.setattr(
        pipeline.preprocessor,
        "_estimate_deskew_angle",
        lambda _cv2, _gray: None,
    )
    image = load_fixture("multifont_small_text_1920x1080.png")

    analysis = pipeline.analyze(image=image, language_profile="en")

    assert len(analysis["blocks"]) == 1
    block = analysis["blocks"][0]
    assert block["text"] == "Submit"
    assert block["confidence"] == pytest.approx(0.94)
    assert block["pixel_rect"]["x"] == pytest.approx(
        image.shape[1] * 0.22,
        abs=2,
    )
    assert len(block["sources"]) == len(analysis["preprocessing_variants"])
    assert {
        source["preprocessing_variant"] for source in block["sources"]
    } == set(analysis["preprocessing_variants"])
    assert "occluded guess" not in {
        item["text"] for item in analysis["blocks"]
    }


def test_engine_recognition_failures_have_analysis_error_code(
    tmp_path: Path,
) -> None:
    created: dict[OcrEngineLanguageProfile, list[FakeEngine]] = {}
    pipeline = OcrRecognitionPipeline(
        engine_pool=OcrEnginePool(
            allowed_language_profiles=("en",),
            model_root=tmp_path,
            allow_model_download=True,
            cache_size=1,
            engine_factory=make_factory(created, fail_profile="en"),
        ),
        preprocessing_profile="fast",
        max_preprocess_variants=1,
        minimum_confidence=0.50,
    )

    with pytest.raises(OcrEngineError) as error:
        pipeline.analyze(
            image=load_fixture("clear_multilingual_1280x720.png"),
            language_profile="en",
        )

    assert error.value.code == OcrErrorCode.OCR_ANALYSIS_FAILED
