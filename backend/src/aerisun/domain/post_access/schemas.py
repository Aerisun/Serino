from __future__ import annotations

from datetime import datetime

from pydantic import Field

from aerisun.core.schemas import ModelBase


class PostAccessStateRead(ModelBase):
    authenticated: bool
    approval_enabled: bool
    requires_approval: bool
    has_access: bool
    owner_name: str
    post_title: str
    mail_feedback_available: bool = False
    access_expires_at: datetime | None = None
    remaining_seconds: int | None = None
    pending_request_id: str | None = None


class PostAccessRequestCreate(ModelBase):
    reason: str = Field(min_length=1, max_length=1000)


class PostAccessRequestRead(ModelBase):
    id: str
    post_id: str
    reason: str
    status: str
    has_access: bool
    access_expires_at: datetime | None = None
    remaining_seconds: int | None = None
    created_at: datetime
    updated_at: datetime


class PostAccessGrantedRead(ModelBase):
    slug: str
    title: str
    access_expires_at: datetime
    remaining_seconds: int


class PostAccessGrantedListRead(ModelBase):
    items: list[PostAccessGrantedRead]


class PostAccessRequestAdminRead(ModelBase):
    id: str
    post_id: str
    post_slug: str
    post_title: str
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


class PostAccessRequestAdminList(ModelBase):
    items: list[PostAccessRequestAdminRead]
    total: int
    page: int
    page_size: int
    people_total: int
    pending_total: int
    authorized_total: int


class PostAccessRequestAdminUpdate(ModelBase):
    grant_access: bool | None = None
    expires_at: datetime | None = None
    revoke_access: bool = False
