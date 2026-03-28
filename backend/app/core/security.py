from __future__ import annotations

import hashlib
import secrets


def hash_secret(raw_value: str) -> str:
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


def verify_secret(raw_value: str, hashed_value: str) -> bool:
    return secrets.compare_digest(hash_secret(raw_value), hashed_value)


def generate_token(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(24)}"

