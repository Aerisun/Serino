from __future__ import annotations

from datetime import datetime

from pydantic import Field

from aerisun.core.schemas import ModelBase


class DiaryAccessStateRead(ModelBase):
    authenticated: bool
    diary_private_enabled: bool
    has_access: bool
    owner_name: str
    mail_feedback_available: bool = False
    access_expires_at: datetime | None = None
    remaining_seconds: int | None = None
    pending_request_id: str | None = None


class DiaryAccessRequestCreate(ModelBase):
    reason: str = Field(min_length=1, max_length=1000)


class DiaryAccessRequestRead(ModelBase):
    id: str
    reason: str
    status: str
    has_access: bool
    access_expires_at: datetime | None = None
    remaining_seconds: int | None = None
    created_at: datetime
    updated_at: datetime


class DiaryAccessRequestAdminRead(ModelBase):
    id: str
    site_user_id: str
    visitor_email: str
    visitor_display_name: str
    visitor_avatar_url: str
    visitor_auth_provider: str
    visitor_oauth_providers: list[str]
    reason: str
    status: str
    has_access: bool
    access_granted_at: datetime | None = None
    access_expires_at: datetime | None = None
    access_revoked_at: datetime | None = None
    remaining_seconds: int | None = None
    created_at: datetime
    updated_at: datetime


class DiaryAccessRequestAdminUpdate(ModelBase):
    grant_access: bool | None = None
    expires_at: datetime | None = None
    revoke_access: bool = False
