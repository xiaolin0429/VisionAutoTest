from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel

ComponentStatus = Literal["draft", "published", "archived"]
TestCaseStatus = Literal["draft", "published", "archived"]
TestSuiteStatus = Literal["draft", "active", "archived"]


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
