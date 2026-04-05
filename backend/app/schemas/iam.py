from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.base import ORMModel


class UserRead(ORMModel):
    id: int
    username: str
    display_name: str
    email: str | None = None
    mobile: str | None = None
    status: str
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    username: str
    display_name: str
    password: str
    email: str | None = None
    mobile: str | None = None
    status: str = "active"


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    mobile: str | None = None
    status: str | None = None


class SessionCreate(BaseModel):
    username: str
    password: str


class SessionRefreshCreate(BaseModel):
    refresh_token: str
