from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ComponentStatus = Literal["draft", "published", "archived"]
TestCaseStatus = Literal["draft", "published", "archived"]
TestSuiteStatus = Literal["draft", "active", "archived"]
TemplateStatus = Literal["draft", "published", "archived"]
TemplateMatchStrategy = Literal["template", "ocr"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRead(ORMModel):
    id: int
    username: str
    display_name: str
    email: str | None = None
    mobile: str | None = None
    status: str
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    username: str
    display_name: str
    password: str
    email: str | None = None
    mobile: str | None = None
    status: str = "active"


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    mobile: str | None = None
    status: str | None = None


class SessionCreate(BaseModel):
    username: str
    password: str


class SessionRefreshCreate(BaseModel):
    refresh_token: str


class WorkspaceRead(ORMModel):
    id: int
    workspace_code: str
    workspace_name: str
    description: str | None = None
    status: str
    owner_user_id: int
    created_at: datetime
    updated_at: datetime


class WorkspaceCreate(BaseModel):
    workspace_code: str
    workspace_name: str
    description: str | None = None
    status: str = "active"


class WorkspaceUpdate(BaseModel):
    workspace_name: str | None = None
    description: str | None = None
    status: str | None = None


class WorkspaceMemberRead(ORMModel):
    id: int
    workspace_id: int
    user_id: int
    workspace_role: str
    status: str
    joined_at: datetime
    created_at: datetime


class WorkspaceMemberCreate(BaseModel):
    user_id: int
    workspace_role: str = "workspace_member"


class WorkspaceMemberUpdate(BaseModel):
    workspace_role: str | None = None
    status: str | None = None


class EnvironmentProfileRead(ORMModel):
    id: int
    workspace_id: int
    profile_name: str
    base_url: str
    description: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class EnvironmentProfileCreate(BaseModel):
    profile_name: str
    base_url: str
    description: str | None = None
    status: str = "active"


class EnvironmentProfileUpdate(BaseModel):
    profile_name: str | None = None
    base_url: str | None = None
    description: str | None = None
    status: str | None = None


class EnvironmentVariableRead(ORMModel):
    id: int
    environment_profile_id: int
    var_key: str
    is_secret: bool
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    display_value: str | None = None


class EnvironmentVariableCreate(BaseModel):
    var_key: str
    value: str
    is_secret: bool = False
    description: str | None = None


class EnvironmentVariableUpdate(BaseModel):
    value: str | None = None
    is_secret: bool | None = None
    description: str | None = None


class DeviceProfileRead(ORMModel):
    id: int
    workspace_id: int
    profile_name: str
    device_type: str
    viewport_width: int
    viewport_height: int
    device_scale_factor: float
    user_agent: str | None = None
    is_default: bool
    created_at: datetime
    updated_at: datetime


class DeviceProfileCreate(BaseModel):
    profile_name: str
    device_type: str
    viewport_width: int
    viewport_height: int
    device_scale_factor: float
    user_agent: str | None = None
    is_default: bool = False


class DeviceProfileUpdate(BaseModel):
    profile_name: str | None = None
    device_type: str | None = None
    viewport_width: int | None = None
    viewport_height: int | None = None
    device_scale_factor: float | None = None
    user_agent: str | None = None
    is_default: bool | None = None


class MediaObjectRead(ORMModel):
    id: int
    workspace_id: int
    storage_type: str
    bucket_name: str | None = None
    object_key: str
    file_name: str
    mime_type: str
    file_size: int
    checksum_sha256: str
    status: str
    usage: str
    remark: str | None = None
    created_at: datetime


class MediaObjectUpdate(BaseModel):
    status: str | None = None
    remark: str | None = None


class TemplateRead(ORMModel):
    id: int
    workspace_id: int
    template_code: str
    template_name: str
    template_type: str
    match_strategy: TemplateMatchStrategy
    threshold_value: float
    status: TemplateStatus
    current_baseline_revision_id: int | None = None
    created_at: datetime
    updated_at: datetime


class TemplateCreate(BaseModel):
    template_code: str
    template_name: str
    template_type: str
    match_strategy: str = "template"
    threshold_value: float = 0.95
    status: str = "draft"
    original_media_object_id: int


class TemplateUpdate(BaseModel):
    template_name: str | None = None
    template_type: str | None = None
    match_strategy: str | None = None
    threshold_value: float | None = None
    status: str | None = None


class BaselineRevisionRead(ORMModel):
    id: int
    template_id: int
    revision_no: int
    media_object_id: int
    source_type: str
    source_report_id: int | None = None
    source_case_run_id: int | None = None
    source_step_result_id: int | None = None
    is_current: bool
    remark: str | None = None
    created_at: datetime


class BaselineRevisionCreate(BaseModel):
    media_object_id: int
    source_type: str = "manual"
    source_report_id: int | None = None
    source_case_run_id: int | None = None
    source_step_result_id: int | None = None
    remark: str | None = None
    is_current: bool = True


class OCRPointRead(BaseModel):
    x: int
    y: int


class OCRPixelRectRead(BaseModel):
    x: int
    y: int
    width: int
    height: int


class OCRRatioRectRead(BaseModel):
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float


class TemplateOCRBlockRead(BaseModel):
    order_no: int
    text: str
    confidence: float
    polygon_points: list[OCRPointRead]
    pixel_rect: OCRPixelRectRead
    ratio_rect: OCRRatioRectRead


class TemplateOCRResultRead(BaseModel):
    id: int | None = None
    template_id: int
    baseline_revision_id: int
    source_media_object_id: int
    status: str
    engine_name: str
    image_width: int | None = None
    image_height: int | None = None
    blocks: list[TemplateOCRBlockRead] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MaskRegionRead(ORMModel):
    id: int
    template_id: int
    region_name: str
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float
    sort_order: int
    created_at: datetime
    updated_at: datetime


class MaskRegionCreate(BaseModel):
    region_name: str
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float
    sort_order: int = 1


class MaskRegionUpdate(BaseModel):
    region_name: str | None = None
    x_ratio: float | None = None
    y_ratio: float | None = None
    width_ratio: float | None = None
    height_ratio: float | None = None
    sort_order: int | None = None


class MaskRegionPreviewWrite(BaseModel):
    name: str | None = None
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float
    sort_order: int | None = None


class MaskRegionPreviewRead(BaseModel):
    name: str
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float
    sort_order: int


class TemplatePreviewCreate(BaseModel):
    mask_regions: list[MaskRegionPreviewWrite] | None = None


class TemplatePreviewRead(BaseModel):
    template_id: int
    baseline_revision_id: int
    source_media_object_id: int
    image_width: int
    image_height: int
    overlay_media_object_id: int
    overlay_content_url: str
    processed_media_object_id: int
    processed_content_url: str
    mask_regions: list[MaskRegionPreviewRead]


class StepWrite(BaseModel):
    step_no: int
    step_type: str
    step_name: str
    template_id: int | None = None
    component_id: int | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = 15000
    retry_times: int = 0


class ComponentRead(ORMModel):
    id: int
    workspace_id: int
    component_code: str
    component_name: str
    status: str
    description: str | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ComponentCreate(BaseModel):
    component_code: str
    component_name: str
    status: ComponentStatus = "draft"
    description: str | None = None


class ComponentUpdate(BaseModel):
    component_name: str | None = None
    status: ComponentStatus | None = None
    description: str | None = None


class TestCaseRead(ORMModel):
    id: int
    workspace_id: int
    case_code: str
    case_name: str
    status: str
    priority: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class TestCaseCreate(BaseModel):
    case_code: str
    case_name: str
    status: TestCaseStatus = "draft"
    priority: str = "p2"
    description: str | None = None


class TestCaseUpdate(BaseModel):
    case_name: str | None = None
    status: TestCaseStatus | None = None
    priority: str | None = None
    description: str | None = None


class TestSuiteRead(ORMModel):
    id: int
    workspace_id: int
    suite_code: str
    suite_name: str
    status: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class TestSuiteCreate(BaseModel):
    suite_code: str
    suite_name: str
    status: TestSuiteStatus = "draft"
    description: str | None = None


class TestSuiteUpdate(BaseModel):
    suite_name: str | None = None
    status: TestSuiteStatus | None = None
    description: str | None = None


class SuiteCaseWrite(BaseModel):
    test_case_id: int
    sort_order: int


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
