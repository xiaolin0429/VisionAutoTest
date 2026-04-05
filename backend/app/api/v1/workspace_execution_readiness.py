from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.http import success_response
from app.db.session import get_db
from app.schemas.contracts import ExecutionReadinessSummaryRead
from app.services import execution as execution_service

router = APIRouter(tags=["workspaces"])


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
