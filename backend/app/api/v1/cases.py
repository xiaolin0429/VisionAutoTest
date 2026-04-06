from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_workspace_header
from app.api.utils import dump_model, dump_list, dump_plain_list
from app.core.http import paginated_response, success_response
from app.db.session import get_db
from app.schemas.contracts import (
    ComponentCreate,
    ComponentRead,
    ComponentUpdate,
    ExecutionReadinessSummaryRead,
    StepWrite,
    SuiteCaseWrite,
    TestCaseCreate,
    TestCaseRead,
    TestCaseUpdate,
    TestSuiteCreate,
    TestSuiteRead,
    TestSuiteUpdate,
)
from app.services import cases
from app.services import execution as execution_service
from app.services.helpers import page_bounds, require_workspace_id

router = APIRouter(tags=["cases"])


@router.get("/components")
def list_components(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None),
    status: str | None = Query(None),
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List components in the current workspace.

    Args:
        request: FastAPI request used for paginated response wrapping.
        page: Requested page number.
        page_size: Requested page size.
        keyword: Optional component keyword filter.
        status: Optional component status filter.
        workspace_id: Workspace id resolved from ``X-Workspace-Id``.
        db: Active database session.
        current_user: Authenticated user.
    """
    page, page_size = page_bounds(page, page_size)
    workspace_id = require_workspace_id(workspace_id)
    items, total = cases.list_components(
        db,
        user=current_user,
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
        keyword=keyword,
        status=status,
    )
    return paginated_response(
        request,
        dump_list(ComponentRead, items),
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/components", status_code=201)
def create_component(
    payload: ComponentCreate,
    request: Request,
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    workspace_id = require_workspace_id(workspace_id)
    component = cases.create_component(
        db,
        user=current_user,
        workspace_id=workspace_id,
        component_code=payload.component_code,
        component_name=payload.component_name,
        status=payload.status,
        description=payload.description,
    )
    return success_response(
        request, dump_model(ComponentRead, component), status_code=201
    )


@router.get("/components/{component_id}")
def get_component(
    component_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    component = cases.get_component(db, component_id)
    cases.require_workspace_access(db, current_user, component.workspace_id)
    return success_response(request, dump_model(ComponentRead, component))


@router.patch("/components/{component_id}")
def patch_component(
    component_id: int,
    payload: ComponentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    component = cases.get_component(db, component_id)
    updated = cases.update_component(
        db,
        user=current_user,
        component=component,
        component_name=payload.component_name,
        status=payload.status,
        description=payload.description,
    )
    return success_response(request, dump_model(ComponentRead, updated))


@router.get("/components/{component_id}/steps")
def list_component_steps(
    component_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    component = cases.get_component(db, component_id)
    items = cases.list_component_steps(db, user=current_user, component=component)
    return success_response(request, dump_plain_list(items))


@router.put("/components/{component_id}/steps")
def put_component_steps(
    component_id: int,
    payload: list[StepWrite],
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Replace the full ordered component-step list.

    Args:
        component_id: Target component id.
        payload: Ordered component-step payload list.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    component = cases.get_component(db, component_id)
    items = cases.replace_component_steps(
        db,
        user=current_user,
        component=component,
        steps=[item.model_dump() for item in payload],
    )
    return success_response(request, dump_plain_list(items))


@router.get("/test-cases")
def list_test_cases(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    page, page_size = page_bounds(page, page_size)
    workspace_id = require_workspace_id(workspace_id)
    items, total = cases.list_test_cases(
        db,
        user=current_user,
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
        status=status,
        keyword=keyword,
    )
    return paginated_response(
        request,
        dump_list(TestCaseRead, items),
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/test-cases", status_code=201)
def create_test_case(
    payload: TestCaseCreate,
    request: Request,
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    workspace_id = require_workspace_id(workspace_id)
    test_case = cases.create_test_case(
        db,
        user=current_user,
        workspace_id=workspace_id,
        case_code=payload.case_code,
        case_name=payload.case_name,
        status=payload.status,
        priority=payload.priority,
        description=payload.description,
    )
    return success_response(
        request, dump_model(TestCaseRead, test_case), status_code=201
    )


@router.get("/test-cases/{test_case_id}")
def get_test_case(
    test_case_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    test_case = cases.get_test_case(db, test_case_id)
    cases.require_workspace_access(db, current_user, test_case.workspace_id)
    return success_response(request, dump_model(TestCaseRead, test_case))


@router.patch("/test-cases/{test_case_id}")
def patch_test_case(
    test_case_id: int,
    payload: TestCaseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    test_case = cases.get_test_case(db, test_case_id)
    updated = cases.update_test_case(
        db,
        user=current_user,
        test_case=test_case,
        case_name=payload.case_name,
        status=payload.status,
        priority=payload.priority,
        description=payload.description,
    )
    return success_response(request, dump_model(TestCaseRead, updated))


@router.post("/test-cases/{test_case_id}/clone", status_code=201)
def clone_test_case(
    test_case_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    test_case = cases.get_test_case(db, test_case_id)
    cloned = cases.clone_test_case(db, user=current_user, test_case=test_case)
    return success_response(request, dump_model(TestCaseRead, cloned), status_code=201)


@router.get("/test-cases/{test_case_id}/steps")
def list_test_case_steps(
    test_case_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    test_case = cases.get_test_case(db, test_case_id)
    items = cases.list_test_case_steps(db, user=current_user, test_case=test_case)
    return success_response(request, dump_plain_list(items))


@router.put("/test-cases/{test_case_id}/steps")
def put_test_case_steps(
    test_case_id: int,
    payload: list[StepWrite],
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Replace the full ordered test-case step list.

    Args:
        test_case_id: Target test-case id.
        payload: Ordered test-case step payload list.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    test_case = cases.get_test_case(db, test_case_id)
    items = cases.replace_test_case_steps(
        db,
        user=current_user,
        test_case=test_case,
        steps=[item.model_dump() for item in payload],
    )
    return success_response(request, dump_plain_list(items))


@router.get("/test-suites")
def list_test_suites(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    page, page_size = page_bounds(page, page_size)
    workspace_id = require_workspace_id(workspace_id)
    items, total = cases.list_test_suites(
        db, user=current_user, workspace_id=workspace_id, page=page, page_size=page_size
    )
    return paginated_response(
        request,
        dump_list(TestSuiteRead, items),
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/test-suites", status_code=201)
def create_test_suite(
    payload: TestSuiteCreate,
    request: Request,
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    workspace_id = require_workspace_id(workspace_id)
    suite = cases.create_test_suite(
        db,
        user=current_user,
        workspace_id=workspace_id,
        suite_code=payload.suite_code,
        suite_name=payload.suite_name,
        status=payload.status,
        description=payload.description,
    )
    return success_response(request, dump_model(TestSuiteRead, suite), status_code=201)


@router.get("/test-suites/{test_suite_id}")
def get_test_suite(
    test_suite_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    suite = cases.get_test_suite(db, test_suite_id)
    cases.require_workspace_access(db, current_user, suite.workspace_id)
    return success_response(request, dump_model(TestSuiteRead, suite))


@router.get("/test-suites/{test_suite_id}/execution-readiness")
def get_test_suite_execution_readiness(
    test_suite_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    suite = cases.get_test_suite(db, test_suite_id)
    readiness = execution_service.get_test_suite_execution_readiness(
        db,
        user=current_user,
        test_suite=suite,
    )
    return success_response(
        request,
        ExecutionReadinessSummaryRead.model_validate(readiness).model_dump(mode="json"),
    )


@router.patch("/test-suites/{test_suite_id}")
def patch_test_suite(
    test_suite_id: int,
    payload: TestSuiteUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    suite = cases.get_test_suite(db, test_suite_id)
    updated = cases.update_test_suite(
        db,
        user=current_user,
        suite=suite,
        suite_name=payload.suite_name,
        status=payload.status,
        description=payload.description,
    )
    return success_response(request, dump_model(TestSuiteRead, updated))


@router.get("/test-suites/{test_suite_id}/cases")
def list_suite_cases(
    test_suite_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    suite = cases.get_test_suite(db, test_suite_id)
    items = cases.list_suite_cases(db, user=current_user, suite=suite)
    return success_response(request, dump_plain_list(items))


@router.put("/test-suites/{test_suite_id}/cases")
def put_suite_cases(
    test_suite_id: int,
    payload: list[SuiteCaseWrite],
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Replace the full ordered case membership of a suite.

    Args:
        test_suite_id: Target suite id.
        payload: Ordered suite-case payload list.
        request: FastAPI request used for response wrapping.
        db: Active database session.
        current_user: Authenticated user.
    """
    suite = cases.get_test_suite(db, test_suite_id)
    items = cases.replace_suite_cases(
        db,
        user=current_user,
        suite=suite,
        items=[item.model_dump() for item in payload],
    )
    return success_response(request, dump_plain_list(items))
