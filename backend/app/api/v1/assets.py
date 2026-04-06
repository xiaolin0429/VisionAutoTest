from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_workspace_header
from app.api.utils import dump_model, dump_list
from app.core.config import get_settings
from app.core.storage import get_storage_backend
from app.core.http import no_content_response, paginated_response, success_response
from app.db.session import get_db
from app.schemas.contracts import (
    BaselineRevisionCreate,
    BaselineRevisionRead,
    MaskRegionCreate,
    MaskRegionRead,
    MaskRegionUpdate,
    MediaObjectRead,
    MediaObjectUpdate,
    TemplateCreate,
    TemplateOCRResultRead,
    TemplatePreviewCreate,
    TemplatePreviewRead,
    TemplateRead,
    TemplateUpdate,
)
from app.services import assets
from app.services.helpers import page_bounds, require_workspace_id

router = APIRouter(tags=["assets"])
settings = get_settings()
storage_backend = get_storage_backend()


@router.post("/media-objects", status_code=201)
def create_media_object(
    request: Request,
    file: UploadFile = File(...),
    usage: str = Form(...),
    remark: str | None = Form(None),
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Upload a media object into the current workspace.

    Args:
        request: FastAPI request used for response wrapping.
        file: Uploaded file stream.
        usage: Business usage tag for the media object.
        remark: Optional operator-facing remark.
        workspace_id: Workspace id resolved from ``X-Workspace-Id``.
        db: Active database session.
        current_user: Authenticated user.
    """
    workspace_id = require_workspace_id(workspace_id)
    media = assets.create_media_object(
        db,
        user=current_user,
        workspace_id=workspace_id,
        file=file,
        usage=usage,
        remark=remark,
    )
    return success_response(
        request, dump_model(MediaObjectRead, media), status_code=201
    )


@router.get("/media-objects/{media_object_id}")
def get_media_object(
    media_object_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get media-object metadata.

    Args:
        media_object_id: Target media-object id.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    media = assets.get_media_object(db, media_object_id)
    assets.require_workspace_access(db, current_user, media.workspace_id)
    return success_response(request, dump_model(MediaObjectRead, media))


@router.get("/media-objects/{media_object_id}/content")
def get_media_object_content(
    media_object_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Download media-object binary content.

    Args:
        media_object_id: Target media-object id.
        db: Active database session.
        current_user: Authenticated user.
    """
    media = assets.get_media_object(db, media_object_id)
    assets.require_workspace_access(db, current_user, media.workspace_id)
    file_path = storage_backend.resolve_path(media.object_key)
    return FileResponse(file_path, media_type=media.mime_type, filename=media.file_name)


@router.get("/media-objects")
def list_media_objects(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    usage: str | None = Query(None),
    status: str | None = Query(None),
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List media objects in the current workspace.

    Args:
        request: FastAPI request used for paginated response wrapping.
        page: Requested page number.
        page_size: Requested page size.
        usage: Optional usage filter.
        status: Optional media status filter.
        workspace_id: Workspace id resolved from ``X-Workspace-Id``.
        db: Active database session.
        current_user: Authenticated user.
    """
    page, page_size = page_bounds(page, page_size)
    workspace_id = require_workspace_id(workspace_id)
    items, total = assets.list_media_objects(
        db,
        user=current_user,
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
        usage=usage,
        status=status,
    )
    return paginated_response(
        request,
        dump_list(MediaObjectRead, items),
        page=page,
        page_size=page_size,
        total=total,
    )


@router.patch("/media-objects/{media_object_id}")
def patch_media_object(
    media_object_id: int,
    payload: MediaObjectUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update mutable media-object fields.

    Args:
        media_object_id: Target media-object id.
        payload: Media-object update payload.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    media = assets.get_media_object(db, media_object_id)
    updated = assets.update_media_object(
        db, user=current_user, media=media, status=payload.status, remark=payload.remark
    )
    return success_response(request, dump_model(MediaObjectRead, updated))


@router.get("/media-objects/{media_object_id}/references")
def get_media_object_references(
    media_object_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List business references pointing at a media object.

    Args:
        media_object_id: Target media-object id.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    media = assets.get_media_object(db, media_object_id)
    assets.require_workspace_access(db, current_user, media.workspace_id)
    return success_response(request, assets.media_references(db, media))


@router.get("/templates")
def list_templates(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    template_type: str | None = Query(None),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List templates in the current workspace.

    Args:
        request: FastAPI request used for paginated response wrapping.
        page: Requested page number.
        page_size: Requested page size.
        template_type: Optional template-type filter.
        status: Optional template status filter.
        keyword: Optional keyword filter.
        workspace_id: Workspace id resolved from ``X-Workspace-Id``.
        db: Active database session.
        current_user: Authenticated user.
    """
    page, page_size = page_bounds(page, page_size)
    workspace_id = require_workspace_id(workspace_id)
    items, total = assets.list_templates(
        db,
        user=current_user,
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
        template_type=template_type,
        status=status,
        keyword=keyword,
    )
    return paginated_response(
        request,
        dump_list(TemplateRead, items),
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/templates", status_code=201)
def create_template(
    payload: TemplateCreate,
    request: Request,
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a template in the current workspace.

    Args:
        payload: Template-create payload.
        request: FastAPI request used for response wrapping.
        workspace_id: Workspace id resolved from ``X-Workspace-Id``.
        db: Active database session.
        current_user: Authenticated user.
    """
    workspace_id = require_workspace_id(workspace_id)
    template = assets.create_template(
        db,
        user=current_user,
        workspace_id=workspace_id,
        template_code=payload.template_code,
        template_name=payload.template_name,
        template_type=payload.template_type,
        match_strategy=payload.match_strategy,
        threshold_value=payload.threshold_value,
        status=payload.status,
        original_media_object_id=payload.original_media_object_id,
    )
    return success_response(
        request, dump_model(TemplateRead, template), status_code=201
    )


@router.get("/templates/{template_id}")
def get_template(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get template metadata.

    Args:
        template_id: Target template id.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    template = assets.get_template(db, template_id)
    assets.require_workspace_access(db, current_user, template.workspace_id)
    return success_response(request, dump_model(TemplateRead, template))


@router.patch("/templates/{template_id}")
def patch_template(
    template_id: int,
    payload: TemplateUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update template summary fields.

    Args:
        template_id: Target template id.
        payload: Template-update payload.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    template = assets.get_template(db, template_id)
    updated = assets.update_template(
        db,
        user=current_user,
        template=template,
        payload=payload.model_dump(exclude_none=True),
    )
    return success_response(request, dump_model(TemplateRead, updated))


@router.get("/templates/{template_id}/baseline-revisions")
def list_baseline_revisions(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List baseline revisions under a template.

    Args:
        template_id: Parent template id.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    template = assets.get_template(db, template_id)
    items = assets.list_baseline_revisions(db, user=current_user, template=template)
    return success_response(request, dump_list(BaselineRevisionRead, items))


@router.post("/templates/{template_id}/baseline-revisions", status_code=201)
def create_baseline_revision(
    template_id: int,
    payload: BaselineRevisionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a baseline revision under a template.

    Args:
        template_id: Parent template id.
        payload: Baseline-revision create payload.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    template = assets.get_template(db, template_id)
    baseline = assets.create_baseline_revision(
        db,
        user=current_user,
        template=template,
        media_object_id=payload.media_object_id,
        source_type=payload.source_type,
        source_report_id=payload.source_report_id,
        source_case_run_id=payload.source_case_run_id,
        source_step_result_id=payload.source_step_result_id,
        remark=payload.remark,
        is_current=payload.is_current,
    )
    return success_response(
        request, dump_model(BaselineRevisionRead, baseline), status_code=201
    )


@router.get(
    "/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results"
)
def get_template_ocr_result(
    template_id: int,
    baseline_revision_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get the latest OCR result for one baseline revision.

    Args:
        template_id: Parent template id.
        baseline_revision_id: Baseline revision id.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    template = assets.get_template(db, template_id)
    snapshot = assets.get_template_ocr_result(
        db,
        user=current_user,
        template=template,
        baseline_revision_id=baseline_revision_id,
    )
    return success_response(request, dump_model(TemplateOCRResultRead, snapshot))


@router.post(
    "/templates/{template_id}/baseline-revisions/{baseline_revision_id}/ocr-results",
    status_code=201,
)
def create_template_ocr_result(
    template_id: int,
    baseline_revision_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Trigger OCR analysis for one template baseline revision.

    Args:
        template_id: Parent template id.
        baseline_revision_id: Baseline revision whose image should be analyzed.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    template = assets.get_template(db, template_id)
    snapshot = assets.analyze_template_ocr(
        db,
        user=current_user,
        template=template,
        baseline_revision_id=baseline_revision_id,
    )
    return success_response(
        request,
        dump_model(TemplateOCRResultRead, assets.template_ocr_result_view(snapshot)),
        status_code=201,
    )


@router.post(
    "/templates/{template_id}/baseline-revisions/{baseline_revision_id}/preview-images",
    status_code=201,
)
def create_template_preview_images(
    template_id: int,
    baseline_revision_id: int,
    payload: TemplatePreviewCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Generate processed preview images for one baseline revision.

    Args:
        template_id: Parent template id.
        baseline_revision_id: Baseline revision whose preview should be generated.
        payload: Optional mask-region payload used for draft preview generation.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    template = assets.get_template(db, template_id)
    preview = assets.create_template_preview_images(
        db,
        user=current_user,
        template=template,
        baseline_revision_id=baseline_revision_id,
        mask_regions=None
        if payload.mask_regions is None
        else [item.model_dump(exclude_none=True) for item in payload.mask_regions],
    )
    return success_response(
        request, dump_model(TemplatePreviewRead, preview), status_code=201
    )


@router.get("/templates/{template_id}/mask-regions")
def list_mask_regions(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List mask regions under a template.

    Args:
        template_id: Parent template id.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    template = assets.get_template(db, template_id)
    items = assets.list_mask_regions(db, user=current_user, template=template)
    return success_response(request, dump_list(MaskRegionRead, items))


@router.post("/templates/{template_id}/mask-regions", status_code=201)
def create_mask_region(
    template_id: int,
    payload: MaskRegionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a mask region under a template.

    Args:
        template_id: Parent template id.
        payload: Mask-region create payload.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    template = assets.get_template(db, template_id)
    region = assets.create_mask_region(
        db,
        user=current_user,
        template=template,
        name=payload.region_name,
        x_ratio=payload.x_ratio,
        y_ratio=payload.y_ratio,
        width_ratio=payload.width_ratio,
        height_ratio=payload.height_ratio,
        sort_order=payload.sort_order,
    )
    return success_response(
        request, dump_model(MaskRegionRead, region), status_code=201
    )


@router.patch("/mask-regions/{mask_region_id}")
def patch_mask_region(
    mask_region_id: int,
    payload: MaskRegionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update one mask region.

    Args:
        mask_region_id: Target mask-region id.
        payload: Mask-region update payload.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    region = assets.get_mask_region(db, mask_region_id)
    updated = assets.update_mask_region(
        db,
        user=current_user,
        region=region,
        payload=payload.model_dump(exclude_none=True),
    )
    return success_response(request, dump_model(MaskRegionRead, updated))


@router.delete("/mask-regions/{mask_region_id}", status_code=204)
def delete_mask_region(
    mask_region_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete one mask region.

    Args:
        mask_region_id: Target mask-region id.
        db: Active database session.
        current_user: Authenticated user.
    """
    region = assets.get_mask_region(db, mask_region_id)
    assets.delete_mask_region(db, user=current_user, region=region)
    return no_content_response()
