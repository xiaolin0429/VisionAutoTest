from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.http import ApiError
from app.models import Component, ComponentStep, TestCase, TestCaseStep


@dataclass(slots=True)
class ResolvedExecutionStep:
    step_no: int
    step_type: str
    step_name: str
    template_id: int | None
    component_id: int | None
    payload_json: dict
    timeout_ms: int
    retry_times: int
    parent_step_no: int | None = None
    branch_key: str | None = None
    branch_name: str | None = None
    branch_step_index: int | None = None


def build_execution_steps(
    db: Session, *, workspace_id: int, test_case_id: int
) -> list[ResolvedExecutionStep]:
    """Resolve a test case into the flattened execution step sequence used by the worker.

    Args:
        db: Active database session.
        workspace_id: Workspace scope used to validate the case and referenced components.
        test_case_id: Test case whose steps should be expanded for execution.

    Returns:
        A flattened step list with contiguous ``step_no`` values.

    Raises:
        ApiError: If the test case does not exist in the given workspace.
    """
    test_case = db.get(TestCase, test_case_id)
    if (
        test_case is None
        or test_case.workspace_id != workspace_id
        or test_case.is_deleted
    ):
        raise ApiError(
            code="TEST_CASE_NOT_FOUND", message="Test case not found.", status_code=404
        )

    case_steps = db.scalars(
        select(TestCaseStep)
        .where(TestCaseStep.test_case_id == test_case_id)
        .order_by(TestCaseStep.step_no.asc())
    ).all()
    resolved_steps: list[ResolvedExecutionStep] = []

    for case_step in case_steps:
        if case_step.step_type == "conditional_branch":
            resolved_steps.extend(build_conditional_branch_steps(case_step=case_step))
            continue
        if case_step.step_type != "component_call":
            resolved_steps.append(
                ResolvedExecutionStep(
                    step_no=0,
                    step_type=case_step.step_type,
                    step_name=case_step.step_name,
                    template_id=case_step.template_id,
                    component_id=case_step.component_id,
                    payload_json=case_step.payload_json or {},
                    timeout_ms=case_step.timeout_ms,
                    retry_times=case_step.retry_times,
                )
            )
            continue

        component = get_component_in_workspace(
            db, workspace_id=workspace_id, component_id=case_step.component_id
        )
        component_steps = db.scalars(
            select(ComponentStep)
            .where(ComponentStep.component_id == component.id)
            .order_by(ComponentStep.step_no.asc())
        ).all()
        for component_step in component_steps:
            resolved_steps.append(
                ResolvedExecutionStep(
                    step_no=0,
                    step_type=component_step.step_type,
                    step_name=component_step.step_name,
                    template_id=component_step.template_id,
                    component_id=component.id,
                    payload_json=component_step.payload_json or {},
                    timeout_ms=case_step.timeout_ms,
                    retry_times=case_step.retry_times,
                )
            )

    for index, step in enumerate(resolved_steps, start=1):
        step.step_no = index
    return resolved_steps


def build_conditional_branch_steps(
    *, case_step: TestCaseStep
) -> list[ResolvedExecutionStep]:
    """Expand a conditional branch step into its parent node plus branch child steps.

    Args:
        case_step: The persisted ``conditional_branch`` test case step.

    Returns:
        A list containing the branch parent step followed by all declared child steps.
    """
    payload = case_step.payload_json or {}
    steps: list[ResolvedExecutionStep] = [
        ResolvedExecutionStep(
            step_no=0,
            step_type="conditional_branch",
            step_name=case_step.step_name,
            template_id=None,
            component_id=None,
            payload_json=payload,
            timeout_ms=case_step.timeout_ms,
            retry_times=case_step.retry_times,
        )
    ]

    branches = (
        payload.get("branches") if isinstance(payload.get("branches"), list) else []
    )
    for branch in branches:
        if not isinstance(branch, dict):
            continue
        branch_key = (
            branch.get("branch_key")
            if isinstance(branch.get("branch_key"), str)
            else None
        )
        branch_name = (
            branch.get("branch_name")
            if isinstance(branch.get("branch_name"), str)
            else None
        )
        branch_steps = (
            branch.get("steps") if isinstance(branch.get("steps"), list) else []
        )
        for branch_step_index, branch_step in enumerate(branch_steps, start=1):
            if not isinstance(branch_step, dict):
                continue
            steps.append(
                ResolvedExecutionStep(
                    step_no=0,
                    step_type=str(branch_step.get("step_type") or "wait"),
                    step_name=str(
                        branch_step.get("step_name")
                        or f"Branch step {branch_step_index}"
                    ),
                    template_id=branch_step.get("template_id")
                    if isinstance(branch_step.get("template_id"), int)
                    else None,
                    component_id=None,
                    payload_json=branch_step.get("payload_json") or {},
                    timeout_ms=int(
                        branch_step.get("timeout_ms") or case_step.timeout_ms
                    ),
                    retry_times=int(
                        branch_step.get("retry_times") or case_step.retry_times
                    ),
                    parent_step_no=case_step.step_no,
                    branch_key=branch_key,
                    branch_name=branch_name,
                    branch_step_index=branch_step_index,
                )
            )

    else_branch = payload.get("else_branch")
    if isinstance(else_branch, dict) and else_branch.get("enabled") is True:
        branch_name = (
            else_branch.get("branch_name")
            if isinstance(else_branch.get("branch_name"), str)
            else "默认分支"
        )
        branch_steps = (
            else_branch.get("steps")
            if isinstance(else_branch.get("steps"), list)
            else []
        )
        for branch_step_index, branch_step in enumerate(branch_steps, start=1):
            if not isinstance(branch_step, dict):
                continue
            steps.append(
                ResolvedExecutionStep(
                    step_no=0,
                    step_type=str(branch_step.get("step_type") or "wait"),
                    step_name=str(
                        branch_step.get("step_name") or f"Else step {branch_step_index}"
                    ),
                    template_id=branch_step.get("template_id")
                    if isinstance(branch_step.get("template_id"), int)
                    else None,
                    component_id=None,
                    payload_json=branch_step.get("payload_json") or {},
                    timeout_ms=int(
                        branch_step.get("timeout_ms") or case_step.timeout_ms
                    ),
                    retry_times=int(
                        branch_step.get("retry_times") or case_step.retry_times
                    ),
                    parent_step_no=case_step.step_no,
                    branch_key="else",
                    branch_name=branch_name,
                    branch_step_index=branch_step_index,
                )
            )
    return steps


def get_component_in_workspace(
    db: Session, *, workspace_id: int, component_id: int | None
) -> Component:
    """Load a component while enforcing workspace ownership and soft-delete rules.

    Args:
        db: Active database session.
        workspace_id: Workspace that the calling test case belongs to.
        component_id: Referenced component id from a ``component_call`` step.

    Returns:
        The resolved component entity.

    Raises:
        ApiError: If the component is missing or not accessible in the workspace.
    """
    if component_id is None:
        raise ApiError(
            code="COMPONENT_NOT_FOUND", message="Component not found.", status_code=404
        )
    component = db.get(Component, component_id)
    if (
        component is None
        or component.workspace_id != workspace_id
        or component.is_deleted
    ):
        raise ApiError(
            code="COMPONENT_NOT_FOUND", message="Component not found.", status_code=404
        )
    return component
