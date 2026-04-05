from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel

TemplateStatus = Literal["draft", "published", "archived"]
TemplateMatchStrategy = Literal["template", "ocr"]


class MediaObjectRead(ORMModel):
    id: int
    workspace_id: int
    storage_type: str
    bucket_name: str | None = None
    object_key: str
    file_name: str
    mime_type: str
    file_size: int
    checksum_sha256: str
    status: str
    usage: str
    remark: str | None = None
    created_at: datetime


class MediaObjectUpdate(BaseModel):
    status: str | None = None
    remark: str | None = None


class TemplateRead(ORMModel):
    id: int
    workspace_id: int
    template_code: str
    template_name: str
    template_type: str
    match_strategy: TemplateMatchStrategy
    threshold_value: float
    status: TemplateStatus
    current_baseline_revision_id: int | None = None
    created_at: datetime
    updated_at: datetime


class TemplateCreate(BaseModel):
    template_code: str
    template_name: str
    template_type: str
    match_strategy: str = "template"
    threshold_value: float = 0.95
    status: str = "draft"
    original_media_object_id: int


class TemplateUpdate(BaseModel):
    template_name: str | None = None
    template_type: str | None = None
    match_strategy: str | None = None
    threshold_value: float | None = None
    status: str | None = None


class BaselineRevisionRead(ORMModel):
    id: int
    template_id: int
    revision_no: int
    media_object_id: int
    source_type: str
    source_report_id: int | None = None
    source_case_run_id: int | None = None
    source_step_result_id: int | None = None
    is_current: bool
    remark: str | None = None
    created_at: datetime


class BaselineRevisionCreate(BaseModel):
    media_object_id: int
    source_type: str = "manual"
    source_report_id: int | None = None
    source_case_run_id: int | None = None
    source_step_result_id: int | None = None
    remark: str | None = None
    is_current: bool = True


class OCRPointRead(BaseModel):
    x: int
    y: int


class OCRPixelRectRead(BaseModel):
    x: int
    y: int
    width: int
    height: int


class OCRRatioRectRead(BaseModel):
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float


class TemplateOCRBlockRead(BaseModel):
    order_no: int
    text: str
    confidence: float
    polygon_points: list[OCRPointRead]
    pixel_rect: OCRPixelRectRead
    ratio_rect: OCRRatioRectRead


class TemplateOCRResultRead(BaseModel):
    id: int | None = None
    template_id: int
    baseline_revision_id: int
    source_media_object_id: int
    status: str
    engine_name: str
    image_width: int | None = None
    image_height: int | None = None
    blocks: list[TemplateOCRBlockRead] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MaskRegionRead(ORMModel):
    id: int
    template_id: int
    region_name: str
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float
    sort_order: int
    created_at: datetime
    updated_at: datetime


class MaskRegionCreate(BaseModel):
    region_name: str
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float
    sort_order: int = 1


class MaskRegionUpdate(BaseModel):
    region_name: str | None = None
    x_ratio: float | None = None
    y_ratio: float | None = None
    width_ratio: float | None = None
    height_ratio: float | None = None
    sort_order: int | None = None


class MaskRegionPreviewWrite(BaseModel):
    name: str | None = None
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float
    sort_order: int | None = None


class MaskRegionPreviewRead(BaseModel):
    name: str
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float
    sort_order: int


class TemplatePreviewCreate(BaseModel):
    mask_regions: list[MaskRegionPreviewWrite] | None = None


class TemplatePreviewRead(BaseModel):
    template_id: int
    baseline_revision_id: int
    source_media_object_id: int
    image_width: int
    image_height: int
    overlay_media_object_id: int
    overlay_content_url: str
    processed_media_object_id: int
    processed_content_url: str
    mask_regions: list[MaskRegionPreviewRead]
