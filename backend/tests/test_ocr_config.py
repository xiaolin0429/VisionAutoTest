from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE_SETTINGS: dict[str, object] = {
    "database_url": "postgresql+psycopg://user:password@localhost/test",
    "database_auto_migrate": False,
    "jwt_secret_key": "unit-test-jwt-secret",
    "data_encryption_key": "unit-test-encryption-key",
}


def build_settings(**overrides: object) -> Settings:
    values = BASE_SETTINGS | overrides
    return Settings(**values, _env_file=None)  # pyright: ignore[reportCallIssue]


def test_ocr_settings_defaults_are_bounded_and_downloads_are_disabled() -> None:
    settings = build_settings(app_env="production")

    assert settings.ocr_default_language_profile == "zh_en"
    assert settings.ocr_allowed_language_profiles == (
        "zh_en",
        "en",
        "latin",
        "japan",
        "korean",
    )
    assert settings.ocr_allow_model_download is False
    assert settings.ocr_preprocessing_profile == "balanced"
    assert settings.ocr_max_preprocess_variants == 5
    assert settings.ocr_max_page_tiles == 20
    assert settings.ocr_page_tile_overlap_ratio == pytest.approx(0.20)
    assert settings.ocr_default_min_confidence == pytest.approx(0.75)
    assert settings.ocr_default_min_score == pytest.approx(0.75)
    assert settings.ocr_default_ambiguity_margin == pytest.approx(0.10)
    assert settings.ocr_evidence_max_candidates == 5
    assert settings.ocr_evidence_max_text_length == 160


def test_all_vat_ocr_environment_variables_are_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        "VAT_OCR_DEFAULT_LANGUAGE_PROFILE": "en",
        "VAT_OCR_ALLOWED_LANGUAGE_PROFILES": '["en","latin"]',
        "VAT_OCR_MODEL_ROOT": "/tmp/vat-ocr-models",
        "VAT_OCR_ALLOW_MODEL_DOWNLOAD": "true",
        "VAT_OCR_ENGINE_CACHE_SIZE": "2",
        "VAT_OCR_PREPROCESSING_PROFILE": "fast",
        "VAT_OCR_MAX_PREPROCESS_VARIANTS": "3",
        "VAT_OCR_MAX_PAGE_TILES": "8",
        "VAT_OCR_PAGE_TILE_OVERLAP_RATIO": "0.25",
        "VAT_OCR_DEFAULT_MIN_CONFIDENCE": "0.65",
        "VAT_OCR_DEFAULT_MIN_SCORE": "0.70",
        "VAT_OCR_DEFAULT_AMBIGUITY_MARGIN": "0.12",
        "VAT_OCR_EVIDENCE_MAX_CANDIDATES": "7",
        "VAT_OCR_EVIDENCE_MAX_TEXT_LENGTH": "200",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    settings = build_settings()

    assert settings.ocr_default_language_profile == "en"
    assert settings.ocr_allowed_language_profiles == ("en", "latin")
    assert str(settings.ocr_model_root) == "/tmp/vat-ocr-models"
    assert settings.ocr_allow_model_download is True
    assert settings.ocr_engine_cache_size == 2
    assert settings.ocr_preprocessing_profile == "fast"
    assert settings.ocr_max_preprocess_variants == 3
    assert settings.ocr_max_page_tiles == 8
    assert settings.ocr_page_tile_overlap_ratio == pytest.approx(0.25)
    assert settings.ocr_default_min_confidence == pytest.approx(0.65)
    assert settings.ocr_default_min_score == pytest.approx(0.70)
    assert settings.ocr_default_ambiguity_margin == pytest.approx(0.12)
    assert settings.ocr_evidence_max_candidates == 7
    assert settings.ocr_evidence_max_text_length == 200


@pytest.mark.parametrize(
    "overrides",
    [
        {"ocr_default_language_profile": "unsupported"},
        {"ocr_allowed_language_profiles": ()},
        {"ocr_allowed_language_profiles": ("zh_en", "zh_en")},
        {
            "ocr_default_language_profile": "japan",
            "ocr_allowed_language_profiles": ("zh_en", "en"),
        },
        {"ocr_model_root": ""},
        {"ocr_allow_model_download": "sometimes"},
        {"ocr_engine_cache_size": 0},
        {"ocr_preprocessing_profile": "unknown"},
        {"ocr_max_preprocess_variants": 0},
        {"ocr_max_page_tiles": 0},
        {"ocr_page_tile_overlap_ratio": 0.0},
        {"ocr_page_tile_overlap_ratio": 1.0},
        {"ocr_default_min_confidence": -0.01},
        {"ocr_default_min_score": 1.01},
        {"ocr_default_ambiguity_margin": 1.01},
        {"ocr_evidence_max_candidates": 0},
        {"ocr_evidence_max_candidates": 21},
        {"ocr_evidence_max_text_length": 15},
        {"ocr_evidence_max_text_length": 513},
    ],
)
def test_invalid_ocr_settings_fail_at_startup(
    overrides: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        build_settings(**overrides)
