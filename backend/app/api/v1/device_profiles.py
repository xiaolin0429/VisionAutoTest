from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_workspace_header
from app.api.utils import dump_list, dump_model
from app.core.http import paginated_response, success_response
from app.db.session import get_db
from app.schemas.contracts import (
    DeviceProfileCreate,
    DeviceProfileRead,
    DeviceProfileUpdate,
)
from app.services import workspace as workspace_service
from app.services.helpers import page_bounds, require_workspace_id

router = APIRouter(tags=["workspaces"])


@router.get("/device-profiles")
def list_device_profiles(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List device profiles in the current workspace.

    Args:
        request: FastAPI request used for paginated response wrapping.
        page: Requested page number.
        page_size: Requested page size.
        workspace_id: Workspace id resolved from ``X-Workspace-Id``.
        db: Active database session.
        current_user: Authenticated user.
    """
    page, page_size = page_bounds(page, page_size)
    workspace_id = require_workspace_id(workspace_id)
    items, total = workspace_service.list_device_profiles(
        db,
        user=current_user,
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
    )
    return paginated_response(
        request,
        dump_list(DeviceProfileRead, items),
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/device-profiles", status_code=201)
def create_device_profile(
    payload: DeviceProfileCreate,
    request: Request,
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a device profile in the current workspace.

    Args:
        payload: Device-profile create payload.
        request: FastAPI request used for response wrapping.
        workspace_id: Workspace id resolved from ``X-Workspace-Id``.
        db: Active database session.
        current_user: Authenticated user.
    """
    workspace_id = require_workspace_id(workspace_id)
    profile = workspace_service.create_device_profile(
        db,
        user=current_user,
        workspace_id=workspace_id,
        profile_name=payload.profile_name,
        device_type=payload.device_type,
        viewport_width=payload.viewport_width,
        viewport_height=payload.viewport_height,
        device_scale_factor=payload.device_scale_factor,
        user_agent=payload.user_agent,
        is_default=payload.is_default,
    )
    return success_response(
        request, dump_model(DeviceProfileRead, profile), status_code=201
    )


@router.patch("/device-profiles/{device_profile_id}")
def patch_device_profile(
    device_profile_id: int,
    payload: DeviceProfileUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update a device profile.

    Args:
        device_profile_id: Target device-profile id.
        payload: Device-profile update payload.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    profile = workspace_service.get_device_profile(db, device_profile_id)
    updated = workspace_service.update_device_profile(
        db,
        user=current_user,
        profile=profile,
        profile_name=payload.profile_name,
        device_type=payload.device_type,
        viewport_width=payload.viewport_width,
        viewport_height=payload.viewport_height,
        device_scale_factor=payload.device_scale_factor,
        user_agent=payload.user_agent,
        is_default=payload.is_default,
    )
    return success_response(request, dump_model(DeviceProfileRead, updated))
