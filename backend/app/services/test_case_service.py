from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.models import TestCase, TestCaseStep, User, utc_now
from app.services.helpers import (
    apply_keyword,
    count_total,
    require_workspace_access,
)


def list_test_cases(
    db: Session,
    *,
    user: User,
    workspace_id: int,
    page: int,
    page_size: int,
    status: str | None,
    keyword: str | None,
):
    require_workspace_access(db, user, workspace_id)
    stmt = select(TestCase).where(
        TestCase.workspace_id == workspace_id, TestCase.is_deleted.is_(False)
    )
    if status:
        stmt = stmt.where(TestCase.status == status)
    stmt = apply_keyword(stmt, keyword, TestCase.case_code, TestCase.case_name)
    total = count_total(db, stmt)
    items = db.scalars(
        stmt.order_by(TestCase.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return items, total


def create_test_case(
    db: Session,
    *,
    user: User,
    workspace_id: int,
    case_code: str,
    case_name: str,
    status: str,
    priority: str,
    description: str | None,
) -> TestCase:
    require_workspace_access(db, user, workspace_id)
    existing = db.scalar(
        select(TestCase).where(
            TestCase.workspace_id == workspace_id,
            TestCase.case_code == case_code,
            TestCase.is_deleted.is_(False),
        )
    )
    if existing is not None:
        raise ApiError(
            code="TEST_CASE_CODE_EXISTS",
            message="Test case code already exists.",
            status_code=409,
        )
    test_case = TestCase(
        workspace_id=workspace_id,
        case_code=case_code,
        case_name=case_name,
        status=status,
        priority=priority,
        description=description,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    return test_case


def get_test_case(db: Session, test_case_id: int) -> TestCase:
    test_case = db.get(TestCase, test_case_id)
    if test_case is None or test_case.is_deleted:
        raise ApiError(
            code="TEST_CASE_NOT_FOUND", message="Test case not found.", status_code=404
        )
    return test_case


def update_test_case(
    db: Session,
    *,
    user: User,
    test_case: TestCase,
    case_name: str | None,
    status: str | None,
    priority: str | None,
    description: str | None,
) -> TestCase:
    require_workspace_access(db, user, test_case.workspace_id)
    if case_name is not None:
        test_case.case_name = case_name
    if status is not None:
        test_case.status = status
    if priority is not None:
        test_case.priority = priority
    if description is not None:
        test_case.description = description
    test_case.updated_by = user.id
    db.commit()
    db.refresh(test_case)
    return test_case


def list_test_case_steps(
    db: Session, *, user: User, test_case: TestCase
) -> Sequence[TestCaseStep]:
    require_workspace_access(db, user, test_case.workspace_id)
    return db.scalars(
        select(TestCaseStep)
        .where(TestCaseStep.test_case_id == test_case.id)
        .order_by(TestCaseStep.step_no.asc())
    ).all()


def clone_test_case(db: Session, *, user: User, test_case: TestCase) -> TestCase:
    require_workspace_access(db, user, test_case.workspace_id)
    timestamp_suffix = utc_now().strftime("%Y%m%d%H%M%S")
    new_code = f"{test_case.case_code}_copy_{timestamp_suffix}"
    cloned = TestCase(
        workspace_id=test_case.workspace_id,
        case_code=new_code,
        case_name=f"{test_case.case_name} (副本)",
        status="draft",
        priority=test_case.priority,
        description=test_case.description,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(cloned)
    db.flush()
    source_steps = db.scalars(
        select(TestCaseStep)
        .where(TestCaseStep.test_case_id == test_case.id)
        .order_by(TestCaseStep.step_no.asc())
    ).all()
    for step in source_steps:
        db.add(
            TestCaseStep(
                test_case_id=cloned.id,
                step_no=step.step_no,
                step_type=step.step_type,
                step_name=step.step_name,
                component_id=step.component_id,
                template_id=step.template_id,
                payload_json=step.payload_json,
                timeout_ms=step.timeout_ms,
                retry_times=step.retry_times,
            )
        )
    db.commit()
    db.refresh(cloned)
    return cloned
