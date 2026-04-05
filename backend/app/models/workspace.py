from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    AuditMixin,
    Base,
    CreatedAtMixin,
    PK_TYPE,
    TimestampMixin,
    utc_now,
)


class Workspace(Base, AuditMixin):
    __tablename__ = "core_workspaces"
    __table_args__ = (
        UniqueConstraint(
            "workspace_code", "is_deleted", name="uk_core_workspaces_code"
        ),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_code: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("iam_users.id"), nullable=False
    )


class WorkspaceMember(Base, CreatedAtMixin):
    __tablename__ = "core_workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uk_core_workspace_members"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("core_workspaces.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("iam_users.id"), nullable=False)
    workspace_role: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    joined_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)


class EnvironmentProfile(Base, AuditMixin):
    __tablename__ = "cfg_environment_profiles"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "profile_name",
            "is_deleted",
            name="uk_cfg_environment_profiles",
        ),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("core_workspaces.id"), nullable=False
    )
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class EnvironmentVariable(Base, TimestampMixin):
    __tablename__ = "cfg_environment_variables"
    __table_args__ = (
        UniqueConstraint(
            "environment_profile_id", "var_key", name="uk_cfg_environment_variables"
        ),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    environment_profile_id: Mapped[int] = mapped_column(
        ForeignKey("cfg_environment_profiles.id"), nullable=False
    )
    var_key: Mapped[str] = mapped_column(String(128), nullable=False)
    var_value_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)


class DeviceProfile(Base, AuditMixin):
    __tablename__ = "cfg_device_profiles"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "profile_name", "is_deleted", name="uk_cfg_device_profiles"
        ),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("core_workspaces.id"), nullable=False
    )
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False)
    viewport_width: Mapped[int] = mapped_column(Integer, nullable=False)
    viewport_height: Mapped[int] = mapped_column(Integer, nullable=False)
    device_scale_factor: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
