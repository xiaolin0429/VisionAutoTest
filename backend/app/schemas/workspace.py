from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class WorkspaceRead(ORMModel):
    id: int
    workspace_code: str
    workspace_name: str
    description: str | None = None
    status: str
    owner_user_id: int
    created_at: datetime
    updated_at: datetime


class ExecutionReadinessIssueRead(BaseModel):
    code: str
    message: str
    resource_type: str
    resource_id: int | None = None
    resource_name: str | None = None
    route_path: str | None = None


class ExecutionReadinessSummaryRead(BaseModel):
    scope: Literal["workspace", "test_suite"]
    status: Literal["ready", "blocked"]
    workspace_id: int
    test_suite_id: int | None = None
    active_environment_count: int = 0
    active_test_suite_count: int = 0
    blocking_issue_count: int = 0
    issues: list[ExecutionReadinessIssueRead] = Field(default_factory=list)


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
