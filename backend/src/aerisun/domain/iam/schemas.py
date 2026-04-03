from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from aerisun.core.schemas import ModelBase

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(ModelBase):
    token: str
    expires_at: datetime


class AdminLoginOptionsRead(ModelBase):
    oauth_providers: list[str] = Field(default_factory=list)
    email_enabled: bool = False


class AdminEmailLoginRequest(BaseModel):
    email: str


class AdminUserRead(ModelBase):
    id: str
    username: str
    is_active: bool
    created_at: datetime


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class AdminProfileUpdate(BaseModel):
    username: str | None = None


class AdminSessionRead(ModelBase):
    id: str
    created_at: datetime
    expires_at: datetime
    is_current: bool = False


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------


class ApiKeyCreate(BaseModel):
    key_name: str
    scopes: list[str] = Field(default_factory=list)


class ApiKeyUpdate(BaseModel):
    key_name: str | None = None
    scopes: list[str] | None = None
    enabled: bool | None = None


class ApiKeyAdminRead(ModelBase):
    id: str
    key_name: str
    key_prefix: str
    key_suffix: str
    enabled: bool
    scopes: list[str]
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApiKeyCreateResponse(ModelBase):
    item: ApiKeyAdminRead
    raw_key: str
