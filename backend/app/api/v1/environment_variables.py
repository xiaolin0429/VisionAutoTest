from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.http import no_content_response, success_response
from app.db.session import get_db
from app.schemas.contracts import (
    EnvironmentVariableCreate,
    EnvironmentVariableRead,
    EnvironmentVariableUpdate,
)
from app.services import workspace as workspace_service

router = APIRouter(tags=["workspaces"])


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
