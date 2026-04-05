from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.utils import dump_list, dump_model
from app.core.http import ApiError, no_content_response, success_response
from app.db.session import get_db
from app.schemas.contracts import (
    WorkspaceMemberCreate,
    WorkspaceMemberRead,
    WorkspaceMemberUpdate,
)
from app.services import workspace as workspace_service

router = APIRouter(tags=["workspaces"])


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
