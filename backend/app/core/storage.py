from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings
from app.core.security import generate_token

settings = get_settings()


@dataclass(slots=True)
class StoredObject:
    object_key: str
    absolute_path: Path


class StorageBackend(Protocol):
    def store_bytes(self, *, namespace: str, file_name: str, content_bytes: bytes) -> StoredObject: ...

    def resolve_path(self, object_key: str) -> Path: ...


class LocalStorageBackend:
    def __init__(self, *, base_path: Path) -> None:
        self._base_path = base_path

    def store_bytes(self, *, namespace: str, file_name: str, content_bytes: bytes) -> StoredObject:
        safe_name = Path(file_name or "upload.bin").name
        object_key = f"{namespace}/{generate_token('obj')}_{safe_name}"
        absolute_path = self.resolve_path(object_key)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(content_bytes)
        return StoredObject(object_key=object_key, absolute_path=absolute_path)

    def resolve_path(self, object_key: str) -> Path:
        return self._base_path / object_key


def get_storage_backend() -> StorageBackend:
    settings.local_storage_path.mkdir(parents=True, exist_ok=True)
    return LocalStorageBackend(base_path=settings.local_storage_path)
