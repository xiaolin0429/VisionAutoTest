from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.models import SuiteCase, TestSuite, User
from app.services.helpers import (
    count_total,
    require_workspace_access,
    validate_ordered_sequence,
)
from app.services.test_case_service import get_test_case


def list_test_suites(
    db: Session, *, user: User, workspace_id: int, page: int, page_size: int
):
    require_workspace_access(db, user, workspace_id)
    stmt = select(TestSuite).where(
        TestSuite.workspace_id == workspace_id, TestSuite.is_deleted.is_(False)
    )
    total = count_total(db, stmt)
    items = db.scalars(
        stmt.order_by(TestSuite.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return items, total


def create_test_suite(
    db: Session,
    *,
    user: User,
    workspace_id: int,
    suite_code: str,
    suite_name: str,
    status: str,
    description: str | None,
) -> TestSuite:
    require_workspace_access(db, user, workspace_id)
    existing = db.scalar(
        select(TestSuite).where(
            TestSuite.workspace_id == workspace_id,
            TestSuite.suite_code == suite_code,
            TestSuite.is_deleted.is_(False),
        )
    )
    if existing is not None:
        raise ApiError(
            code="TEST_SUITE_CODE_EXISTS",
            message="Test suite code already exists.",
            status_code=409,
        )
    suite = TestSuite(
        workspace_id=workspace_id,
        suite_code=suite_code,
        suite_name=suite_name,
        status=status,
        description=description,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(suite)
    db.commit()
    db.refresh(suite)
    return suite


def get_test_suite(db: Session, test_suite_id: int) -> TestSuite:
    suite = db.get(TestSuite, test_suite_id)
    if suite is None or suite.is_deleted:
        raise ApiError(
            code="TEST_SUITE_NOT_FOUND",
            message="Test suite not found.",
            status_code=404,
        )
    return suite


def update_test_suite(
    db: Session,
    *,
    user: User,
    suite: TestSuite,
    suite_name: str | None,
    status: str | None,
    description: str | None,
) -> TestSuite:
    require_workspace_access(db, user, suite.workspace_id)
    if suite_name is not None:
        suite.suite_name = suite_name
    if status is not None:
        suite.status = status
    if description is not None:
        suite.description = description
    suite.updated_by = user.id
    db.commit()
    db.refresh(suite)
    return suite


def list_suite_cases(
    db: Session, *, user: User, suite: TestSuite
) -> Sequence[SuiteCase]:
    require_workspace_access(db, user, suite.workspace_id)
    return db.scalars(
        select(SuiteCase)
        .where(SuiteCase.test_suite_id == suite.id)
        .order_by(SuiteCase.sort_order.asc())
    ).all()


def replace_suite_cases(
    db: Session, *, user: User, suite: TestSuite, items: list[dict]
) -> list[SuiteCase]:
    require_workspace_access(db, user, suite.workspace_id)
    validate_ordered_sequence(
        [item["sort_order"] for item in items],
        code="SUITE_CASE_SEQUENCE_INVALID",
        message="Suite case order must start from 1 and be continuous.",
    )
    for item in items:
        test_case = get_test_case(db, item["test_case_id"])
        if test_case.workspace_id != suite.workspace_id:
            raise ApiError(
                code="TEST_CASE_NOT_FOUND",
                message="Test case not found in workspace.",
                status_code=404,
            )
    db.execute(delete(SuiteCase).where(SuiteCase.test_suite_id == suite.id))
    for item in items:
        db.add(
            SuiteCase(
                test_suite_id=suite.id,
                test_case_id=item["test_case_id"],
                sort_order=item["sort_order"],
            )
        )
    db.commit()
    return list(list_suite_cases(db, user=user, suite=suite))
