from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_workspace_header
from app.api.utils import dump_model, dump_list
from app.core.http import paginated_response, success_response
from app.db.session import get_db
from app.schemas.contracts import RunReportRead, StepResultRead, TestCaseRunRead, TestRunCreate, TestRunRead, TestRunUpdate
from app.services import execution
from app.services.helpers import page_bounds, require_workspace_id
from app.workers.execution import process_test_run

router = APIRouter(tags=["executions"])


@router.post("/test-runs", status_code=201)
def create_test_run(
    payload: TestRunCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    workspace_id = require_workspace_id(workspace_id)
    test_run = execution.create_test_run(
        db,
        user=current_user,
        workspace_id=workspace_id,
        test_suite_id=payload.test_suite_id,
        environment_profile_id=payload.environment_profile_id,
        device_profile_id=payload.device_profile_id,
        trigger_source=payload.trigger_source,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    background_tasks.add_task(process_test_run, test_run.id)
    return success_response(request, dump_model(TestRunRead, test_run), status_code=201)


@router.get("/test-runs")
def list_test_runs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    workspace_id: int | None = Depends(get_workspace_header),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    page, page_size = page_bounds(page, page_size)
    workspace_id = require_workspace_id(workspace_id)
    items, total = execution.list_test_runs(
        db,
        user=current_user,
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
        status=status,
    )
    return paginated_response(request, dump_list(TestRunRead, items), page=page, page_size=page_size, total=total)


@router.get("/test-runs/{test_run_id}")
def get_test_run(test_run_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    test_run = execution.get_test_run(db, test_run_id)
    execution.require_workspace_access(db, current_user, test_run.workspace_id)
    return success_response(request, dump_model(TestRunRead, test_run))


@router.patch("/test-runs/{test_run_id}")
def patch_test_run(test_run_id: int, payload: TestRunUpdate, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    test_run = execution.get_test_run(db, test_run_id)
    updated = execution.update_test_run_status(db, user=current_user, test_run=test_run, status=payload.status)
    return success_response(request, dump_model(TestRunRead, updated))


@router.get("/test-runs/{test_run_id}/case-runs")
def list_case_runs(test_run_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    test_run = execution.get_test_run(db, test_run_id)
    items = execution.list_case_runs(db, user=current_user, test_run=test_run)
    return success_response(request, dump_list(TestCaseRunRead, items))


@router.get("/case-runs/{case_run_id}")
def get_case_run(case_run_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    case_run = execution.get_case_run(db, case_run_id)
    test_run = execution.get_test_run(db, case_run.test_run_id)
    execution.require_workspace_access(db, current_user, test_run.workspace_id)
    return success_response(request, dump_model(TestCaseRunRead, case_run))


@router.get("/case-runs/{case_run_id}/step-results")
def list_step_results(case_run_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    case_run = execution.get_case_run(db, case_run_id)
    test_run = execution.get_test_run(db, case_run.test_run_id)
    execution.require_workspace_access(db, current_user, test_run.workspace_id)
    items = execution.list_step_results(db, case_run_id)
    return success_response(request, dump_list(StepResultRead, items))


@router.get("/reports/{report_id}")
def get_report(report_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    report = execution.get_report(db, report_id)
    test_run = execution.get_test_run(db, report.test_run_id)
    execution.require_workspace_access(db, current_user, test_run.workspace_id)
    return success_response(request, dump_model(RunReportRead, report))

