from __future__ import annotations

from app.models import utc_now


def published_at_for_status(status: str, current_published_at=None):
    if status == "published" and current_published_at is None:
        return utc_now()
    return current_published_at
