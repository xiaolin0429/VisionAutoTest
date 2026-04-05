from __future__ import annotations

from collections.abc import Sequence
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
from app.services.branch_validator import (
    validate_branch_condition,
    validate_branch_steps,
    validate_conditional_branch_payload,
)
from app.services.case_service_common import published_at_for_status
from app.services.component_service import (
    create_component as create_component_service,
    get_component as get_component_service,
    list_component_steps as list_component_steps_service,
    list_components as list_components_service,
    update_component as update_component_service,
)
from app.services.suite_service import (
    create_test_suite as create_test_suite_service,
    get_test_suite as get_test_suite_service,
    list_suite_cases as list_suite_cases_service,
    list_test_suites as list_test_suites_service,
    replace_suite_cases as replace_suite_cases_service,
    update_test_suite as update_test_suite_service,
)
from app.services.test_case_service import (
    clone_test_case as clone_test_case_service,
    create_test_case as create_test_case_service,
    get_test_case as get_test_case_service,
    list_test_case_steps as list_test_case_steps_service,
    list_test_cases as list_test_cases_service,
    update_test_case as update_test_case_service,
)
from app.services.step_payload_validator import (
    validate_interaction_locator,
    validate_long_press_payload,
    validate_navigate_payload,
    validate_ocr_locator_fields,
    validate_scroll_payload,
    validate_step_payload,
    validate_visual_locator_fields,
)
from app.services.step_validation_common import (
    SUPPORTED_INPUT_MODES,
    SUPPORTED_LOCATOR_TYPES,
    SUPPORTED_LONG_PRESS_BUTTONS,
    SUPPORTED_NAVIGATE_WAIT_UNTIL,
    SUPPORTED_OCR_MATCH_MODES,
    SUPPORTED_SCROLL_BEHAVIORS,
    SUPPORTED_SCROLL_DIRECTIONS,
    SUPPORTED_SCROLL_TARGETS,
    assert_template,
)
from app.services import execution
from app.services.helpers import (
    apply_keyword,
    count_total,
    require_workspace_access,
    validate_ordered_sequence,
)


def _published_at_for_status(status: str, current_published_at=None):
    return published_at_for_status(status, current_published_at)


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
    return list_components_service(
        db,
        user=user,
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
        keyword=keyword,
        status=status,
    )


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
    return create_component_service(
        db,
        user=user,
        workspace_id=workspace_id,
        component_code=component_code,
        component_name=component_name,
        status=status,
        description=description,
    )


def get_component(db: Session, component_id: int) -> Component:
    return get_component_service(db, component_id)


def update_component(
    db: Session,
    *,
    user: User,
    component: Component,
    component_name: str | None,
    status: str | None,
    description: str | None,
) -> Component:
    return update_component_service(
        db,
        user=user,
        component=component,
        component_name=component_name,
        status=status,
        description=description,
    )


def list_component_steps(
    db: Session, *, user: User, component: Component
) -> Sequence[ComponentStep]:
    return list_component_steps_service(db, user=user, component=component)


def replace_component_steps(
    db: Session, *, user: User, component: Component, steps: list[dict]
) -> list[ComponentStep]:
    require_workspace_access(db, user, component.workspace_id)
    validate_ordered_sequence(
        [item["step_no"] for item in steps],
        code="STEP_SEQUENCE_INVALID",
        message="Step sequence must start from 1 and be continuous.",
    )
    db.execute(delete(ComponentStep).where(ComponentStep.component_id == component.id))
    for item in steps:
        _validate_step_payload(
            db,
            workspace_id=component.workspace_id,
            item=item,
            allow_component_call=False,
        )
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
    return list(list_component_steps(db, user=user, component=component))


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
    return list_test_cases_service(
        db,
        user=user,
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
        status=status,
        keyword=keyword,
    )


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
    return create_test_case_service(
        db,
        user=user,
        workspace_id=workspace_id,
        case_code=case_code,
        case_name=case_name,
        status=status,
        priority=priority,
        description=description,
    )


def get_test_case(db: Session, test_case_id: int) -> TestCase:
    return get_test_case_service(db, test_case_id)


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
    return update_test_case_service(
        db,
        user=user,
        test_case=test_case,
        case_name=case_name,
        status=status,
        priority=priority,
        description=description,
    )


def list_test_case_steps(
    db: Session, *, user: User, test_case: TestCase
) -> Sequence[TestCaseStep]:
    return list_test_case_steps_service(db, user=user, test_case=test_case)


def replace_test_case_steps(
    db: Session, *, user: User, test_case: TestCase, steps: list[dict]
) -> list[TestCaseStep]:
    require_workspace_access(db, user, test_case.workspace_id)
    validate_ordered_sequence(
        [item["step_no"] for item in steps],
        code="STEP_SEQUENCE_INVALID",
        message="Step sequence must start from 1 and be continuous.",
    )
    db.execute(delete(TestCaseStep).where(TestCaseStep.test_case_id == test_case.id))
    for item in steps:
        _validate_step_payload(
            db,
            workspace_id=test_case.workspace_id,
            item=item,
            allow_component_call=True,
        )
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
    return list(list_test_case_steps(db, user=user, test_case=test_case))


def clone_test_case(db: Session, *, user: User, test_case: TestCase) -> TestCase:
    return clone_test_case_service(db, user=user, test_case=test_case)


def list_test_suites(
    db: Session, *, user: User, workspace_id: int, page: int, page_size: int
):
    return list_test_suites_service(
        db, user=user, workspace_id=workspace_id, page=page, page_size=page_size
    )


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
    return create_test_suite_service(
        db,
        user=user,
        workspace_id=workspace_id,
        suite_code=suite_code,
        suite_name=suite_name,
        status=status,
        description=description,
    )


def get_test_suite(db: Session, test_suite_id: int) -> TestSuite:
    return get_test_suite_service(db, test_suite_id)


def update_test_suite(
    db: Session,
    *,
    user: User,
    suite: TestSuite,
    suite_name: str | None,
    status: str | None,
    description: str | None,
) -> TestSuite:
    return update_test_suite_service(
        db,
        user=user,
        suite=suite,
        suite_name=suite_name,
        status=status,
        description=description,
    )


def list_suite_cases(
    db: Session, *, user: User, suite: TestSuite
) -> Sequence[SuiteCase]:
    return list_suite_cases_service(db, user=user, suite=suite)


def replace_suite_cases(
    db: Session, *, user: User, suite: TestSuite, items: list[dict]
) -> list[SuiteCase]:
    return replace_suite_cases_service(db, user=user, suite=suite, items=items)


def _assert_template(db: Session, workspace_id: int, template_id: int) -> None:
    assert_template(db, workspace_id, template_id)


def _validate_step_payload(
    db: Session, *, workspace_id: int, item: dict, allow_component_call: bool
) -> None:
    validate_step_payload(
        db,
        workspace_id=workspace_id,
        item=item,
        allow_component_call=allow_component_call,
    )


def _validate_navigate_payload(payload: dict) -> None:
    validate_navigate_payload(payload)


def _validate_scroll_payload(payload: dict) -> None:
    validate_scroll_payload(payload)


def _validate_long_press_payload(payload: dict) -> None:
    validate_long_press_payload(payload)


def _validate_interaction_locator(
    payload: dict, step_type: str, *, require_selector: bool
) -> None:
    validate_interaction_locator(payload, step_type, require_selector=require_selector)


def _validate_ocr_locator_fields(payload: dict, step_type: str) -> None:
    validate_ocr_locator_fields(payload, step_type)


def _validate_visual_locator_fields(payload: dict, step_type: str) -> None:
    validate_visual_locator_fields(payload, step_type)


def _validate_conditional_branch_payload(
    db: Session, *, workspace_id: int, payload: dict
) -> None:
    validate_conditional_branch_payload(db, workspace_id=workspace_id, payload=payload)


def _validate_branch_condition(
    db: Session, *, workspace_id: int, condition: object
) -> None:
    validate_branch_condition(db, workspace_id=workspace_id, condition=condition)


def _validate_branch_steps(db: Session, *, workspace_id: int, steps: object) -> None:
    validate_branch_steps(db, workspace_id=workspace_id, steps=steps)
