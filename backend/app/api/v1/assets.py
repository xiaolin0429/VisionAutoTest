from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_workspace_header
from app.api.utils import dump_model, dump_list
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
    TemplateRead,
    TemplateUpdate,
)
from app.services import assets
from app.services.helpers import page_bounds, require_workspace_id

router = APIRouter(tags=["assets"])


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
    workspace_id = require_workspace_id(workspace_id)
    media = assets.create_media_object(
        db,
        user=current_user,
        workspace_id=workspace_id,
        file=file,
        usage=usage,
        remark=remark,
    )
    return success_response(request, dump_model(MediaObjectRead, media), status_code=201)


@router.get("/media-objects/{media_object_id}")
def get_media_object(media_object_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    media = assets.get_media_object(db, media_object_id)
    assets.require_workspace_access(db, current_user, media.workspace_id)
    return success_response(request, dump_model(MediaObjectRead, media))


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
    return paginated_response(request, dump_list(MediaObjectRead, items), page=page, page_size=page_size, total=total)


@router.patch("/media-objects/{media_object_id}")
def patch_media_object(media_object_id: int, payload: MediaObjectUpdate, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    media = assets.get_media_object(db, media_object_id)
    updated = assets.update_media_object(db, user=current_user, media=media, status=payload.status, remark=payload.remark)
    return success_response(request, dump_model(MediaObjectRead, updated))


@router.get("/media-objects/{media_object_id}/references")
def get_media_object_references(media_object_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
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
    return paginated_response(request, dump_list(TemplateRead, items), page=page, page_size=page_size, total=total)


@router.post("/templates", status_code=201)
def create_template(
    payload: TemplateCreate,
    request: Request,
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
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
    return success_response(request, dump_model(TemplateRead, template), status_code=201)


@router.get("/templates/{template_id}")
def get_template(template_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    template = assets.get_template(db, template_id)
    assets.require_workspace_access(db, current_user, template.workspace_id)
    return success_response(request, dump_model(TemplateRead, template))


@router.patch("/templates/{template_id}")
def patch_template(template_id: int, payload: TemplateUpdate, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    template = assets.get_template(db, template_id)
    updated = assets.update_template(db, user=current_user, template=template, payload=payload.model_dump(exclude_none=True))
    return success_response(request, dump_model(TemplateRead, updated))


@router.get("/templates/{template_id}/baseline-revisions")
def list_baseline_revisions(template_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    template = assets.get_template(db, template_id)
    items = assets.list_baseline_revisions(db, user=current_user, template=template)
    return success_response(request, dump_list(BaselineRevisionRead, items))


@router.post("/templates/{template_id}/baseline-revisions", status_code=201)
def create_baseline_revision(template_id: int, payload: BaselineRevisionCreate, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    template = assets.get_template(db, template_id)
    baseline = assets.create_baseline_revision(
        db,
        user=current_user,
        template=template,
        media_object_id=payload.media_object_id,
        source_type=payload.source_type,
        remark=payload.remark,
        is_current=payload.is_current,
    )
    return success_response(request, dump_model(BaselineRevisionRead, baseline), status_code=201)


@router.get("/templates/{template_id}/mask-regions")
def list_mask_regions(template_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    template = assets.get_template(db, template_id)
    items = assets.list_mask_regions(db, user=current_user, template=template)
    return success_response(request, dump_list(MaskRegionRead, items))


@router.post("/templates/{template_id}/mask-regions", status_code=201)
def create_mask_region(template_id: int, payload: MaskRegionCreate, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    template = assets.get_template(db, template_id)
    region = assets.create_mask_region(
        db,
        user=current_user,
        template=template,
        name=payload.name,
        x_ratio=payload.x_ratio,
        y_ratio=payload.y_ratio,
        width_ratio=payload.width_ratio,
        height_ratio=payload.height_ratio,
        sort_order=payload.sort_order,
    )
    return success_response(request, dump_model(MaskRegionRead, region), status_code=201)


@router.patch("/mask-regions/{mask_region_id}")
def patch_mask_region(mask_region_id: int, payload: MaskRegionUpdate, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    region = assets.get_mask_region(db, mask_region_id)
    updated = assets.update_mask_region(db, user=current_user, region=region, payload=payload.model_dump(exclude_none=True))
    return success_response(request, dump_model(MaskRegionRead, updated))


@router.delete("/mask-regions/{mask_region_id}", status_code=204)
def delete_mask_region(mask_region_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    region = assets.get_mask_region(db, mask_region_id)
    assets.delete_mask_region(db, user=current_user, region=region)
    return no_content_response()

