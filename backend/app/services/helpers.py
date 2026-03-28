from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.models import User, Workspace, WorkspaceMember


def page_bounds(page: int, page_size: int) -> tuple[int, int]:
    normalized_page = max(page, 1)
    normalized_page_size = min(max(page_size, 1), 100)
    return normalized_page, normalized_page_size


def count_total(db: Session, stmt) -> int:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    return int(total or 0)


def apply_keyword(stmt, keyword: str | None, *columns):
    if not keyword:
        return stmt
    like_value = f"%{keyword}%"
    return stmt.where(or_(*[column.ilike(like_value) for column in columns]))


def require_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise ApiError(code="USER_NOT_FOUND", message="User not found.", status_code=404)
    return user


def require_workspace(db: Session, workspace_id: int) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.is_deleted:
        raise ApiError(code="WORKSPACE_NOT_FOUND", message="Workspace not found.", status_code=404)
    return workspace


def require_workspace_access(db: Session, user: User, workspace_id: int) -> Workspace:
    workspace = require_workspace(db, workspace_id)
    if workspace.owner_user_id == user.id:
        return workspace
    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.status == "active",
        )
    )
    if member is None:
        raise ApiError(
            code="WORKSPACE_FORBIDDEN",
            message="Current user does not have access to the workspace.",
            status_code=403,
        )
    return workspace


def require_workspace_admin(db: Session, user: User, workspace_id: int) -> Workspace:
    workspace = require_workspace_access(db, user, workspace_id)
    if workspace.owner_user_id == user.id:
        return workspace
    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.status == "active",
            WorkspaceMember.workspace_role == "workspace_admin",
        )
    )
    if member is None:
        raise ApiError(
            code="WORKSPACE_FORBIDDEN",
            message="Workspace admin permission is required.",
            status_code=403,
        )
    return workspace


def require_workspace_id(workspace_id: int | None) -> int:
    if workspace_id is None:
        raise ApiError(code="WORKSPACE_ID_REQUIRED", message="X-Workspace-Id header is required.", status_code=400)
    return workspace_id


def validate_ordered_sequence(values: list[int], *, code: str, message: str) -> None:
    if values != list(range(1, len(values) + 1)):
        raise ApiError(code=code, message=message, status_code=422)

