from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_session, get_current_user
from app.api.utils import dump_model, dump_list
from app.core.http import no_content_response, paginated_response, success_response
from app.db.session import get_db
from app.models import User
from app.schemas.contracts import (
    SessionCreate,
    SessionRefreshCreate,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.services import iam
from app.services.helpers import page_bounds

router = APIRouter(tags=["iam"])


@router.post("/sessions", status_code=201)
def create_session(
    payload: SessionCreate, request: Request, db: Session = Depends(get_db)
):
    """Create a login session.

    Args:
        payload: Session-create payload carrying username and password.
        request: FastAPI request used for response wrapping and client metadata capture.
        db: Active database session.
    """
    session_payload = iam.create_session(
        db,
        payload.username,
        payload.password,
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    return success_response(request, session_payload, status_code=201)


@router.post("/session-refreshes", status_code=201)
def create_session_refresh(
    payload: SessionRefreshCreate, request: Request, db: Session = Depends(get_db)
):
    """Refresh an existing login session.

    Args:
        payload: Refresh payload carrying the current refresh token.
        request: FastAPI request used for response wrapping.
        db: Active database session.
    """
    data = iam.refresh_session(db, payload.refresh_token)
    return success_response(request, data, status_code=201)


@router.get("/sessions/current")
def get_current_login_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    current_session=Depends(get_current_session),
):
    """Return the current authenticated session snapshot.

    Args:
        request: FastAPI request used for response wrapping.
        current_user: Authenticated user resolved from the access token.
        current_session: Authenticated session resolved from the access token.
    """
    data = {
        "session_id": current_session.session_code,
        "status": current_session.status,
        "expires_at": current_session.expires_at.isoformat(),
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "display_name": current_user.display_name,
        },
    }
    return success_response(request, data)


@router.delete("/sessions/current", status_code=204)
def delete_current_login_session(
    db: Session = Depends(get_db), current_session=Depends(get_current_session)
):
    """Revoke the current login session.

    Args:
        db: Active database session.
        current_session: Authenticated session resolved from the access token.
    """
    iam.revoke_current_session(db, current_session)
    return no_content_response()


@router.get("/users/current")
def get_current_login_user(
    request: Request, current_user: User = Depends(get_current_user)
):
    """Return the current authenticated user.

    Args:
        request: FastAPI request used for response wrapping.
        current_user: Authenticated user resolved from the access token.
    """
    return success_response(request, dump_model(UserRead, current_user))


@router.get("/users")
def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List users with optional status/keyword filters.

    Args:
        request: FastAPI request used for paginated response wrapping.
        page: Requested page number.
        page_size: Requested page size.
        status: Optional user status filter.
        keyword: Optional keyword filter.
        db: Active database session.
        _: Authenticated user guard placeholder.
    """
    page, page_size = page_bounds(page, page_size)
    items, total = iam.list_users(
        db, page=page, page_size=page_size, status=status, keyword=keyword
    )
    return paginated_response(
        request, dump_list(UserRead, items), page=page, page_size=page_size, total=total
    )


@router.post("/users", status_code=201)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Create a user.

    Args:
        payload: User-create payload.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        _: Authenticated user guard placeholder.
    """
    user = iam.create_user(
        db,
        username=payload.username,
        display_name=payload.display_name,
        password=payload.password,
        email=payload.email,
        mobile=payload.mobile,
        status=payload.status,
    )
    return success_response(request, dump_model(UserRead, user), status_code=201)


@router.get("/users/{user_id}")
def get_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get one user by id.

    Args:
        user_id: Target user id.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        _: Authenticated user guard placeholder.
    """
    user = iam.get_user(db, user_id)
    return success_response(request, dump_model(UserRead, user))


@router.patch("/users/{user_id}")
def patch_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Update a user.

    Args:
        user_id: Target user id.
        payload: User-update payload.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        _: Authenticated user guard placeholder.
    """
    user = iam.get_user(db, user_id)
    updated = iam.update_user(
        db,
        user,
        display_name=payload.display_name,
        email=payload.email,
        mobile=payload.mobile,
        status=payload.status,
    )
    return success_response(request, dump_model(UserRead, updated))
