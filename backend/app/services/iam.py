from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.http import ApiError
from app.core.security import (
    decode_access_token,
    generate_access_token,
    generate_token,
    hash_secret,
    is_token_expired_error,
    is_token_invalid_error,
    verify_secret,
)
from app.models import RefreshToken, User, UserSession, utc_now
from app.services.helpers import apply_keyword, count_total

settings = get_settings()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def create_session(db: Session, username: str, password: str, *, client_ip: str | None, user_agent: str | None) -> dict:
    user = db.scalar(select(User).where(User.username == username, User.is_deleted.is_(False)))
    if user is None or not verify_secret(password, user.password_hash):
        raise ApiError(code="INVALID_CREDENTIALS", message="Username or password is invalid.", status_code=401)
    if user.status != "active":
        raise ApiError(code="USER_DISABLED", message="User is not active.", status_code=403)

    now = utc_now()
    session_code = generate_token("ses")
    access_token_jti = generate_token("jti")[:64]
    access_token = generate_access_token(
        subject=user.id,
        session_id=session_code,
        token_jti=access_token_jti,
        expires_in_seconds=settings.access_token_ttl_seconds,
    )
    refresh_token = generate_token("rfr")
    session = UserSession(
        user_id=user.id,
        session_code=session_code,
        access_token_jti=access_token_jti,
        client_type="web",
        client_ip=client_ip,
        user_agent=user_agent,
        status="active",
        last_seen_at=now,
        expires_at=now + timedelta(seconds=settings.access_token_ttl_seconds),
    )
    db.add(session)
    db.flush()
    db.add(
        RefreshToken(
            session_id=session.id,
            token_hash=hash_secret(refresh_token),
            status="active",
            expires_at=now + timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
    )
    user.last_login_at = now
    db.commit()
    db.refresh(session)
    db.refresh(user)
    return {
        "session_id": session.session_code,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": settings.access_token_ttl_seconds,
        "token_type": "Bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
        },
    }


def refresh_session(db: Session, refresh_token: str) -> dict:
    token_hash = hash_secret(refresh_token)
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if token is None or token.status != "active" or _as_utc(token.expires_at) <= utc_now():
        raise ApiError(code="REFRESH_TOKEN_INVALID", message="Refresh token is invalid.", status_code=401)

    session = db.get(UserSession, token.session_id)
    if session is None or session.status != "active":
        raise ApiError(code="SESSION_NOT_FOUND", message="Session not found.", status_code=404)

    now = utc_now()
    token.status = "used"
    token.consumed_at = now

    new_access_token_jti = generate_token("jti")[:64]
    new_access_token = generate_access_token(
        subject=session.user_id,
        session_id=session.session_code,
        token_jti=new_access_token_jti,
        expires_in_seconds=settings.access_token_ttl_seconds,
    )
    new_refresh_token = generate_token("rfr")
    session.access_token_jti = new_access_token_jti
    session.expires_at = now + timedelta(seconds=settings.access_token_ttl_seconds)
    session.last_seen_at = now
    db.add(
        RefreshToken(
            session_id=session.id,
            token_hash=hash_secret(new_refresh_token),
            status="active",
            expires_at=now + timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
    )
    db.commit()
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "expires_in": settings.access_token_ttl_seconds,
        "token_type": "Bearer",
    }


def get_current_user_by_token(db: Session, token: str) -> tuple[User, UserSession]:
    try:
        claims = decode_access_token(token)
    except Exception as exc:  # noqa: BLE001
        if is_token_expired_error(exc):
            raise ApiError(code="TOKEN_EXPIRED", message="Access token is expired.", status_code=401) from exc
        if is_token_invalid_error(exc):
            raise ApiError(code="TOKEN_REVOKED", message="Access token is invalid.", status_code=401) from exc
        raise

    session_id = claims.get("sid")
    token_jti = claims.get("jti")
    subject = claims.get("sub")
    if not isinstance(session_id, str) or not session_id or not isinstance(token_jti, str) or not token_jti:
        raise ApiError(code="TOKEN_REVOKED", message="Access token is invalid.", status_code=401)

    session = db.scalar(
        select(UserSession).where(
            UserSession.session_code == session_id,
            UserSession.access_token_jti == token_jti,
            UserSession.status == "active",
        )
    )
    if session is None:
        raise ApiError(code="TOKEN_REVOKED", message="Access token is invalid.", status_code=401)
    if _as_utc(session.expires_at) <= utc_now():
        session.status = "expired"
        db.commit()
        raise ApiError(code="TOKEN_EXPIRED", message="Access token is expired.", status_code=401)
    user = db.get(User, session.user_id)
    if user is None or user.is_deleted or str(user.id) != str(subject):
        raise ApiError(code="USER_NOT_FOUND", message="User not found.", status_code=404)
    session.last_seen_at = utc_now()
    db.commit()
    return user, session


def revoke_current_session(db: Session, session: UserSession) -> None:
    now = utc_now()
    session.status = "revoked"
    session.revoked_at = now
    tokens = db.scalars(select(RefreshToken).where(RefreshToken.session_id == session.id, RefreshToken.status == "active")).all()
    for token in tokens:
        token.status = "revoked"
        token.revoked_at = now
    db.commit()


def list_users(db: Session, *, page: int, page_size: int, status: str | None, keyword: str | None):
    stmt = select(User).where(User.is_deleted.is_(False))
    if status:
        stmt = stmt.where(User.status == status)
    stmt = apply_keyword(stmt, keyword, User.username, User.display_name)
    total = count_total(db, stmt)
    items = db.scalars(stmt.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def create_user(db: Session, *, username: str, display_name: str, password: str, email: str | None, mobile: str | None, status: str):
    existing = db.scalar(select(User).where(User.username == username, User.is_deleted.is_(False)))
    if existing is not None:
        raise ApiError(code="USERNAME_ALREADY_EXISTS", message="Username already exists.", status_code=409)
    user = User(
        username=username,
        display_name=display_name,
        password_hash=hash_secret(password),
        email=email,
        mobile=mobile,
        status=status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise ApiError(code="USER_NOT_FOUND", message="User not found.", status_code=404)
    return user


def update_user(db: Session, user: User, *, display_name: str | None, email: str | None, mobile: str | None, status: str | None) -> User:
    if display_name is not None:
        user.display_name = display_name
    if email is not None:
        user.email = email
    if mobile is not None:
        user.mobile = mobile
    if status is not None:
        user.status = status
    db.commit()
    db.refresh(user)
    return user
