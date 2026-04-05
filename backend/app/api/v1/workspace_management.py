from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.utils import dump_list, dump_model
from app.core.http import paginated_response, success_response
from app.db.session import get_db
from app.schemas.contracts import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate
from app.services import workspace as workspace_service
from app.services.helpers import page_bounds

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
