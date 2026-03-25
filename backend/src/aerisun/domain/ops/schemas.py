from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from aerisun.core.schemas import ModelBase

# ---------------------------------------------------------------------------
# Moderation
# ---------------------------------------------------------------------------


class CommentAdminRead(ModelBase):
    id: str
    content_type: str
    content_slug: str
    parent_id: str | None
    author_name: str
    author_email: str | None
    body: str
    status: str
    created_at: datetime
    updated_at: datetime


class GuestbookAdminRead(ModelBase):
    id: str
    name: str
    email: str | None
    website: str | None
    body: str
    status: str
    created_at: datetime
    updated_at: datetime


class ModerateAction(BaseModel):
    action: str  # "approve", "reject", "delete"
    reason: str | None = None


# ---------------------------------------------------------------------------
# Audit & Backup
# ---------------------------------------------------------------------------


class AuditLogRead(ModelBase):
    id: str
    actor_type: str
    actor_id: str | None
    action: str
    target_type: str | None
    target_id: str | None
    payload: dict[str, Any]
    created_at: datetime


class BackupSnapshotRead(ModelBase):
    id: str
    snapshot_type: str
    status: str
    db_path: str
    replica_url: str | None
    backup_path: str | None
    checksum: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class MonthlyCount(BaseModel):
    month: str  # "2026-01"
    posts: int = 0
    diary: int = 0
    thoughts: int = 0
    excerpts: int = 0


class RecentContentItem(BaseModel):
    id: str
    title: str
    content_type: str  # "post", "diary", "thought", "excerpt"
    status: str
    updated_at: datetime


class DashboardStats(ModelBase):
    posts: int
    diary_entries: int
    thoughts: int
    excerpts: int
    comments: int
    guestbook_entries: int
    friends: int
    assets: int


class EnhancedDashboardStats(ModelBase):
    posts: int
    diary_entries: int
    thoughts: int
    excerpts: int
    comments: int
    guestbook_entries: int
    friends: int
    assets: int
    posts_by_status: dict[str, int] = Field(default_factory=dict)
    content_by_month: list[MonthlyCount] = Field(default_factory=list)
    recent_content: list[RecentContentItem] = Field(default_factory=list)


class SystemInfo(BaseModel):
    version: str = "1.0.0"
    python_version: str
    db_size_bytes: int
    media_dir_size_bytes: int
    uptime_seconds: float
    environment: str
    site_url: str
