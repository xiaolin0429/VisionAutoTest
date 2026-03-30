from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.models import (
    Component,
    ComponentStep,
    SuiteCase,
    Template,
    TestCase,
    TestCaseStep,
    TestSuite,
    User,
    utc_now,
)
from app.services.assets import SUPPORTED_TEMPLATE_MATCH_STRATEGIES
from app.services.helpers import apply_keyword, count_total, require_workspace_access, validate_ordered_sequence

SUPPORTED_NAVIGATE_WAIT_UNTIL = {"load", "domcontentloaded", "networkidle"}
SUPPORTED_SCROLL_TARGETS = {"page", "element"}
SUPPORTED_SCROLL_DIRECTIONS = {"up", "down", "left", "right"}
SUPPORTED_SCROLL_BEHAVIORS = {"auto", "smooth"}
SUPPORTED_LONG_PRESS_BUTTONS = {"left"}


def _published_at_for_status(status: str, current_published_at=None):
    if status == "published" and current_published_at is None:
        return utc_now()
    return current_published_at


def list_components(db: Session, *, user: User, workspace_id: int, page: int, page_size: int):
    require_workspace_access(db, user, workspace_id)
    stmt = select(Component).where(Component.workspace_id == workspace_id, Component.is_deleted.is_(False))
    total = count_total(db, stmt)
    items = db.scalars(stmt.order_by(Component.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def create_component(db: Session, *, user: User, workspace_id: int, component_code: str, component_name: str, status: str, description: str | None) -> Component:
    require_workspace_access(db, user, workspace_id)
    existing = db.scalar(
        select(Component).where(
            Component.workspace_id == workspace_id,
            Component.component_code == component_code,
            Component.is_deleted.is_(False),
        )
    )
    if existing is not None:
        raise ApiError(code="COMPONENT_CODE_EXISTS", message="Component code already exists.", status_code=409)
    component = Component(
        workspace_id=workspace_id,
        component_code=component_code,
        component_name=component_name,
        status=status,
        description=description,
        published_at=_published_at_for_status(status),
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
        raise ApiError(code="COMPONENT_NOT_FOUND", message="Component not found.", status_code=404)
    return component


def update_component(db: Session, *, user: User, component: Component, component_name: str | None, status: str | None, description: str | None) -> Component:
    require_workspace_access(db, user, component.workspace_id)
    if component_name is not None:
        component.component_name = component_name
    if status is not None:
        component.status = status
        component.published_at = _published_at_for_status(status, component.published_at)
    if description is not None:
        component.description = description
    component.updated_by = user.id
    db.commit()
    db.refresh(component)
    return component


def list_component_steps(db: Session, *, user: User, component: Component):
    require_workspace_access(db, user, component.workspace_id)
    return db.scalars(
        select(ComponentStep).where(ComponentStep.component_id == component.id).order_by(ComponentStep.step_no.asc())
    ).all()


def replace_component_steps(db: Session, *, user: User, component: Component, steps: list[dict]) -> list[ComponentStep]:
    require_workspace_access(db, user, component.workspace_id)
    validate_ordered_sequence([item["step_no"] for item in steps], code="STEP_SEQUENCE_INVALID", message="Step sequence must start from 1 and be continuous.")
    db.execute(delete(ComponentStep).where(ComponentStep.component_id == component.id))
    for item in steps:
        _validate_step_payload(db, workspace_id=component.workspace_id, item=item, allow_component_call=False)
        db.add(
            ComponentStep(
                component_id=component.id,
                step_no=item["step_no"],
                step_type=item["step_type"],
                step_name=item["step_name"],
                template_id=item.get("template_id"),
                payload_json=item.get("payload_json", {}),
                timeout_ms=item.get("timeout_ms", 15000),
                retry_times=item.get("retry_times", 0),
            )
        )
    db.commit()
    return list_component_steps(db, user=user, component=component)


def list_test_cases(db: Session, *, user: User, workspace_id: int, page: int, page_size: int, status: str | None, keyword: str | None):
    require_workspace_access(db, user, workspace_id)
    stmt = select(TestCase).where(TestCase.workspace_id == workspace_id, TestCase.is_deleted.is_(False))
    if status:
        stmt = stmt.where(TestCase.status == status)
    stmt = apply_keyword(stmt, keyword, TestCase.case_code, TestCase.case_name)
    total = count_total(db, stmt)
    items = db.scalars(stmt.order_by(TestCase.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def create_test_case(db: Session, *, user: User, workspace_id: int, case_code: str, case_name: str, status: str, priority: str, description: str | None) -> TestCase:
    require_workspace_access(db, user, workspace_id)
    existing = db.scalar(
        select(TestCase).where(
            TestCase.workspace_id == workspace_id,
            TestCase.case_code == case_code,
            TestCase.is_deleted.is_(False),
        )
    )
    if existing is not None:
        raise ApiError(code="TEST_CASE_CODE_EXISTS", message="Test case code already exists.", status_code=409)
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
        raise ApiError(code="TEST_CASE_NOT_FOUND", message="Test case not found.", status_code=404)
    return test_case


def update_test_case(db: Session, *, user: User, test_case: TestCase, case_name: str | None, status: str | None, priority: str | None, description: str | None) -> TestCase:
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


def list_test_case_steps(db: Session, *, user: User, test_case: TestCase):
    require_workspace_access(db, user, test_case.workspace_id)
    return db.scalars(
        select(TestCaseStep).where(TestCaseStep.test_case_id == test_case.id).order_by(TestCaseStep.step_no.asc())
    ).all()


def replace_test_case_steps(db: Session, *, user: User, test_case: TestCase, steps: list[dict]) -> list[TestCaseStep]:
    require_workspace_access(db, user, test_case.workspace_id)
    validate_ordered_sequence([item["step_no"] for item in steps], code="STEP_SEQUENCE_INVALID", message="Step sequence must start from 1 and be continuous.")
    db.execute(delete(TestCaseStep).where(TestCaseStep.test_case_id == test_case.id))
    for item in steps:
        _validate_step_payload(db, workspace_id=test_case.workspace_id, item=item, allow_component_call=True)
        if item.get("component_id") is not None:
            get_component(db, item["component_id"])
        db.add(
            TestCaseStep(
                test_case_id=test_case.id,
                step_no=item["step_no"],
                step_type=item["step_type"],
                step_name=item["step_name"],
                component_id=item.get("component_id"),
                template_id=item.get("template_id"),
                payload_json=item.get("payload_json", {}),
                timeout_ms=item.get("timeout_ms", 15000),
                retry_times=item.get("retry_times", 0),
            )
        )
    db.commit()
    return list_test_case_steps(db, user=user, test_case=test_case)


def list_test_suites(db: Session, *, user: User, workspace_id: int, page: int, page_size: int):
    require_workspace_access(db, user, workspace_id)
    stmt = select(TestSuite).where(TestSuite.workspace_id == workspace_id, TestSuite.is_deleted.is_(False))
    total = count_total(db, stmt)
    items = db.scalars(stmt.order_by(TestSuite.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def create_test_suite(db: Session, *, user: User, workspace_id: int, suite_code: str, suite_name: str, status: str, description: str | None) -> TestSuite:
    require_workspace_access(db, user, workspace_id)
    existing = db.scalar(
        select(TestSuite).where(
            TestSuite.workspace_id == workspace_id,
            TestSuite.suite_code == suite_code,
            TestSuite.is_deleted.is_(False),
        )
    )
    if existing is not None:
        raise ApiError(code="TEST_SUITE_CODE_EXISTS", message="Test suite code already exists.", status_code=409)
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
        raise ApiError(code="TEST_SUITE_NOT_FOUND", message="Test suite not found.", status_code=404)
    return suite


def update_test_suite(db: Session, *, user: User, suite: TestSuite, suite_name: str | None, status: str | None, description: str | None) -> TestSuite:
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


def list_suite_cases(db: Session, *, user: User, suite: TestSuite):
    require_workspace_access(db, user, suite.workspace_id)
    return db.scalars(
        select(SuiteCase).where(SuiteCase.test_suite_id == suite.id).order_by(SuiteCase.sort_order.asc())
    ).all()


def replace_suite_cases(db: Session, *, user: User, suite: TestSuite, items: list[dict]) -> list[SuiteCase]:
    require_workspace_access(db, user, suite.workspace_id)
    validate_ordered_sequence([item["sort_order"] for item in items], code="SUITE_CASE_SEQUENCE_INVALID", message="Suite case order must start from 1 and be continuous.")
    for item in items:
        test_case = get_test_case(db, item["test_case_id"])
        if test_case.workspace_id != suite.workspace_id:
            raise ApiError(code="TEST_CASE_NOT_FOUND", message="Test case not found in workspace.", status_code=404)
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
    return list_suite_cases(db, user=user, suite=suite)


def _assert_template(db: Session, workspace_id: int, template_id: int) -> None:
    template = db.get(Template, template_id)
    if template is None or template.workspace_id != workspace_id or template.is_deleted:
        raise ApiError(code="TEMPLATE_NOT_FOUND", message="Template not found.", status_code=404)


def _validate_step_payload(db: Session, *, workspace_id: int, item: dict, allow_component_call: bool) -> None:
    step_type = item.get("step_type")
    payload = item.get("payload_json") or {}
    template_id = item.get("template_id")

    if step_type == "component_call":
        if not allow_component_call:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="component_call is not supported inside component steps.",
                status_code=422,
            )
        if item.get("component_id") is None:
            raise ApiError(code="STEP_CONFIGURATION_INVALID", message="component_call step requires component_id.", status_code=422)
        return

    if template_id is not None:
        _assert_template(db, workspace_id, template_id)
        template = db.get(Template, template_id)
        assert template is not None
        if template.match_strategy not in SUPPORTED_TEMPLATE_MATCH_STRATEGIES:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="Referenced template match_strategy is not supported in the current version.",
                status_code=422,
            )

    if step_type == "template_assert":
        if template_id is None:
            raise ApiError(code="STEP_CONFIGURATION_INVALID", message="template_assert step requires template_id.", status_code=422)
        template = db.get(Template, template_id)
        assert template is not None
        if template.match_strategy != "template":
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="template_assert step requires template match_strategy `template`.",
                status_code=422,
            )
        threshold = payload.get("threshold")
        if threshold is not None and (isinstance(threshold, bool) or not isinstance(threshold, (int, float))):
            raise ApiError(code="STEP_CONFIGURATION_INVALID", message="template_assert threshold must be numeric.", status_code=422)
        if isinstance(threshold, (int, float)) and not (0 <= float(threshold) <= 1):
            raise ApiError(code="STEP_CONFIGURATION_INVALID", message="template_assert threshold must be between 0 and 1.", status_code=422)
        return

    if step_type == "ocr_assert":
        selector = payload.get("selector")
        expected_text = payload.get("expected_text")
        if not isinstance(selector, str) or not selector.strip():
            raise ApiError(code="STEP_CONFIGURATION_INVALID", message="ocr_assert step requires payload_json.selector.", status_code=422)
        if not isinstance(expected_text, str) or not expected_text.strip():
            raise ApiError(code="STEP_CONFIGURATION_INVALID", message="ocr_assert step requires payload_json.expected_text.", status_code=422)
        if template_id is not None:
            template = db.get(Template, template_id)
            assert template is not None
            if template.match_strategy != "ocr":
                raise ApiError(
                    code="STEP_CONFIGURATION_INVALID",
                    message="ocr_assert step requires template match_strategy `ocr`.",
                    status_code=422,
                )
        match_mode = payload.get("match_mode")
        if match_mode is not None and match_mode not in {"exact", "contains"}:
            raise ApiError(code="STEP_CONFIGURATION_INVALID", message="ocr_assert match_mode must be `exact` or `contains`.", status_code=422)
        case_sensitive = payload.get("case_sensitive")
        if case_sensitive is not None and not isinstance(case_sensitive, bool):
            raise ApiError(code="STEP_CONFIGURATION_INVALID", message="ocr_assert case_sensitive must be boolean.", status_code=422)
        return

    if step_type == "navigate":
        _validate_navigate_payload(payload)
        return

    if step_type == "scroll":
        _validate_scroll_payload(payload)
        return

    if step_type == "long_press":
        _validate_long_press_payload(payload)


def _validate_navigate_payload(payload: dict) -> None:
    url = payload.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ApiError(code="STEP_CONFIGURATION_INVALID", message="navigate step requires payload_json.url.", status_code=422)
    parsed_url = urlparse(url)
    if parsed_url.scheme:
        if parsed_url.scheme not in {"http", "https"}:
            raise ApiError(
                code="STEP_CONFIGURATION_INVALID",
                message="navigate url must be an absolute http/https URL or a path starting with `/`.",
                status_code=422,
            )
    elif not url.startswith("/"):
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="navigate url must be an absolute http/https URL or a path starting with `/`.",
            status_code=422,
        )

    wait_until = payload.get("wait_until")
    if wait_until is not None and wait_until not in SUPPORTED_NAVIGATE_WAIT_UNTIL:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="navigate wait_until must be `load`, `domcontentloaded`, or `networkidle`.",
            status_code=422,
        )


def _validate_scroll_payload(payload: dict) -> None:
    target = payload.get("target")
    if target not in SUPPORTED_SCROLL_TARGETS:
        raise ApiError(code="STEP_CONFIGURATION_INVALID", message="scroll target must be `page` or `element`.", status_code=422)

    selector = payload.get("selector")
    if target == "element" and (not isinstance(selector, str) or not selector.strip()):
        raise ApiError(code="STEP_CONFIGURATION_INVALID", message="scroll step requires payload_json.selector when target is `element`.", status_code=422)

    direction = payload.get("direction")
    if direction not in SUPPORTED_SCROLL_DIRECTIONS:
        raise ApiError(
            code="STEP_CONFIGURATION_INVALID",
            message="scroll direction must be `up`, `down`, `left`, or `right`.",
            status_code=422,
        )

    distance = payload.get("distance")
    if isinstance(distance, bool) or not isinstance(distance, (int, float)) or float(distance) <= 0:
        raise ApiError(code="STEP_CONFIGURATION_INVALID", message="scroll distance must be a numeric value greater than 0.", status_code=422)

    behavior = payload.get("behavior")
    if behavior is not None and behavior not in SUPPORTED_SCROLL_BEHAVIORS:
        raise ApiError(code="STEP_CONFIGURATION_INVALID", message="scroll behavior must be `auto` or `smooth`.", status_code=422)


def _validate_long_press_payload(payload: dict) -> None:
    selector = payload.get("selector")
    if not isinstance(selector, str) or not selector.strip():
        raise ApiError(code="STEP_CONFIGURATION_INVALID", message="long_press step requires payload_json.selector.", status_code=422)

    duration_ms = payload.get("duration_ms")
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, (int, float)) or float(duration_ms) <= 0:
        raise ApiError(code="STEP_CONFIGURATION_INVALID", message="long_press duration_ms must be a numeric value greater than 0.", status_code=422)

    button = payload.get("button")
    if button is not None and button not in SUPPORTED_LONG_PRESS_BUTTONS:
        raise ApiError(code="STEP_CONFIGURATION_INVALID", message="long_press button currently only supports `left`.", status_code=422)
