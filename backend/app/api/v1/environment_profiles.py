from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_workspace_header
from app.api.utils import dump_list, dump_model
from app.core.http import no_content_response, paginated_response, success_response
from app.db.session import get_db
from app.schemas.contracts import (
    EnvironmentProfileCreate,
    EnvironmentProfileRead,
    EnvironmentProfileUpdate,
)
from app.services import workspace as workspace_service
from app.services.helpers import page_bounds, require_workspace_id

router = APIRouter(tags=["workspaces"])


@router.get("/environment-profiles")
def list_environment_profiles(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    page, page_size = page_bounds(page, page_size)
    workspace_id = require_workspace_id(workspace_id)
    items, total = workspace_service.list_environment_profiles(
        db,
        user=current_user,
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
    )
    return paginated_response(
        request,
        dump_list(EnvironmentProfileRead, items),
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/environment-profiles", status_code=201)
def create_environment_profile(
    payload: EnvironmentProfileCreate,
    request: Request,
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    workspace_id = require_workspace_id(workspace_id)
    profile = workspace_service.create_environment_profile(
        db,
        user=current_user,
        workspace_id=workspace_id,
        profile_name=payload.profile_name,
        base_url=payload.base_url,
        description=payload.description,
        status=payload.status,
    )
    return success_response(
        request, dump_model(EnvironmentProfileRead, profile), status_code=201
    )


@router.get("/environment-profiles/{environment_profile_id}")
def get_environment_profile(
    environment_profile_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    profile = workspace_service.get_environment_profile(db, environment_profile_id)
    workspace_service.require_workspace_access(db, current_user, profile.workspace_id)
    return success_response(request, dump_model(EnvironmentProfileRead, profile))


@router.patch("/environment-profiles/{environment_profile_id}")
def patch_environment_profile(
    environment_profile_id: int,
    payload: EnvironmentProfileUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    profile = workspace_service.get_environment_profile(db, environment_profile_id)
    updated = workspace_service.update_environment_profile(
        db,
        user=current_user,
        profile=profile,
        profile_name=payload.profile_name,
        base_url=payload.base_url,
        description=payload.description,
        status=payload.status,
    )
    return success_response(request, dump_model(EnvironmentProfileRead, updated))


@router.delete("/environment-profiles/{environment_profile_id}", status_code=204)
def delete_environment_profile(
    environment_profile_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    profile = workspace_service.get_environment_profile(db, environment_profile_id)
    workspace_service.delete_environment_profile(db, user=current_user, profile=profile)
    return no_content_response()
