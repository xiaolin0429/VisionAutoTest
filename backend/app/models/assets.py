from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    AuditMixin,
    Base,
    CreatedAtMixin,
    PK_TYPE,
    TimestampMixin,
    utc_now,
)


class MediaObject(Base):
    __tablename__ = "asset_media_objects"
    __table_args__ = (
        UniqueConstraint(
            "checksum_sha256",
            "file_size",
            "workspace_id",
            name="uk_asset_media_objects_checksum",
        ),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("core_workspaces.id"), nullable=False
    )
    storage_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="local"
    )
    bucket_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    object_key: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    usage: Mapped[str] = mapped_column(String(32), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    created_by: Mapped[int | None] = mapped_column(PK_TYPE, nullable=True)


class Template(Base, AuditMixin):
    __tablename__ = "asset_templates"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "template_code", "is_deleted", name="uk_asset_templates"
        ),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("core_workspaces.id"), nullable=False
    )
    template_code: Mapped[str] = mapped_column(String(64), nullable=False)
    template_name: Mapped[str] = mapped_column(String(128), nullable=False)
    template_type: Mapped[str] = mapped_column(String(32), nullable=False)
    match_strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    current_baseline_revision_id: Mapped[int | None] = mapped_column(
        PK_TYPE, nullable=True
    )


class TemplateMaskRegion(Base, TimestampMixin):
    __tablename__ = "asset_template_mask_regions"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("asset_templates.id"), nullable=False
    )
    region_name: Mapped[str] = mapped_column(String(128), nullable=False)
    x_ratio: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    y_ratio: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    width_ratio: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    height_ratio: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class BaselineRevision(Base, CreatedAtMixin):
    __tablename__ = "asset_baseline_revisions"
    __table_args__ = (
        UniqueConstraint(
            "template_id", "revision_no", name="uk_asset_baseline_revisions"
        ),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("asset_templates.id"), nullable=False
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    media_object_id: Mapped[int] = mapped_column(
        ForeignKey("asset_media_objects.id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("report_run_reports.id"), nullable=True
    )
    source_case_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("exec_test_case_runs.id"), nullable=True
    )
    source_step_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("exec_step_results.id"), nullable=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[int | None] = mapped_column(PK_TYPE, nullable=True)


class TemplateOCRResult(Base, TimestampMixin):
    __tablename__ = "asset_template_ocr_results"
    __table_args__ = (
        UniqueConstraint(
            "template_id", "baseline_revision_id", name="uk_asset_template_ocr_results"
        ),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("asset_templates.id"), nullable=False
    )
    baseline_revision_id: Mapped[int] = mapped_column(
        ForeignKey("asset_baseline_revisions.id"), nullable=False
    )
    source_media_object_id: Mapped[int] = mapped_column(
        ForeignKey("asset_media_objects.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_name: Mapped[str] = mapped_column(String(64), nullable=False)
    image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
