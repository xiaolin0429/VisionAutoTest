from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.http import ApiError
from app.core.security import generate_token
from app.models import (
    BaselineRevision,
    MediaObject,
    ReportArtifact,
    StepResult,
    Template,
    TemplateMaskRegion,
    User,
)
from app.services.helpers import count_total, require_workspace_access

settings = get_settings()


class _SystemUser:
    id: int | None = None


SYSTEM_USER = _SystemUser()


def list_media_objects(
    db: Session,
    *,
    user: User,
    workspace_id: int,
    page: int,
    page_size: int,
    usage: str | None,
    status: str | None,
):
    require_workspace_access(db, user, workspace_id)
    stmt = select(MediaObject).where(MediaObject.workspace_id == workspace_id)
    if usage:
        stmt = stmt.where(MediaObject.usage == usage)
    if status:
        stmt = stmt.where(MediaObject.status == status)
    total = count_total(db, stmt)
    items = db.scalars(stmt.order_by(MediaObject.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def create_media_object(db: Session, *, user: User, workspace_id: int, file: UploadFile, usage: str, remark: str | None) -> MediaObject:
    file_bytes = file.file.read()
    return create_media_object_from_bytes(
        db,
        user=user,
        workspace_id=workspace_id,
        file_bytes=file_bytes,
        file_name=file.filename or "upload.bin",
        mime_type=file.content_type or "application/octet-stream",
        usage=usage,
        remark=remark,
    )


def create_media_object_from_bytes(
    db: Session,
    *,
    user: User | None,
    workspace_id: int,
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
    usage: str,
    remark: str | None,
) -> MediaObject:
    actor = user or SYSTEM_USER
    if user is not None:
        require_workspace_access(db, user, workspace_id)
    checksum = hashlib.sha256(file_bytes).hexdigest()
    existing = db.scalar(
        select(MediaObject).where(
            MediaObject.workspace_id == workspace_id,
            MediaObject.checksum_sha256 == checksum,
            MediaObject.file_size == len(file_bytes),
        )
    )
    if existing is not None:
        return existing

    workspace_dir = settings.local_storage_path / str(workspace_id)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file_name or "upload.bin").name
    object_key = f"{workspace_id}/{generate_token('obj')}_{safe_name}"
    disk_path = settings.local_storage_path / object_key
    disk_path.parent.mkdir(parents=True, exist_ok=True)
    disk_path.write_bytes(file_bytes)

    media = MediaObject(
        workspace_id=workspace_id,
        storage_type="local",
        bucket_name=None,
        object_key=object_key,
        file_name=safe_name,
        mime_type=mime_type,
        file_size=len(file_bytes),
        checksum_sha256=checksum,
        status="active",
        usage=usage,
        remark=remark,
        created_by=actor.id,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media


def get_media_object(db: Session, media_object_id: int) -> MediaObject:
    media = db.get(MediaObject, media_object_id)
    if media is None:
        raise ApiError(code="MEDIA_OBJECT_NOT_FOUND", message="Media object not found.", status_code=404)
    return media


def update_media_object(db: Session, *, user: User, media: MediaObject, status: str | None, remark: str | None) -> MediaObject:
    require_workspace_access(db, user, media.workspace_id)
    if status is not None and status == "deleted":
        references = media_references(db, media)
        if references:
            raise ApiError(
                code="MEDIA_OBJECT_REFERENCE_CONFLICT",
                message="Media object is still referenced by business resources.",
                status_code=409,
            )
        media.status = status
    elif status is not None:
        media.status = status
    if remark is not None:
        media.remark = remark
    db.commit()
    db.refresh(media)
    return media


def media_references(db: Session, media: MediaObject) -> list[dict]:
    references: list[dict] = []
    baseline_count = db.scalar(
        select(func.count()).select_from(BaselineRevision).where(BaselineRevision.media_object_id == media.id)
    ) or 0
    if baseline_count:
        references.append({"resource": "baseline-revisions", "count": int(baseline_count)})
    step_result_count = db.scalar(
        select(func.count()).select_from(StepResult).where(
            (StepResult.expected_media_object_id == media.id)
            | (StepResult.actual_media_object_id == media.id)
            | (StepResult.diff_media_object_id == media.id)
        )
    ) or 0
    if step_result_count:
        references.append({"resource": "step-results", "count": int(step_result_count)})
    artifact_count = db.scalar(
        select(func.count()).select_from(ReportArtifact).where(ReportArtifact.media_object_id == media.id)
    ) or 0
    if artifact_count:
        references.append({"resource": "report-artifacts", "count": int(artifact_count)})
    return references


def list_templates(db: Session, *, user: User, workspace_id: int, page: int, page_size: int, template_type: str | None, status: str | None, keyword: str | None):
    require_workspace_access(db, user, workspace_id)
    stmt = select(Template).where(Template.workspace_id == workspace_id, Template.is_deleted.is_(False))
    if template_type:
        stmt = stmt.where(Template.template_type == template_type)
    if status:
        stmt = stmt.where(Template.status == status)
    if keyword:
        like_value = f"%{keyword}%"
        stmt = stmt.where((Template.template_code.ilike(like_value)) | (Template.template_name.ilike(like_value)))
    total = count_total(db, stmt)
    items = db.scalars(stmt.order_by(Template.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def create_template(
    db: Session,
    *,
    user: User,
    workspace_id: int,
    template_code: str,
    template_name: str,
    template_type: str,
    match_strategy: str,
    threshold_value: float,
    status: str,
    original_media_object_id: int,
) -> Template:
    require_workspace_access(db, user, workspace_id)
    existing = db.scalar(
        select(Template).where(
            Template.workspace_id == workspace_id,
            Template.template_code == template_code,
            Template.is_deleted.is_(False),
        )
    )
    if existing is not None:
        raise ApiError(code="TEMPLATE_CODE_EXISTS", message="Template code already exists.", status_code=409)
    media = get_media_object(db, original_media_object_id)
    if media.workspace_id != workspace_id:
        raise ApiError(code="MEDIA_OBJECT_NOT_FOUND", message="Media object not found in workspace.", status_code=404)
    template = Template(
        workspace_id=workspace_id,
        template_code=template_code,
        template_name=template_name,
        template_type=template_type,
        match_strategy=match_strategy,
        threshold_value=threshold_value,
        status=status,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(template)
    db.flush()
    baseline = BaselineRevision(
        template_id=template.id,
        revision_no=1,
        media_object_id=original_media_object_id,
        source_type="uploaded",
        is_current=True,
        created_by=user.id,
    )
    db.add(baseline)
    db.flush()
    template.current_baseline_revision_id = baseline.id
    db.commit()
    db.refresh(template)
    return template


def get_template(db: Session, template_id: int) -> Template:
    template = db.get(Template, template_id)
    if template is None or template.is_deleted:
        raise ApiError(code="TEMPLATE_NOT_FOUND", message="Template not found.", status_code=404)
    return template


def update_template(db: Session, *, user: User, template: Template, payload: dict) -> Template:
    require_workspace_access(db, user, template.workspace_id)
    for key, value in payload.items():
        if value is not None:
            setattr(template, key, value)
    template.updated_by = user.id
    db.commit()
    db.refresh(template)
    return template


def list_baseline_revisions(db: Session, *, user: User, template: Template):
    require_workspace_access(db, user, template.workspace_id)
    return db.scalars(
        select(BaselineRevision).where(BaselineRevision.template_id == template.id).order_by(BaselineRevision.revision_no.desc())
    ).all()


def create_baseline_revision(
    db: Session,
    *,
    user: User,
    template: Template,
    media_object_id: int,
    source_type: str,
    remark: str | None,
    is_current: bool,
) -> BaselineRevision:
    require_workspace_access(db, user, template.workspace_id)
    media = get_media_object(db, media_object_id)
    if media.workspace_id != template.workspace_id:
        raise ApiError(code="MEDIA_OBJECT_NOT_FOUND", message="Media object not found in workspace.", status_code=404)
    max_revision = db.scalar(
        select(func.max(BaselineRevision.revision_no)).where(BaselineRevision.template_id == template.id)
    ) or 0
    if is_current:
        current_list = db.scalars(select(BaselineRevision).where(BaselineRevision.template_id == template.id, BaselineRevision.is_current.is_(True))).all()
        for current in current_list:
            current.is_current = False
    baseline = BaselineRevision(
        template_id=template.id,
        revision_no=int(max_revision) + 1,
        media_object_id=media_object_id,
        source_type=source_type,
        is_current=is_current,
        remark=remark,
        created_by=user.id,
    )
    db.add(baseline)
    db.flush()
    if is_current:
        template.current_baseline_revision_id = baseline.id
    db.commit()
    db.refresh(baseline)
    return baseline


def list_mask_regions(db: Session, *, user: User, template: Template):
    require_workspace_access(db, user, template.workspace_id)
    return db.scalars(
        select(TemplateMaskRegion).where(TemplateMaskRegion.template_id == template.id).order_by(TemplateMaskRegion.sort_order.asc())
    ).all()


def _validate_ratios(x_ratio: float, y_ratio: float, width_ratio: float, height_ratio: float) -> None:
    if not (0 <= x_ratio < 1 and 0 <= y_ratio < 1 and 0 < width_ratio <= 1 and 0 < height_ratio <= 1):
        raise ApiError(code="MASK_REGION_OUT_OF_RANGE", message="Mask region ratios are out of range.", status_code=422)
    if x_ratio + width_ratio > 1 or y_ratio + height_ratio > 1:
        raise ApiError(code="MASK_REGION_OUT_OF_RANGE", message="Mask region exceeds template bounds.", status_code=422)


def create_mask_region(
    db: Session,
    *,
    user: User,
    template: Template,
    name: str,
    x_ratio: float,
    y_ratio: float,
    width_ratio: float,
    height_ratio: float,
    sort_order: int,
) -> TemplateMaskRegion:
    require_workspace_access(db, user, template.workspace_id)
    _validate_ratios(x_ratio, y_ratio, width_ratio, height_ratio)
    region = TemplateMaskRegion(
        template_id=template.id,
        region_name=name,
        x_ratio=x_ratio,
        y_ratio=y_ratio,
        width_ratio=width_ratio,
        height_ratio=height_ratio,
        sort_order=sort_order,
    )
    db.add(region)
    db.commit()
    db.refresh(region)
    return region


def get_mask_region(db: Session, mask_region_id: int) -> TemplateMaskRegion:
    region = db.get(TemplateMaskRegion, mask_region_id)
    if region is None:
        raise ApiError(code="MASK_REGION_NOT_FOUND", message="Mask region not found.", status_code=404)
    return region


def update_mask_region(db: Session, *, user: User, region: TemplateMaskRegion, payload: dict) -> TemplateMaskRegion:
    template = get_template(db, region.template_id)
    require_workspace_access(db, user, template.workspace_id)
    data = {
        "region_name": payload.get("name", region.region_name),
        "x_ratio": payload.get("x_ratio", float(region.x_ratio)),
        "y_ratio": payload.get("y_ratio", float(region.y_ratio)),
        "width_ratio": payload.get("width_ratio", float(region.width_ratio)),
        "height_ratio": payload.get("height_ratio", float(region.height_ratio)),
        "sort_order": payload.get("sort_order", region.sort_order),
    }
    _validate_ratios(data["x_ratio"], data["y_ratio"], data["width_ratio"], data["height_ratio"])
    region.region_name = data["region_name"]
    region.x_ratio = data["x_ratio"]
    region.y_ratio = data["y_ratio"]
    region.width_ratio = data["width_ratio"]
    region.height_ratio = data["height_ratio"]
    region.sort_order = data["sort_order"]
    db.commit()
    db.refresh(region)
    return region


def delete_mask_region(db: Session, *, user: User, region: TemplateMaskRegion) -> None:
    template = get_template(db, region.template_id)
    require_workspace_access(db, user, template.workspace_id)
    db.delete(region)
    db.commit()
