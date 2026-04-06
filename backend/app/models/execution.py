from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, PK_TYPE, TimestampMixin, utc_now


class TestRun(Base, TimestampMixin):
    __tablename__ = "exec_test_runs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "idempotency_key", name="uk_exec_test_runs_idempotency"
        ),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("core_workspaces.id"), nullable=False
    )
    test_suite_id: Mapped[int] = mapped_column(
        ForeignKey("case_test_suites.id"), nullable=False
    )
    environment_profile_id: Mapped[int] = mapped_column(
        ForeignKey("cfg_environment_profiles.id"), nullable=False
    )
    device_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("cfg_device_profiles.id"), nullable=True
    )
    trigger_source: Mapped[str] = mapped_column(String(32), nullable=False)
    triggered_by: Mapped[int | None] = mapped_column(
        ForeignKey("iam_users.id"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class TestCaseRun(Base, CreatedAtMixin):
    __tablename__ = "exec_test_case_runs"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    test_run_id: Mapped[int] = mapped_column(
        ForeignKey("exec_test_runs.id"), nullable=False
    )
    test_case_id: Mapped[int] = mapped_column(
        ForeignKey("case_test_cases.id"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    failure_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)


class StepResult(Base, CreatedAtMixin):
    __tablename__ = "exec_step_results"
    __table_args__ = (
        UniqueConstraint("case_run_id", "step_no", name="uk_exec_step_results"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    case_run_id: Mapped[int] = mapped_column(
        ForeignKey("exec_test_case_runs.id"), nullable=False
    )
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    score_value: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    expected_media_object_id: Mapped[int | None] = mapped_column(
        ForeignKey("asset_media_objects.id"), nullable=True
    )
    actual_media_object_id: Mapped[int | None] = mapped_column(
        ForeignKey("asset_media_objects.id"), nullable=True
    )
    diff_media_object_id: Mapped[int | None] = mapped_column(
        ForeignKey("asset_media_objects.id"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    parent_step_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    branch_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    branch_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    branch_step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)


class RunReport(Base, CreatedAtMixin):
    __tablename__ = "report_run_reports"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    test_run_id: Mapped[int] = mapped_column(
        ForeignKey("exec_test_runs.id"), nullable=False, unique=True
    )
    summary_status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ReportArtifact(Base, CreatedAtMixin):
    __tablename__ = "report_artifacts"
    __table_args__ = (
        Index("ix_report_artifacts_report_artifact_type", "report_id", "artifact_type"),
        Index("ix_report_artifacts_report_case_run", "report_id", "case_run_id"),
        Index("ix_report_artifacts_report_step_result", "report_id", "step_result_id"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("report_run_reports.id"), nullable=False
    )
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    media_object_id: Mapped[int | None] = mapped_column(
        ForeignKey("asset_media_objects.id"), nullable=True
    )
    case_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("exec_test_case_runs.id"), nullable=True
    )
    step_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("exec_step_results.id"), nullable=True
    )
    artifact_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
