from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.http import ApiError
from app.core.storage import get_storage_backend
from app.core.security import generate_token
from app.models import (
    BaselineRevision,
    MediaObject,
    ReportArtifact,
    RunReport,
    StepResult,
    Template,
    TemplateMaskRegion,
    TemplateOCRResult,
    TestCaseRun,
    User,
)
from app.services.helpers import count_total, require_workspace_access
from app.workers.vision import MaskRegionRatio, build_vision_assertion_adapter

settings = get_settings()
storage_backend = get_storage_backend()
SUPPORTED_TEMPLATE_MATCH_STRATEGIES = {"template", "ocr"}
SUPPORTED_TEMPLATE_STATUSES = {"draft", "published", "archived"}
SUPPORTED_BASELINE_SOURCE_TYPES = {"manual", "uploaded", "adopted_from_failure"}
OCR_RESULT_SUCCESS_STATUS = "succeeded"
OCR_RESULT_FAILED_STATUS = "failed"
OCR_RESULT_NOT_GENERATED_STATUS = "not_generated"
OCR_ENGINE_NAME = "paddleocr"


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
    """List media objects inside one workspace with optional usage/status filters.

    Args:
        db: Active database session.
        user: User requesting access to workspace media.
        workspace_id: Workspace that owns the media objects.
        page: 1-based page number.
        page_size: Maximum items returned for the page.
        usage: Optional media usage filter such as template or artifact.
        status: Optional media status filter.

    Returns:
        A tuple of ``(items, total)`` for paginated media listing.
    """
    require_workspace_access(db, user, workspace_id)
    stmt = select(MediaObject).where(MediaObject.workspace_id == workspace_id)
    if usage:
        stmt = stmt.where(MediaObject.usage == usage)
    if status:
        stmt = stmt.where(MediaObject.status == status)
    total = count_total(db, stmt)
    items = db.scalars(
        stmt.order_by(MediaObject.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return items, total


def create_media_object(
    db: Session,
    *,
    user: User,
    workspace_id: int,
    file: UploadFile,
    usage: str,
    remark: str | None,
) -> MediaObject:
    """Create a media object from an uploaded file.

    Args:
        db: Active database session.
        user: User uploading the file.
        workspace_id: Workspace that will own the media object.
        file: Uploaded file wrapper from the API layer.
        usage: Business usage tag written to the media record.
        remark: Optional operator-facing remark.

    Returns:
        The persisted media object, reusing an existing deduplicated record when possible.
    """
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
    """Create or reuse a media object from raw bytes.

    Args:
        db: Active database session.
        user: Optional user performing the write; ``None`` is used for system-created artifacts.
        workspace_id: Workspace that will own the media object.
        file_bytes: Raw file content.
        file_name: Original or generated file name.
        mime_type: Stored MIME type.
        usage: Business usage tag written to the media record.
        remark: Optional operator-facing remark.

    Returns:
        The existing deduplicated media object or the newly persisted one.
    """
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

    safe_name = Path(file_name or "upload.bin").name
    stored_object = storage_backend.store_bytes(
        namespace=str(workspace_id),
        file_name=safe_name,
        content_bytes=file_bytes,
    )

    media = MediaObject(
        workspace_id=workspace_id,
        storage_type="local",
        bucket_name=None,
        object_key=stored_object.object_key,
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
        raise ApiError(
            code="MEDIA_OBJECT_NOT_FOUND",
            message="Media object not found.",
            status_code=404,
        )
    return media


def update_media_object(
    db: Session,
    *,
    user: User,
    media: MediaObject,
    status: str | None,
    remark: str | None,
) -> MediaObject:
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
    """Collect business references that still point at a media object.

    Args:
        db: Active database session.
        media: Media object being checked for delete safety.

    Returns:
        A list of reference summaries grouped by resource type.
    """
    references: list[dict] = []
    baseline_count = (
        db.scalar(
            select(func.count())
            .select_from(BaselineRevision)
            .where(BaselineRevision.media_object_id == media.id)
        )
        or 0
    )
    if baseline_count:
        references.append(
            {"resource": "baseline-revisions", "count": int(baseline_count)}
        )
    step_result_count = (
        db.scalar(
            select(func.count())
            .select_from(StepResult)
            .where(
                (StepResult.expected_media_object_id == media.id)
                | (StepResult.actual_media_object_id == media.id)
                | (StepResult.diff_media_object_id == media.id)
            )
        )
        or 0
    )
    if step_result_count:
        references.append({"resource": "step-results", "count": int(step_result_count)})
    artifact_count = (
        db.scalar(
            select(func.count())
            .select_from(ReportArtifact)
            .where(ReportArtifact.media_object_id == media.id)
        )
        or 0
    )
    if artifact_count:
        references.append(
            {"resource": "report-artifacts", "count": int(artifact_count)}
        )
    return references


def list_templates(
    db: Session,
    *,
    user: User,
    workspace_id: int,
    page: int,
    page_size: int,
    template_type: str | None,
    status: str | None,
    keyword: str | None,
):
    require_workspace_access(db, user, workspace_id)
    stmt = select(Template).where(
        Template.workspace_id == workspace_id, Template.is_deleted.is_(False)
    )
    if template_type:
        stmt = stmt.where(Template.template_type == template_type)
    if status:
        stmt = stmt.where(Template.status == status)
    if keyword:
        like_value = f"%{keyword}%"
        stmt = stmt.where(
            (Template.template_code.ilike(like_value))
            | (Template.template_name.ilike(like_value))
        )
    total = count_total(db, stmt)
    items = db.scalars(
        stmt.order_by(Template.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
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
    """Create a template and seed its first baseline revision from the uploaded original media.

    Args:
        db: Active database session.
        user: User creating the template.
        workspace_id: Workspace that will own the template.
        template_code: Unique template code inside the workspace.
        template_name: Human-readable template name.
        template_type: Template category such as web or mobile screen.
        match_strategy: Visual strategy used by the template.
        threshold_value: Matching threshold persisted on the template.
        status: Initial template status.
        original_media_object_id: Media object used to create the first baseline.

    Returns:
        The newly created template with ``current_baseline_revision_id`` initialized.

    Raises:
        ApiError: If the template code already exists or the media object is outside the workspace.
    """
    require_workspace_access(db, user, workspace_id)
    _validate_template_contract(match_strategy=match_strategy, status=status)
    existing = db.scalar(
        select(Template).where(
            Template.workspace_id == workspace_id,
            Template.template_code == template_code,
            Template.is_deleted.is_(False),
        )
    )
    if existing is not None:
        raise ApiError(
            code="TEMPLATE_CODE_EXISTS",
            message="Template code already exists.",
            status_code=409,
        )
    media = get_media_object(db, original_media_object_id)
    if media.workspace_id != workspace_id:
        raise ApiError(
            code="MEDIA_OBJECT_NOT_FOUND",
            message="Media object not found in workspace.",
            status_code=404,
        )
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
        raise ApiError(
            code="TEMPLATE_NOT_FOUND", message="Template not found.", status_code=404
        )
    return template


def update_template(
    db: Session, *, user: User, template: Template, payload: dict
) -> Template:
    require_workspace_access(db, user, template.workspace_id)
    next_match_strategy = payload.get("match_strategy", template.match_strategy)
    next_status = payload.get("status", template.status)
    _validate_template_contract(match_strategy=next_match_strategy, status=next_status)
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
        select(BaselineRevision)
        .where(BaselineRevision.template_id == template.id)
        .order_by(BaselineRevision.revision_no.desc())
    ).all()


def create_baseline_revision(
    db: Session,
    *,
    user: User,
    template: Template,
    media_object_id: int,
    source_type: str,
    source_report_id: int | None,
    source_case_run_id: int | None,
    source_step_result_id: int | None,
    remark: str | None,
    is_current: bool,
) -> BaselineRevision:
    """Create one baseline revision under an existing template.

    Args:
        db: Active database session.
        user: User creating the baseline revision.
        template: Parent template that will own the new baseline.
        media_object_id: Media object used as the baseline image.
        source_type: Declared source type before normalization/validation.
        source_report_id: Optional source report id when adopting from execution output.
        source_case_run_id: Optional source case-run id when adopting from execution output.
        source_step_result_id: Optional source step-result id when adopting from execution output.
        remark: Optional operator-facing remark.
        is_current: Whether the new baseline should become the current revision.

    Returns:
        The newly created baseline revision.
    """
    require_workspace_access(db, user, template.workspace_id)
    media = get_media_object(db, media_object_id)
    if media.workspace_id != template.workspace_id:
        raise ApiError(
            code="MEDIA_OBJECT_NOT_FOUND",
            message="Media object not found in workspace.",
            status_code=404,
        )
    normalized_source = _normalize_baseline_source(
        db,
        template=template,
        media_object_id=media_object_id,
        source_type=source_type,
        source_report_id=source_report_id,
        source_case_run_id=source_case_run_id,
        source_step_result_id=source_step_result_id,
    )
    max_revision = (
        db.scalar(
            select(func.max(BaselineRevision.revision_no)).where(
                BaselineRevision.template_id == template.id
            )
        )
        or 0
    )
    if is_current:
        current_list = db.scalars(
            select(BaselineRevision).where(
                BaselineRevision.template_id == template.id,
                BaselineRevision.is_current.is_(True),
            )
        ).all()
        for current in current_list:
            current.is_current = False
    baseline = BaselineRevision(
        template_id=template.id,
        revision_no=int(max_revision) + 1,
        media_object_id=media_object_id,
        source_type=str(normalized_source["source_type"]),
        source_report_id=normalized_source["source_report_id"],
        source_case_run_id=normalized_source["source_case_run_id"],
        source_step_result_id=normalized_source["source_step_result_id"],
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


def get_baseline_revision(db: Session, baseline_revision_id: int) -> BaselineRevision:
    baseline = db.get(BaselineRevision, baseline_revision_id)
    if baseline is None:
        raise ApiError(
            code="BASELINE_REVISION_NOT_FOUND",
            message="Baseline revision not found.",
            status_code=404,
        )
    return baseline


def get_template_ocr_result(
    db: Session,
    *,
    user: User,
    template: Template,
    baseline_revision_id: int,
) -> dict:
    require_workspace_access(db, user, template.workspace_id)
    baseline, media, _ = _resolve_template_baseline_context(
        db,
        template=template,
        baseline_revision_id=baseline_revision_id,
    )
    snapshot = db.scalar(
        select(TemplateOCRResult).where(
            TemplateOCRResult.template_id == template.id,
            TemplateOCRResult.baseline_revision_id == baseline_revision_id,
        )
    )
    if snapshot is None:
        return {
            "id": None,
            "template_id": template.id,
            "baseline_revision_id": baseline.id,
            "source_media_object_id": media.id,
            "status": OCR_RESULT_NOT_GENERATED_STATUS,
            "engine_name": OCR_ENGINE_NAME,
            "image_width": None,
            "image_height": None,
            "blocks": [],
            "error_code": "TEMPLATE_OCR_RESULT_NOT_FOUND",
            "error_message": "Template OCR result not found for the baseline revision.",
            "created_at": None,
            "updated_at": None,
        }
    return template_ocr_result_view(snapshot)


def analyze_template_ocr(
    db: Session,
    *,
    user: User,
    template: Template,
    baseline_revision_id: int,
) -> TemplateOCRResult:
    require_workspace_access(db, user, template.workspace_id)
    baseline, media, baseline_path = _resolve_template_baseline_context(
        db,
        template=template,
        baseline_revision_id=baseline_revision_id,
    )
    adapter = build_vision_assertion_adapter()
    image_png_bytes = baseline_path.read_bytes()
    try:
        analysis = adapter.analyze_ocr(image_png_bytes=image_png_bytes)
    except Exception as exc:  # noqa: BLE001
        _upsert_template_ocr_result(
            db,
            template_id=template.id,
            baseline_revision_id=baseline.id,
            source_media_object_id=media.id,
            status=OCR_RESULT_FAILED_STATUS,
            engine_name=OCR_ENGINE_NAME,
            image_width=None,
            image_height=None,
            result_json={"blocks": []},
            error_code="TEMPLATE_OCR_ANALYSIS_FAILED",
            error_message=_format_runtime_error(exc),
        )
        raise ApiError(
            code="TEMPLATE_OCR_ANALYSIS_FAILED",
            message="Template OCR analysis failed.",
            status_code=500,
            details=[
                {"field": "baseline_revision_id", "reason": _format_runtime_error(exc)}
            ],
        ) from exc

    return _upsert_template_ocr_result(
        db,
        template_id=template.id,
        baseline_revision_id=baseline.id,
        source_media_object_id=media.id,
        status=OCR_RESULT_SUCCESS_STATUS,
        engine_name=str(analysis.get("engine_name") or OCR_ENGINE_NAME),
        image_width=int(analysis["image_width"]),
        image_height=int(analysis["image_height"]),
        result_json={"blocks": list(analysis.get("blocks", []))},
        error_code=None,
        error_message=None,
    )


def create_template_preview_images(
    db: Session,
    *,
    user: User,
    template: Template,
    baseline_revision_id: int,
    mask_regions: list[dict] | None,
) -> dict:
    require_workspace_access(db, user, template.workspace_id)
    baseline, media, baseline_path = _resolve_template_baseline_context(
        db,
        template=template,
        baseline_revision_id=baseline_revision_id,
    )
    normalized_mask_regions = _normalize_preview_mask_regions(
        db,
        template=template,
        payload_regions=mask_regions,
    )
    adapter = build_vision_assertion_adapter()
    image_png_bytes = baseline_path.read_bytes()
    try:
        preview = adapter.build_mask_preview(
            image_png_bytes=image_png_bytes,
            mask_regions=[
                MaskRegionRatio(
                    x_ratio=region["x_ratio"],
                    y_ratio=region["y_ratio"],
                    width_ratio=region["width_ratio"],
                    height_ratio=region["height_ratio"],
                )
                for region in normalized_mask_regions
            ],
        )
    except Exception as exc:  # noqa: BLE001
        raise ApiError(
            code="TEMPLATE_PREVIEW_GENERATION_FAILED",
            message="Template preview generation failed.",
            status_code=500,
            details=[
                {"field": "baseline_revision_id", "reason": _format_runtime_error(exc)}
            ],
        ) from exc

    overlay_media = create_media_object_from_bytes(
        db,
        user=user,
        workspace_id=template.workspace_id,
        file_bytes=preview["overlay_png_bytes"],
        file_name=f"template-{template.id}-baseline-{baseline.id}-overlay.png",
        mime_type="image/png",
        usage="artifact",
        remark=f"template-{template.id}-baseline-{baseline.id}-preview-overlay",
    )
    processed_media = create_media_object_from_bytes(
        db,
        user=user,
        workspace_id=template.workspace_id,
        file_bytes=preview["processed_png_bytes"],
        file_name=f"template-{template.id}-baseline-{baseline.id}-processed.png",
        mime_type="image/png",
        usage="artifact",
        remark=f"template-{template.id}-baseline-{baseline.id}-preview-processed",
    )
    return {
        "template_id": template.id,
        "baseline_revision_id": baseline.id,
        "source_media_object_id": media.id,
        "image_width": int(preview["image_width"]),
        "image_height": int(preview["image_height"]),
        "overlay_media_object_id": overlay_media.id,
        "overlay_content_url": _media_content_url(overlay_media.id),
        "processed_media_object_id": processed_media.id,
        "processed_content_url": _media_content_url(processed_media.id),
        "mask_regions": normalized_mask_regions,
    }


def list_mask_regions(db: Session, *, user: User, template: Template):
    require_workspace_access(db, user, template.workspace_id)
    return db.scalars(
        select(TemplateMaskRegion)
        .where(TemplateMaskRegion.template_id == template.id)
        .order_by(TemplateMaskRegion.sort_order.asc())
    ).all()


def _validate_ratios(
    x_ratio: float, y_ratio: float, width_ratio: float, height_ratio: float
) -> None:
    if not (
        0 <= x_ratio < 1
        and 0 <= y_ratio < 1
        and 0 < width_ratio <= 1
        and 0 < height_ratio <= 1
    ):
        raise ApiError(
            code="MASK_REGION_OUT_OF_RANGE",
            message="Mask region ratios are out of range.",
            status_code=422,
        )
    if x_ratio + width_ratio > 1 or y_ratio + height_ratio > 1:
        raise ApiError(
            code="MASK_REGION_OUT_OF_RANGE",
            message="Mask region exceeds template bounds.",
            status_code=422,
        )


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
        raise ApiError(
            code="MASK_REGION_NOT_FOUND",
            message="Mask region not found.",
            status_code=404,
        )
    return region


def update_mask_region(
    db: Session, *, user: User, region: TemplateMaskRegion, payload: dict
) -> TemplateMaskRegion:
    template = get_template(db, region.template_id)
    require_workspace_access(db, user, template.workspace_id)
    data = {
        "region_name": payload.get("region_name", region.region_name),
        "x_ratio": payload.get("x_ratio", float(region.x_ratio)),
        "y_ratio": payload.get("y_ratio", float(region.y_ratio)),
        "width_ratio": payload.get("width_ratio", float(region.width_ratio)),
        "height_ratio": payload.get("height_ratio", float(region.height_ratio)),
        "sort_order": payload.get("sort_order", region.sort_order),
    }
    _validate_ratios(
        data["x_ratio"], data["y_ratio"], data["width_ratio"], data["height_ratio"]
    )
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


def template_ocr_result_view(snapshot: TemplateOCRResult) -> dict:
    payload = snapshot.result_json or {}
    return {
        "id": snapshot.id,
        "template_id": snapshot.template_id,
        "baseline_revision_id": snapshot.baseline_revision_id,
        "source_media_object_id": snapshot.source_media_object_id,
        "status": snapshot.status,
        "engine_name": snapshot.engine_name,
        "image_width": snapshot.image_width,
        "image_height": snapshot.image_height,
        "blocks": list(payload.get("blocks", [])),
        "error_code": snapshot.error_code,
        "error_message": snapshot.error_message,
        "created_at": snapshot.created_at,
        "updated_at": snapshot.updated_at,
    }


def _resolve_template_baseline_context(
    db: Session,
    *,
    template: Template,
    baseline_revision_id: int,
) -> tuple[BaselineRevision, MediaObject, Path]:
    baseline = get_baseline_revision(db, baseline_revision_id)
    if baseline.template_id != template.id:
        raise ApiError(
            code="BASELINE_REVISION_NOT_FOUND",
            message="Baseline revision not found.",
            status_code=404,
        )
    media = get_media_object(db, baseline.media_object_id)
    if media.workspace_id != template.workspace_id:
        raise ApiError(
            code="MEDIA_OBJECT_NOT_FOUND",
            message="Media object not found in workspace.",
            status_code=404,
        )
    return baseline, media, storage_backend.resolve_path(media.object_key)


def _upsert_template_ocr_result(
    db: Session,
    *,
    template_id: int,
    baseline_revision_id: int,
    source_media_object_id: int,
    status: str,
    engine_name: str,
    image_width: int | None,
    image_height: int | None,
    result_json: dict,
    error_code: str | None,
    error_message: str | None,
) -> TemplateOCRResult:
    snapshot = db.scalar(
        select(TemplateOCRResult).where(
            TemplateOCRResult.template_id == template_id,
            TemplateOCRResult.baseline_revision_id == baseline_revision_id,
        )
    )
    if snapshot is None:
        snapshot = TemplateOCRResult(
            template_id=template_id,
            baseline_revision_id=baseline_revision_id,
            source_media_object_id=source_media_object_id,
            status=status,
            engine_name=engine_name,
            image_width=image_width,
            image_height=image_height,
            result_json=result_json,
            error_code=error_code,
            error_message=error_message,
        )
        db.add(snapshot)
    else:
        snapshot.source_media_object_id = source_media_object_id
        snapshot.status = status
        snapshot.engine_name = engine_name
        snapshot.image_width = image_width
        snapshot.image_height = image_height
        snapshot.result_json = result_json
        snapshot.error_code = error_code
        snapshot.error_message = error_message
    db.commit()
    db.refresh(snapshot)
    return snapshot


def _normalize_preview_mask_regions(
    db: Session,
    *,
    template: Template,
    payload_regions: list[dict] | None,
) -> list[dict]:
    if payload_regions is None:
        persisted_regions = db.scalars(
            select(TemplateMaskRegion)
            .where(TemplateMaskRegion.template_id == template.id)
            .order_by(TemplateMaskRegion.sort_order.asc(), TemplateMaskRegion.id.asc())
        ).all()
        return [
            {
                "name": region.region_name,
                "x_ratio": float(region.x_ratio),
                "y_ratio": float(region.y_ratio),
                "width_ratio": float(region.width_ratio),
                "height_ratio": float(region.height_ratio),
                "sort_order": int(region.sort_order),
            }
            for region in persisted_regions
        ]

    normalized_regions: list[dict] = []
    for index, item in enumerate(payload_regions, start=1):
        region = {
            "name": str(item.get("name") or f"mask_region_{index}"),
            "x_ratio": float(item["x_ratio"]),
            "y_ratio": float(item["y_ratio"]),
            "width_ratio": float(item["width_ratio"]),
            "height_ratio": float(item["height_ratio"]),
            "sort_order": int(item.get("sort_order") or index),
        }
        _validate_ratios(
            region["x_ratio"],
            region["y_ratio"],
            region["width_ratio"],
            region["height_ratio"],
        )
        normalized_regions.append(region)
    normalized_regions.sort(key=lambda item: (item["sort_order"], item["name"]))
    return normalized_regions


def _media_content_url(media_object_id: int) -> str:
    return f"{settings.api_v1_prefix}/media-objects/{media_object_id}/content"


def _format_runtime_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc).strip() or 'unexpected runtime error'}"


def _validate_template_contract(*, match_strategy: str, status: str) -> None:
    if match_strategy not in SUPPORTED_TEMPLATE_MATCH_STRATEGIES:
        raise ApiError(
            code="TEMPLATE_MATCH_STRATEGY_UNSUPPORTED",
            message="Template match_strategy currently only supports `template` or `ocr`.",
            status_code=422,
        )
    if status not in SUPPORTED_TEMPLATE_STATUSES:
        raise ApiError(
            code="TEMPLATE_STATUS_INVALID",
            message="Template status must be `draft`, `published`, or `archived`.",
            status_code=422,
        )


def _normalize_baseline_source(
    db: Session,
    *,
    template: Template,
    media_object_id: int,
    source_type: str,
    source_report_id: int | None,
    source_case_run_id: int | None,
    source_step_result_id: int | None,
) -> dict[str, int | str | None]:
    if source_type not in SUPPORTED_BASELINE_SOURCE_TYPES:
        raise ApiError(
            code="BASELINE_SOURCE_TYPE_INVALID",
            message="Baseline revision source type is invalid.",
            status_code=422,
        )
    if source_type != "adopted_from_failure":
        if (
            source_report_id is not None
            or source_case_run_id is not None
            or source_step_result_id is not None
        ):
            raise ApiError(
                code="BASELINE_ADOPTION_INVALID",
                message="Failure evidence source fields are only allowed for adopted_from_failure baselines.",
                status_code=422,
            )
        return {
            "source_type": source_type,
            "source_report_id": None,
            "source_case_run_id": None,
            "source_step_result_id": None,
        }
    if source_step_result_id is None:
        raise ApiError(
            code="BASELINE_ADOPTION_INVALID",
            message="Failure evidence adoption requires source_step_result_id.",
            status_code=422,
        )

    step_result = db.get(StepResult, source_step_result_id)
    if step_result is None:
        raise ApiError(
            code="BASELINE_ADOPTION_MISMATCH",
            message="Failure evidence does not belong to the template baseline chain.",
            status_code=422,
        )
    if step_result.status not in {"failed", "error"}:
        raise ApiError(
            code="BASELINE_ADOPTION_INVALID",
            message="Failure evidence adoption requires a failed or errored step result.",
            status_code=422,
        )
    if step_result.actual_media_object_id != media_object_id:
        raise ApiError(
            code="BASELINE_ADOPTION_INVALID",
            message="Failure evidence adoption requires the step actual media object.",
            status_code=422,
        )
    if step_result.expected_media_object_id is None:
        raise ApiError(
            code="BASELINE_ADOPTION_MISMATCH",
            message="Failure evidence does not belong to the template baseline chain.",
            status_code=422,
        )

    template_baseline = db.scalar(
        select(BaselineRevision).where(
            BaselineRevision.template_id == template.id,
            BaselineRevision.media_object_id == step_result.expected_media_object_id,
        )
    )
    if template_baseline is None:
        raise ApiError(
            code="BASELINE_ADOPTION_MISMATCH",
            message="Failure evidence does not belong to the template baseline chain.",
            status_code=422,
        )

    case_run = db.get(TestCaseRun, step_result.case_run_id)
    if case_run is None:
        raise ApiError(
            code="BASELINE_ADOPTION_MISMATCH",
            message="Failure evidence does not belong to the template baseline chain.",
            status_code=422,
        )
    report = db.scalar(
        select(RunReport).where(RunReport.test_run_id == case_run.test_run_id)
    )
    if report is None:
        raise ApiError(
            code="BASELINE_ADOPTION_MISMATCH",
            message="Failure evidence does not belong to the template baseline chain.",
            status_code=422,
        )
    if source_case_run_id is not None and source_case_run_id != case_run.id:
        raise ApiError(
            code="BASELINE_ADOPTION_MISMATCH",
            message="Failure evidence does not belong to the requested case run.",
            status_code=422,
        )
    if source_report_id is not None and source_report_id != report.id:
        raise ApiError(
            code="BASELINE_ADOPTION_MISMATCH",
            message="Failure evidence does not belong to the requested report.",
            status_code=422,
        )
    return {
        "source_type": source_type,
        "source_report_id": report.id,
        "source_case_run_id": case_run.id,
        "source_step_result_id": step_result.id,
    }
