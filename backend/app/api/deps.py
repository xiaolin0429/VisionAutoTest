from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.db.session import get_db
from app.services.iam import get_current_user_by_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_actor(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    if credentials is None:
        raise ApiError(code="UNAUTHORIZED", message="Authorization header is required.", status_code=401)
    return get_current_user_by_token(db, credentials.credentials)


def get_current_user(actor=Depends(get_current_actor)):
    return actor[0]


def get_current_session(actor=Depends(get_current_actor)):
    return actor[1]


def get_workspace_header(
    x_workspace_id: Annotated[int | None, Header(alias="X-Workspace-Id")] = None,
) -> int | None:
    return x_workspace_id

