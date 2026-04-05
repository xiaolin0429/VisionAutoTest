from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, CreatedAtMixin, PK_TYPE, TimestampMixin


class User(Base, AuditMixin):
    __tablename__ = "iam_users"
    __table_args__ = (
        UniqueConstraint("username", "is_deleted", name="uk_iam_users_username"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class UserSession(Base, TimestampMixin):
    __tablename__ = "iam_sessions"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("iam_users.id"), nullable=False)
    session_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    access_token_jti: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    client_type: Mapped[str] = mapped_column(String(32), nullable=False, default="web")
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RefreshToken(Base, CreatedAtMixin):
    __tablename__ = "iam_refresh_tokens"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("iam_sessions.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
