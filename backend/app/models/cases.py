from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, CreatedAtMixin, PK_TYPE, TimestampMixin


class Component(Base, AuditMixin):
    __tablename__ = "case_components"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "component_code", "is_deleted", name="uk_case_components"
        ),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("core_workspaces.id"), nullable=False
    )
    component_code: Mapped[str] = mapped_column(String(64), nullable=False)
    component_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ComponentStep(Base, TimestampMixin):
    __tablename__ = "case_component_steps"
    __table_args__ = (
        UniqueConstraint("component_id", "step_no", name="uk_case_component_steps"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    component_id: Mapped[int] = mapped_column(
        ForeignKey("case_components.id"), nullable=False
    )
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(32), nullable=False)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("asset_templates.id"), nullable=True
    )
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=15000, nullable=False)
    retry_times: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class TestCase(Base, AuditMixin):
    __tablename__ = "case_test_cases"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "case_code", "is_deleted", name="uk_case_test_cases"
        ),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("core_workspaces.id"), nullable=False
    )
    case_code: Mapped[str] = mapped_column(String(64), nullable=False)
    case_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="p2")
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)


class TestCaseStep(Base, TimestampMixin):
    __tablename__ = "case_test_case_steps"
    __table_args__ = (
        UniqueConstraint("test_case_id", "step_no", name="uk_case_test_case_steps"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    test_case_id: Mapped[int] = mapped_column(
        ForeignKey("case_test_cases.id"), nullable=False
    )
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(32), nullable=False)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    component_id: Mapped[int | None] = mapped_column(
        ForeignKey("case_components.id"), nullable=True
    )
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("asset_templates.id"), nullable=True
    )
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=15000, nullable=False)
    retry_times: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class TestSuite(Base, AuditMixin):
    __tablename__ = "case_test_suites"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "suite_code", "is_deleted", name="uk_case_test_suites"
        ),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("core_workspaces.id"), nullable=False
    )
    suite_code: Mapped[str] = mapped_column(String(64), nullable=False)
    suite_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)


class SuiteCase(Base, CreatedAtMixin):
    __tablename__ = "case_suite_cases"
    __table_args__ = (
        UniqueConstraint("test_suite_id", "test_case_id", name="uk_case_suite_cases"),
        UniqueConstraint("test_suite_id", "sort_order", name="uk_case_suite_sort"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    test_suite_id: Mapped[int] = mapped_column(
        ForeignKey("case_test_suites.id"), nullable=False
    )
    test_case_id: Mapped[int] = mapped_column(
        ForeignKey("case_test_cases.id"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
