from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.base import ORMModel


class TestRunRead(ORMModel):
    id: int
    workspace_id: int
    test_suite_id: int
    environment_profile_id: int
    device_profile_id: int | None = None
    trigger_source: str
    triggered_by: int | None = None
    idempotency_key: str | None = None
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_case_count: int
    passed_case_count: int
    failed_case_count: int
    error_case_count: int
    created_at: datetime
    updated_at: datetime


class TestRunCreate(BaseModel):
    test_suite_id: int
    environment_profile_id: int
    device_profile_id: int | None = None
    trigger_source: str = "manual"


class TestRunUpdate(BaseModel):
    status: str


class TestCaseRunRead(ORMModel):
    id: int
    test_run_id: int
    test_case_id: int
    sort_order: int
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    failure_reason_code: str | None = None
    failure_summary: str | None = None
    created_at: datetime


class StepResultRead(ORMModel):
    id: int
    case_run_id: int
    step_no: int
    step_type: str
    status: str
    score_value: float | None = None
    expected_media_object_id: int | None = None
    actual_media_object_id: int | None = None
    diff_media_object_id: int | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    parent_step_no: int | None = None
    branch_key: str | None = None
    branch_name: str | None = None
    branch_step_index: int | None = None
    repair_resource_type: Literal["template", "component", "test_case"] | None = None
    repair_resource_id: int | None = None
    repair_route_path: str | None = None
    repair_step_no: int | None = None
    created_at: datetime


class ReportArtifactRead(ORMModel):
    id: int
    report_id: int
    artifact_type: str
    media_object_id: int | None = None
    case_run_id: int | None = None
    step_result_id: int | None = None
    artifact_url: str | None = None
    created_at: datetime


class ReportSummaryCountsRead(BaseModel):
    total: int
    passed: int
    failed: int
    error: int
    cancelled: int


class ReportSummaryFailureRead(BaseModel):
    code: str | None = None
    summary: str | None = None


class ReportSummaryTimingRead(BaseModel):
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None


class ReportSummaryArtifactsRead(BaseModel):
    total: int
    by_type: dict[str, int]


class ReportSummaryRead(BaseModel):
    status: str
    counts: ReportSummaryCountsRead
    failure: ReportSummaryFailureRead | None = None
    timing: ReportSummaryTimingRead
    artifacts: ReportSummaryArtifactsRead
    total_case_count: int
    passed_case_count: int
    failed_case_count: int
    error_case_count: int
    cancelled_case_count: int
    message: str | None = None


class RunReportRead(ORMModel):
    id: int
    test_run_id: int
    summary_status: str
    summary_json: ReportSummaryRead
    generated_at: datetime
    created_at: datetime
