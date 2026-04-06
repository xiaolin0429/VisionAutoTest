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
    """Resolve the authenticated user/session pair for the current request.

    Args:
        db: Active database session used to load the bound session and user.
        credentials: Parsed bearer token from the Authorization header.

    Returns:
        A tuple of ``(user, session)`` for downstream dependencies and routes.

    Raises:
        ApiError: If the Authorization header is missing.
    """
    # Dependency resolution stops at authentication/session lookup. Resource-level
    # permission checks still belong in domain services or route-specific guards.
    if credentials is None:
        raise ApiError(
            code="UNAUTHORIZED",
            message="Authorization header is required.",
            status_code=401,
        )
    return get_current_user_by_token(db, credentials.credentials)


def get_current_user(actor=Depends(get_current_actor)):
    """Return only the authenticated user from ``get_current_actor``.

    Args:
        actor: Tuple returned by ``get_current_actor``.

    Returns:
        The authenticated user object for the request.
    """
    return actor[0]


def get_current_session(actor=Depends(get_current_actor)):
    """Return only the authenticated session from ``get_current_actor``.

    Args:
        actor: Tuple returned by ``get_current_actor``.

    Returns:
        The authenticated session object for the request.
    """
    return actor[1]


def get_workspace_header(
    x_workspace_id: Annotated[int | None, Header(alias="X-Workspace-Id")] = None,
) -> int | None:
    """Expose the raw workspace header for route-level workspace decisions.

    Args:
        x_workspace_id: Workspace id supplied by the client, if any.

    Returns:
        The parsed workspace id or ``None`` when the header is absent.
    """
    # The raw workspace header is exposed separately so endpoints can decide whether the
    # header is optional, mandatory, or needs additional membership validation.
    return x_workspace_id
