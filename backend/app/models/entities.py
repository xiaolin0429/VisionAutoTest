from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)

PK_TYPE = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    metadata = metadata


class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by: Mapped[int | None] = mapped_column(PK_TYPE, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    updated_by: Mapped[int | None] = mapped_column(PK_TYPE, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class User(Base, AuditMixin):
    __tablename__ = "iam_users"
    __table_args__ = (UniqueConstraint("username", "is_deleted", name="uk_iam_users_username"),)

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSession(Base, TimestampMixin):
    __tablename__ = "iam_sessions"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("iam_users.id"), nullable=False)
    session_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    access_token_jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    client_type: Mapped[str] = mapped_column(String(32), nullable=False, default="web")
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RefreshToken(Base, CreatedAtMixin):
    __tablename__ = "iam_refresh_tokens"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("iam_sessions.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Workspace(Base, AuditMixin):
    __tablename__ = "core_workspaces"
    __table_args__ = (UniqueConstraint("workspace_code", "is_deleted", name="uk_core_workspaces_code"),)

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_code: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("iam_users.id"), nullable=False)


class WorkspaceMember(Base, CreatedAtMixin):
    __tablename__ = "core_workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uk_core_workspace_members"),)

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("core_workspaces.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("iam_users.id"), nullable=False)
    workspace_role: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class EnvironmentProfile(Base, AuditMixin):
    __tablename__ = "cfg_environment_profiles"
    __table_args__ = (
        UniqueConstraint("workspace_id", "profile_name", "is_deleted", name="uk_cfg_environment_profiles"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("core_workspaces.id"), nullable=False)
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class EnvironmentVariable(Base, TimestampMixin):
    __tablename__ = "cfg_environment_variables"
    __table_args__ = (
        UniqueConstraint("environment_profile_id", "var_key", name="uk_cfg_environment_variables"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    environment_profile_id: Mapped[int] = mapped_column(
        ForeignKey("cfg_environment_profiles.id"),
        nullable=False,
    )
    var_key: Mapped[str] = mapped_column(String(128), nullable=False)
    var_value_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)


class DeviceProfile(Base, AuditMixin):
    __tablename__ = "cfg_device_profiles"
    __table_args__ = (
        UniqueConstraint("workspace_id", "profile_name", "is_deleted", name="uk_cfg_device_profiles"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("core_workspaces.id"), nullable=False)
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False)
    viewport_width: Mapped[int] = mapped_column(Integer, nullable=False)
    viewport_height: Mapped[int] = mapped_column(Integer, nullable=False)
    device_scale_factor: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MediaObject(Base):
    __tablename__ = "asset_media_objects"
    __table_args__ = (
        UniqueConstraint("checksum_sha256", "file_size", "workspace_id", name="uk_asset_media_objects_checksum"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("core_workspaces.id"), nullable=False)
    storage_type: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    bucket_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    object_key: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    usage: Mapped[str] = mapped_column(String(32), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by: Mapped[int | None] = mapped_column(PK_TYPE, nullable=True)


class Template(Base, AuditMixin):
    __tablename__ = "asset_templates"
    __table_args__ = (
        UniqueConstraint("workspace_id", "template_code", "is_deleted", name="uk_asset_templates"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("core_workspaces.id"), nullable=False)
    template_code: Mapped[str] = mapped_column(String(64), nullable=False)
    template_name: Mapped[str] = mapped_column(String(128), nullable=False)
    template_type: Mapped[str] = mapped_column(String(32), nullable=False)
    match_strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    current_baseline_revision_id: Mapped[int | None] = mapped_column(PK_TYPE, nullable=True)


class TemplateMaskRegion(Base, TimestampMixin):
    __tablename__ = "asset_template_mask_regions"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("asset_templates.id"), nullable=False)
    region_name: Mapped[str] = mapped_column(String(128), nullable=False)
    x_ratio: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    y_ratio: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    width_ratio: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    height_ratio: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class BaselineRevision(Base, CreatedAtMixin):
    __tablename__ = "asset_baseline_revisions"
    __table_args__ = (
        UniqueConstraint("template_id", "revision_no", name="uk_asset_baseline_revisions"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("asset_templates.id"), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    media_object_id: Mapped[int] = mapped_column(ForeignKey("asset_media_objects.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_report_id: Mapped[int | None] = mapped_column(ForeignKey("report_run_reports.id"), nullable=True)
    source_case_run_id: Mapped[int | None] = mapped_column(ForeignKey("exec_test_case_runs.id"), nullable=True)
    source_step_result_id: Mapped[int | None] = mapped_column(ForeignKey("exec_step_results.id"), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[int | None] = mapped_column(PK_TYPE, nullable=True)


class TemplateOCRResult(Base, TimestampMixin):
    __tablename__ = "asset_template_ocr_results"
    __table_args__ = (
        UniqueConstraint("template_id", "baseline_revision_id", name="uk_asset_template_ocr_results"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("asset_templates.id"), nullable=False)
    baseline_revision_id: Mapped[int] = mapped_column(ForeignKey("asset_baseline_revisions.id"), nullable=False)
    source_media_object_id: Mapped[int] = mapped_column(ForeignKey("asset_media_objects.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_name: Mapped[str] = mapped_column(String(64), nullable=False)
    image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class Component(Base, AuditMixin):
    __tablename__ = "case_components"
    __table_args__ = (
        UniqueConstraint("workspace_id", "component_code", "is_deleted", name="uk_case_components"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("core_workspaces.id"), nullable=False)
    component_code: Mapped[str] = mapped_column(String(64), nullable=False)
    component_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ComponentStep(Base, TimestampMixin):
    __tablename__ = "case_component_steps"
    __table_args__ = (UniqueConstraint("component_id", "step_no", name="uk_case_component_steps"),)

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    component_id: Mapped[int] = mapped_column(ForeignKey("case_components.id"), nullable=False)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(32), nullable=False)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("asset_templates.id"), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=15000, nullable=False)
    retry_times: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class TestCase(Base, AuditMixin):
    __tablename__ = "case_test_cases"
    __table_args__ = (
        UniqueConstraint("workspace_id", "case_code", "is_deleted", name="uk_case_test_cases"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("core_workspaces.id"), nullable=False)
    case_code: Mapped[str] = mapped_column(String(64), nullable=False)
    case_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="p2")
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)


class TestCaseStep(Base, TimestampMixin):
    __tablename__ = "case_test_case_steps"
    __table_args__ = (UniqueConstraint("test_case_id", "step_no", name="uk_case_test_case_steps"),)

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("case_test_cases.id"), nullable=False)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(32), nullable=False)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    component_id: Mapped[int | None] = mapped_column(ForeignKey("case_components.id"), nullable=True)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("asset_templates.id"), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=15000, nullable=False)
    retry_times: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class TestSuite(Base, AuditMixin):
    __tablename__ = "case_test_suites"
    __table_args__ = (
        UniqueConstraint("workspace_id", "suite_code", "is_deleted", name="uk_case_test_suites"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("core_workspaces.id"), nullable=False)
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
    test_suite_id: Mapped[int] = mapped_column(ForeignKey("case_test_suites.id"), nullable=False)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("case_test_cases.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class TestRun(Base, TimestampMixin):
    __tablename__ = "exec_test_runs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "idempotency_key", name="uk_exec_test_runs_idempotency"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("core_workspaces.id"), nullable=False)
    test_suite_id: Mapped[int] = mapped_column(ForeignKey("case_test_suites.id"), nullable=False)
    environment_profile_id: Mapped[int] = mapped_column(ForeignKey("cfg_environment_profiles.id"), nullable=False)
    device_profile_id: Mapped[int | None] = mapped_column(ForeignKey("cfg_device_profiles.id"), nullable=True)
    trigger_source: Mapped[str] = mapped_column(String(32), nullable=False)
    triggered_by: Mapped[int | None] = mapped_column(ForeignKey("iam_users.id"), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class TestCaseRun(Base, CreatedAtMixin):
    __tablename__ = "exec_test_case_runs"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    test_run_id: Mapped[int] = mapped_column(ForeignKey("exec_test_runs.id"), nullable=False)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("case_test_cases.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    failure_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)


class StepResult(Base, CreatedAtMixin):
    __tablename__ = "exec_step_results"
    __table_args__ = (UniqueConstraint("case_run_id", "step_no", name="uk_exec_step_results"),)

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    case_run_id: Mapped[int] = mapped_column(ForeignKey("exec_test_case_runs.id"), nullable=False)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    score_value: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    expected_media_object_id: Mapped[int | None] = mapped_column(ForeignKey("asset_media_objects.id"), nullable=True)
    actual_media_object_id: Mapped[int | None] = mapped_column(ForeignKey("asset_media_objects.id"), nullable=True)
    diff_media_object_id: Mapped[int | None] = mapped_column(ForeignKey("asset_media_objects.id"), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class RunReport(Base, CreatedAtMixin):
    __tablename__ = "report_run_reports"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    test_run_id: Mapped[int] = mapped_column(ForeignKey("exec_test_runs.id"), nullable=False, unique=True)
    summary_status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ReportArtifact(Base, CreatedAtMixin):
    __tablename__ = "report_artifacts"
    __table_args__ = (
        Index("ix_report_artifacts_report_artifact_type", "report_id", "artifact_type"),
        Index("ix_report_artifacts_report_case_run", "report_id", "case_run_id"),
        Index("ix_report_artifacts_report_step_result", "report_id", "step_result_id"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("report_run_reports.id"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    media_object_id: Mapped[int | None] = mapped_column(ForeignKey("asset_media_objects.id"), nullable=True)
    case_run_id: Mapped[int | None] = mapped_column(ForeignKey("exec_test_case_runs.id"), nullable=True)
    step_result_id: Mapped[int | None] = mapped_column(ForeignKey("exec_step_results.id"), nullable=True)
    artifact_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
