from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.models import Component, ComponentStep, User
from app.services.case_service_common import published_at_for_status
from app.services.helpers import (
    apply_keyword,
    count_total,
    require_workspace_access,
)


def list_components(
    db: Session,
    *,
    user: User,
    workspace_id: int,
    page: int,
    page_size: int,
    keyword: str | None = None,
    status: str | None = None,
):
    require_workspace_access(db, user, workspace_id)
    stmt = select(Component).where(
        Component.workspace_id == workspace_id, Component.is_deleted.is_(False)
    )
    if status:
        stmt = stmt.where(Component.status == status)
    stmt = apply_keyword(
        stmt, keyword, Component.component_code, Component.component_name
    )
    total = count_total(db, stmt)
    items = db.scalars(
        stmt.order_by(Component.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return items, total


def create_component(
    db: Session,
    *,
    user: User,
    workspace_id: int,
    component_code: str,
    component_name: str,
    status: str,
    description: str | None,
) -> Component:
    require_workspace_access(db, user, workspace_id)
    existing = db.scalar(
        select(Component).where(
            Component.workspace_id == workspace_id,
            Component.component_code == component_code,
            Component.is_deleted.is_(False),
        )
    )
    if existing is not None:
        raise ApiError(
            code="COMPONENT_CODE_EXISTS",
            message="Component code already exists.",
            status_code=409,
        )
    component = Component(
        workspace_id=workspace_id,
        component_code=component_code,
        component_name=component_name,
        status=status,
        description=description,
        published_at=published_at_for_status(status),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(component)
    db.commit()
    db.refresh(component)
    return component


def get_component(db: Session, component_id: int) -> Component:
    component = db.get(Component, component_id)
    if component is None or component.is_deleted:
        raise ApiError(
            code="COMPONENT_NOT_FOUND", message="Component not found.", status_code=404
        )
    return component


def update_component(
    db: Session,
    *,
    user: User,
    component: Component,
    component_name: str | None,
    status: str | None,
    description: str | None,
) -> Component:
    require_workspace_access(db, user, component.workspace_id)
    if component_name is not None:
        component.component_name = component_name
    if status is not None:
        component.status = status
        component.published_at = published_at_for_status(status, component.published_at)
    if description is not None:
        component.description = description
    component.updated_by = user.id
    db.commit()
    db.refresh(component)
    return component


def list_component_steps(
    db: Session, *, user: User, component: Component
) -> Sequence[ComponentStep]:
    require_workspace_access(db, user, component.workspace_id)
    return db.scalars(
        select(ComponentStep)
        .where(ComponentStep.component_id == component.id)
        .order_by(ComponentStep.step_no.asc())
    ).all()
