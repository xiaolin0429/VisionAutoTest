from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_workspace_header
from app.api.utils import dump_model, dump_list
from app.core.http import (
    ApiError,
    no_content_response,
    paginated_response,
    success_response,
)
from app.db.session import get_db
from app.schemas.contracts import (
    DeviceProfileCreate,
    DeviceProfileRead,
    DeviceProfileUpdate,
    ExecutionReadinessSummaryRead,
    EnvironmentProfileCreate,
    EnvironmentProfileRead,
    EnvironmentProfileUpdate,
    EnvironmentVariableCreate,
    EnvironmentVariableRead,
    EnvironmentVariableUpdate,
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberRead,
    WorkspaceMemberUpdate,
    WorkspaceRead,
    WorkspaceUpdate,
)
from app.services import workspace as workspace_service
from app.services import execution as execution_service
from app.services.helpers import page_bounds, require_workspace_id

router = APIRouter(tags=["workspaces"])


@router.get("/workspaces")
def list_workspaces(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    page, page_size = page_bounds(page, page_size)
    items, total = workspace_service.list_workspaces(
        db,
        user=current_user,
        page=page,
        page_size=page_size,
        status=status,
        keyword=keyword,
    )
    return paginated_response(
        request,
        dump_list(WorkspaceRead, items),
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/workspaces", status_code=201)
def create_workspace(
    payload: WorkspaceCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    workspace = workspace_service.create_workspace(
        db,
        user=current_user,
        workspace_code=payload.workspace_code,
        name=payload.workspace_name,
        description=payload.description,
        status=payload.status,
    )
    return success_response(
        request, dump_model(WorkspaceRead, workspace), status_code=201
    )


@router.get("/workspaces/{workspace_id}")
def get_workspace(
    workspace_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    workspace = workspace_service.require_workspace_access(
        db, current_user, workspace_id
    )
    return success_response(request, dump_model(WorkspaceRead, workspace))


@router.get("/workspaces/{workspace_id}/execution-readiness")
def get_workspace_execution_readiness(
    workspace_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    readiness = execution_service.get_workspace_execution_readiness(
        db,
        user=current_user,
        workspace_id=workspace_id,
    )
    return success_response(
        request,
        ExecutionReadinessSummaryRead.model_validate(readiness).model_dump(mode="json"),
    )


@router.patch("/workspaces/{workspace_id}")
def patch_workspace(
    workspace_id: int,
    payload: WorkspaceUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    workspace = workspace_service.require_workspace(db, workspace_id)
    updated = workspace_service.update_workspace(
        db,
        workspace,
        user=current_user,
        name=payload.workspace_name,
        description=payload.description,
        status=payload.status,
    )
    return success_response(request, dump_model(WorkspaceRead, updated))


@router.get("/workspaces/{workspace_id}/members")
def list_workspace_members(
    workspace_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    items = workspace_service.list_members(
        db, user=current_user, workspace_id=workspace_id
    )
    return success_response(request, dump_list(WorkspaceMemberRead, items))


@router.post("/workspaces/{workspace_id}/members", status_code=201)
def create_workspace_member(
    workspace_id: int,
    payload: WorkspaceMemberCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    member = workspace_service.add_member(
        db,
        user=current_user,
        workspace_id=workspace_id,
        user_id=payload.user_id,
        workspace_role=payload.workspace_role,
    )
    return success_response(
        request, dump_model(WorkspaceMemberRead, member), status_code=201
    )


@router.patch("/workspaces/{workspace_id}/members/{member_id}")
def patch_workspace_member(
    workspace_id: int,
    member_id: int,
    payload: WorkspaceMemberUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    member = workspace_service.get_member(db, member_id)
    if member.workspace_id != workspace_id:
        raise ApiError(
            code="WORKSPACE_MEMBER_NOT_FOUND",
            message="Workspace member not found.",
            status_code=404,
        )
    updated = workspace_service.update_member(
        db,
        user=current_user,
        member=member,
        workspace_role=payload.workspace_role,
        status=payload.status,
    )
    return success_response(request, dump_model(WorkspaceMemberRead, updated))


@router.delete("/workspaces/{workspace_id}/members/{member_id}", status_code=204)
def delete_workspace_member(
    workspace_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    member = workspace_service.get_member(db, member_id)
    if member.workspace_id != workspace_id:
        raise ApiError(
            code="WORKSPACE_MEMBER_NOT_FOUND",
            message="Workspace member not found.",
            status_code=404,
        )
    workspace_service.remove_member(db, user=current_user, member=member)
    return no_content_response()


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


@router.get("/environment-profiles/{environment_profile_id}/variables")
def list_environment_variables(
    environment_profile_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    profile = workspace_service.get_environment_profile(db, environment_profile_id)
    items = workspace_service.list_environment_variables(
        db, user=current_user, profile=profile
    )
    data = [workspace_service.environment_variable_view(item) for item in items]
    return success_response(request, data)


@router.post(
    "/environment-profiles/{environment_profile_id}/variables", status_code=201
)
def create_environment_variable(
    environment_profile_id: int,
    payload: EnvironmentVariableCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    profile = workspace_service.get_environment_profile(db, environment_profile_id)
    variable = workspace_service.create_environment_variable(
        db,
        user=current_user,
        profile=profile,
        var_key=payload.var_key,
        value=payload.value,
        is_secret=payload.is_secret,
        description=payload.description,
    )
    return success_response(
        request,
        EnvironmentVariableRead.model_validate(
            workspace_service.environment_variable_view(variable)
        ).model_dump(mode="json"),
        status_code=201,
    )


@router.patch("/environment-variables/{environment_variable_id}")
def patch_environment_variable(
    environment_variable_id: int,
    payload: EnvironmentVariableUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    variable = workspace_service.get_environment_variable(db, environment_variable_id)
    updated = workspace_service.update_environment_variable(
        db,
        user=current_user,
        variable=variable,
        value=payload.value,
        is_secret=payload.is_secret,
        description=payload.description,
    )
    return success_response(
        request,
        EnvironmentVariableRead.model_validate(
            workspace_service.environment_variable_view(updated)
        ).model_dump(mode="json"),
    )


@router.delete("/environment-variables/{environment_variable_id}", status_code=204)
def delete_environment_variable(
    environment_variable_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    variable = workspace_service.get_environment_variable(db, environment_variable_id)
    workspace_service.delete_environment_variable(
        db, user=current_user, variable=variable
    )
    return no_content_response()


@router.get("/device-profiles")
def list_device_profiles(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
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
