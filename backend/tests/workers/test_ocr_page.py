from __future__ import annotations

from collections.abc import Sequence

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from app.workers.ocr_page import (
    OcrAssociationError,
    OcrCoordinateMapper,
    OcrPageGeometryError,
    build_ocr_page_snapshot,
    build_ocr_page_snapshot_from_analysis,
    related_elements,
    resolve_associated_control_rect,
)
from app.workers.ocr_types import (
    OcrCoordinateSet,
    OcrErrorCode,
    OcrPoint,
    OcrRatioRect,
    OcrRect,
    OcrTextBlock,
)

pytestmark = [pytest.mark.vision, pytest.mark.ocr_fake]


def _encode_image(
    width: int,
    height: int,
    *,
    rectangles: Sequence[tuple[int, int, int, int]] = (),
) -> bytes:
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    for left, top, right, bottom in rectangles:
        cv2.rectangle(
            image,
            (left, top),
            (right, bottom),
            (35, 35, 35),
            thickness=2,
        )
    success, encoded = cv2.imencode(".png", image)
    assert success
    return encoded.tobytes()


def _raw_block(
    block_id: str,
    text: str,
    rect: tuple[float, float, float, float],
    *,
    image_width: int,
    image_height: int,
    confidence: float = 0.95,
) -> OcrTextBlock:
    x, y, width, height = rect
    pixel_rect = OcrRect(x=x, y=y, width=width, height=height)
    ratio_rect = OcrRatioRect(
        x=x / image_width,
        y=y / image_height,
        width=width / image_width,
        height=height / image_height,
    )
    coordinates = OcrCoordinateSet(
        pixel_rect=pixel_rect,
        ratio_rect=ratio_rect,
        viewport_css_rect=pixel_rect,
        document_css_rect=pixel_rect,
    )
    return OcrTextBlock(
        block_id=block_id,
        text=text,
        confidence=confidence,
        polygon=(
            OcrPoint(x=x, y=y),
            OcrPoint(x=x + width, y=y),
            OcrPoint(x=x + width, y=y + height),
            OcrPoint(x=x, y=y + height),
        ),
        coordinates=coordinates,
        language="zh_en",
        preprocessing_variant="original",
    )


def _assert_rect_close(actual: OcrRect, expected: OcrRect) -> None:
    assert actual.x == pytest.approx(expected.x)
    assert actual.y == pytest.approx(expected.y)
    assert actual.width == pytest.approx(expected.width)
    assert actual.height == pytest.approx(expected.height)


@pytest.mark.parametrize(
    ("viewport_width", "viewport_height", "device_scale_factor"),
    [(320, 180, 1.0), (390, 844, 2.0)],
)
def test_coordinate_mapper_round_trips_pixel_ratio_viewport_and_document(
    viewport_width: int,
    viewport_height: int,
    device_scale_factor: float,
) -> None:
    mapper = OcrCoordinateMapper(
        image_width_px=int(viewport_width * device_scale_factor),
        image_height_px=int(viewport_height * device_scale_factor),
        viewport_width_css=viewport_width,
        viewport_height_css=viewport_height,
        device_scale_factor=device_scale_factor,
        scroll_x_css=13,
        scroll_y_css=240,
    )
    pixel_rect = OcrRect(
        x=40 * device_scale_factor,
        y=30 * device_scale_factor,
        width=80 * device_scale_factor,
        height=24 * device_scale_factor,
    )

    coordinates = mapper.pixel_rect_to_coordinates(pixel_rect)

    assert coordinates.viewport_css_rect == OcrRect(
        x=40, y=30, width=80, height=24
    )
    assert coordinates.document_css_rect == OcrRect(
        x=53, y=270, width=80, height=24
    )
    _assert_rect_close(
        mapper.ratio_rect_to_pixel(coordinates.ratio_rect),
        pixel_rect,
    )
    _assert_rect_close(
        mapper.viewport_css_rect_to_pixel(coordinates.viewport_css_rect),
        pixel_rect,
    )
    _assert_rect_close(
        mapper.document_css_rect_to_pixel(coordinates.document_css_rect),
        pixel_rect,
    )


def test_coordinate_mapper_rejects_dpr_and_viewport_mismatch() -> None:
    with pytest.raises(OcrPageGeometryError, match="device scale factor"):
        OcrCoordinateMapper(
            image_width_px=600,
            image_height_px=400,
            viewport_width_css=300,
            viewport_height_css=200,
            device_scale_factor=1.0,
        )


def test_engine_analysis_dictionary_builds_typed_page_snapshot() -> None:
    viewport_width = 320
    viewport_height = 180
    image_width = viewport_width * 2
    image_height = viewport_height * 2
    analysis = {
        "image_width": image_width,
        "image_height": image_height,
        "language_profiles": ["en"],
        "preprocessing_variants": ["original", "clahe"],
        "elapsed_ms": 12.5,
        "blocks": [
            {
                "order_no": 1,
                "text": "Submit",
                "confidence": 0.96,
                "polygon_points": [
                    {"x": 80, "y": 60},
                    {"x": 200, "y": 60},
                    {"x": 200, "y": 100},
                    {"x": 80, "y": 100},
                ],
                "pixel_rect": {
                    "x": 80,
                    "y": 60,
                    "width": 120,
                    "height": 40,
                },
                "language": "en",
                "preprocessing_variant": "clahe",
            }
        ],
    }

    snapshot = build_ocr_page_snapshot_from_analysis(
        image_png_bytes=_encode_image(image_width, image_height),
        analysis=analysis,
        viewport_width_css=viewport_width,
        viewport_height_css=viewport_height,
        device_scale_factor=2.0,
        scroll_y_css=90,
    )

    assert snapshot.language_profiles == ("en",)
    assert snapshot.preprocessing_variants == ("original", "clahe")
    assert snapshot.elapsed_ms == 12.5
    assert snapshot.blocks[0].block_id == "block-1"
    assert snapshot.blocks[0].coordinates.viewport_css_rect == OcrRect(
        x=40, y=30, width=60, height=20
    )
    assert snapshot.blocks[0].coordinates.document_css_rect == OcrRect(
        x=40, y=120, width=60, height=20
    )


@pytest.mark.parametrize("device_scale_factor", [1.0, 2.0])
def test_snapshot_merges_blocks_and_keeps_css_coordinates_stable(
    device_scale_factor: float,
) -> None:
    viewport_width = 400
    viewport_height = 200
    image_width = int(viewport_width * device_scale_factor)
    image_height = int(viewport_height * device_scale_factor)

    def scaled(rect: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
        return tuple(value * device_scale_factor for value in rect)

    blocks = (
        _raw_block(
            "b1",
            "User",
            scaled((20, 30, 38, 18)),
            image_width=image_width,
            image_height=image_height,
        ),
        _raw_block(
            "b2",
            "Name",
            scaled((64, 31, 42, 18)),
            image_width=image_width,
            image_height=image_height,
        ),
        _raw_block(
            "b3",
            "Status",
            scaled((230, 30, 54, 18)),
            image_width=image_width,
            image_height=image_height,
        ),
        _raw_block(
            "b4",
            "Ready",
            scaled((20, 90, 48, 18)),
            image_width=image_width,
            image_height=image_height,
        ),
    )

    snapshot = build_ocr_page_snapshot(
        image_png_bytes=_encode_image(image_width, image_height),
        blocks=blocks,
        viewport_width_css=viewport_width,
        viewport_height_css=viewport_height,
        device_scale_factor=device_scale_factor,
        scroll_x_css=7,
        scroll_y_css=300,
        elapsed_ms=4.5,
    )

    assert [line.text for line in snapshot.lines] == ["User Name Status", "Ready"]
    assert [element.text for element in snapshot.elements] == [
        "User Name",
        "Status",
        "Ready",
    ]
    first = snapshot.elements[0]
    assert first.coordinates.viewport_css_rect == OcrRect(
        x=20, y=30, width=86, height=19
    )
    assert first.coordinates.document_css_rect == OcrRect(
        x=27, y=330, width=86, height=19
    )
    assert snapshot.screenshot_checksum_sha256


def test_snapshot_infers_roles_from_screenshot_geometry_only() -> None:
    width = 500
    height = 340
    screenshot = _encode_image(
        width,
        height,
        rectangles=(
            (20, 20, 130, 65),
            (160, 20, 450, 65),
            (20, 105, 230, 310),
        ),
    )
    blocks = (
        _raw_block(
            "button",
            "Submit",
            (48, 34, 55, 18),
            image_width=width,
            image_height=height,
        ),
        _raw_block(
            "input",
            "Email",
            (178, 34, 48, 18),
            image_width=width,
            image_height=height,
        ),
        _raw_block(
            "menu-1",
            "Profile",
            (42, 132, 58, 18),
            image_width=width,
            image_height=height,
        ),
        _raw_block(
            "menu-2",
            "Settings",
            (42, 190, 70, 18),
            image_width=width,
            image_height=height,
        ),
        _raw_block(
            "menu-3",
            "Logout",
            (42, 248, 55, 18),
            image_width=width,
            image_height=height,
        ),
        _raw_block(
            "text",
            "Welcome",
            (330, 145, 68, 18),
            image_width=width,
            image_height=height,
        ),
    )

    snapshot = build_ocr_page_snapshot(
        image_png_bytes=screenshot,
        blocks=blocks,
        viewport_width_css=width,
        viewport_height_css=height,
        device_scale_factor=1.0,
    )
    roles = {element.text: element.role for element in snapshot.elements}

    assert roles == {
        "Submit": "button",
        "Email": "input",
        "Profile": "menu_item",
        "Settings": "menu_item",
        "Logout": "menu_item",
        "Welcome": "text",
    }
    email = next(element for element in snapshot.elements if element.text == "Email")
    assert email.associated_control_rect is not None
    assert "enclosed_rect" in email.role_evidence


def test_label_associates_with_unique_input_and_builds_spatial_relations() -> None:
    width = 500
    height = 200
    screenshot = _encode_image(
        width,
        height,
        rectangles=((170, 55, 450, 105),),
    )
    blocks = (
        _raw_block(
            "label",
            "Email",
            (45, 70, 48, 18),
            image_width=width,
            image_height=height,
        ),
        _raw_block(
            "placeholder",
            "name@example.com",
            (190, 70, 140, 18),
            image_width=width,
            image_height=height,
        ),
        _raw_block(
            "below",
            "Help",
            (45, 145, 40, 18),
            image_width=width,
            image_height=height,
        ),
    )

    snapshot = build_ocr_page_snapshot(
        image_png_bytes=screenshot,
        blocks=blocks,
        viewport_width_css=width,
        viewport_height_css=height,
        device_scale_factor=1.0,
    )
    label = next(element for element in snapshot.elements if element.text == "Email")
    placeholder = next(
        element for element in snapshot.elements if element.text == "name@example.com"
    )
    help_text = next(element for element in snapshot.elements if element.text == "Help")

    assert label.role == "label"
    assert label.association_ambiguous is False
    assert resolve_associated_control_rect(label).width >= 275
    assert related_elements(
        snapshot,
        source_element_id=label.element_id,
        relation_type="associated_control",
    ) == (placeholder,)
    assert placeholder in related_elements(
        snapshot,
        source_element_id=label.element_id,
        relation_type="left_of",
    )
    assert label in related_elements(
        snapshot,
        source_element_id=placeholder.element_id,
        relation_type="right_of",
    )
    assert placeholder in related_elements(
        snapshot,
        source_element_id=label.element_id,
        relation_type="same_row",
    )
    assert help_text in related_elements(
        snapshot,
        source_element_id=label.element_id,
        relation_type="above",
    )
    assert label in related_elements(
        snapshot,
        source_element_id=help_text.element_id,
        relation_type="below",
    )
    assert help_text in related_elements(
        snapshot,
        source_element_id=label.element_id,
        relation_type="same_column",
    )
    assert help_text in related_elements(
        snapshot,
        source_element_id=label.element_id,
        relation_type="nearest",
    )


def test_label_can_associate_with_unique_empty_input_geometry() -> None:
    width = 400
    height = 180
    screenshot = _encode_image(
        width,
        height,
        rectangles=((145, 55, 365, 105),),
    )
    blocks = (
        _raw_block(
            "label",
            "Username",
            (35, 70, 72, 18),
            image_width=width,
            image_height=height,
        ),
    )

    snapshot = build_ocr_page_snapshot(
        image_png_bytes=screenshot,
        blocks=blocks,
        viewport_width_css=width,
        viewport_height_css=height,
        device_scale_factor=1.0,
    )
    label = snapshot.elements[0]

    assert label.role == "label"
    assert label.association_ambiguous is False
    assert resolve_associated_control_rect(label).x >= 140
    assert related_elements(
        snapshot,
        source_element_id=label.element_id,
        relation_type="associated_control",
    ) == ()


def test_equally_ranked_label_controls_are_reported_as_ambiguous() -> None:
    width = 400
    height = 220
    screenshot = _encode_image(
        width,
        height,
        rectangles=(
            (40, 80, 185, 130),
            (215, 80, 360, 130),
        ),
    )
    blocks = (
        _raw_block(
            "label",
            "Account",
            (166, 35, 68, 18),
            image_width=width,
            image_height=height,
        ),
    )

    snapshot = build_ocr_page_snapshot(
        image_png_bytes=screenshot,
        blocks=blocks,
        viewport_width_css=width,
        viewport_height_css=height,
        device_scale_factor=1.0,
    )
    label = snapshot.elements[0]

    assert label.role == "label"
    assert label.association_ambiguous is True
    assert label.associated_control_rect is None
    assert len(label.associated_control_candidates) == 2
    with pytest.raises(OcrAssociationError) as exc_info:
        resolve_associated_control_rect(label)
    assert exc_info.value.code == OcrErrorCode.OCR_TARGET_AMBIGUOUS


def test_nearest_relation_is_omitted_when_distance_is_tied() -> None:
    width = 300
    height = 160
    blocks = (
        _raw_block(
            "left",
            "Left",
            (40, 70, 35, 16),
            image_width=width,
            image_height=height,
        ),
        _raw_block(
            "center",
            "Center",
            (125, 70, 50, 16),
            image_width=width,
            image_height=height,
        ),
        _raw_block(
            "right",
            "Right",
            (225, 70, 35, 16),
            image_width=width,
            image_height=height,
        ),
    )
    snapshot = build_ocr_page_snapshot(
        image_png_bytes=_encode_image(width, height),
        blocks=blocks,
        viewport_width_css=width,
        viewport_height_css=height,
        device_scale_factor=1.0,
    )
    center = next(element for element in snapshot.elements if element.text == "Center")

    assert related_elements(
        snapshot,
        source_element_id=center.element_id,
        relation_type="nearest",
    ) == ()
