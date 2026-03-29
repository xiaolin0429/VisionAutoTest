from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
import secrets
from typing import Any

import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

settings = get_settings()


def hash_secret(raw_value: str) -> str:
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


def verify_secret(raw_value: str, hashed_value: str) -> bool:
    return secrets.compare_digest(hash_secret(raw_value), hashed_value)


def generate_token(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(24)}"


def generate_access_token(*, subject: int, session_id: str, token_jti: str, expires_in_seconds: int) -> str:
    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "sid": session_id,
        "jti": token_jti,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(seconds=expires_in_seconds)).timestamp()),
        "iss": settings.jwt_issuer,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        options={"require": ["sub", "sid", "jti", "iat", "exp", "iss"]},
    )


def is_token_expired_error(exc: Exception) -> bool:
    return isinstance(exc, jwt.ExpiredSignatureError)


def is_token_invalid_error(exc: Exception) -> bool:
    return isinstance(exc, jwt.InvalidTokenError)


def encrypt_sensitive_value(value: str) -> str:
    return _build_cipher().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_sensitive_value(ciphertext: str) -> str:
    try:
        return _build_cipher().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored sensitive value cannot be decrypted with the current key.") from exc


def _build_cipher() -> Fernet:
    key_material = hashlib.sha256(settings.data_encryption_key.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key_material)
    return Fernet(fernet_key)
