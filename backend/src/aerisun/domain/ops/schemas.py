from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

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
    auth_provider: str | None = Field(default=None, description="Normalized auth provider")
    body: str
    status: str
    created_at: datetime
    updated_at: datetime


class GuestbookAdminRead(ModelBase):
    id: str
    name: str
    email: str | None
    auth_provider: str | None = Field(default=None, description="Normalized auth provider")
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


class ConfigDiffLineRead(BaseModel):
    path: str = Field(description="Flattened JSON path for the changed field")
    before: str = Field(description="Human-readable previous value")
    after: str = Field(description="Human-readable next value")


class ConfigRevisionListItemRead(ModelBase):
    id: str
    actor_id: str | None
    resource_key: str
    resource_label: str
    operation: str
    resource_version: str
    summary: str
    changed_fields: list[str] = Field(default_factory=list)
    sensitive_fields: list[str] = Field(default_factory=list)
    restored_from_revision_id: str | None = None
    created_at: datetime


class ConfigRevisionDetailRead(ConfigRevisionListItemRead):
    before_preview: Any = Field(default=None, description="Masked preview of the config before the change")
    after_preview: Any = Field(default=None, description="Masked preview of the config after the change")
    diff_lines: list[ConfigDiffLineRead] = Field(default_factory=list)
    restorable: bool = Field(default=True, description="Whether the revision can be restored")


class ConfigRevisionRestoreWrite(BaseModel):
    target: Literal["before", "after"] = Field(default="before", description='Restore target: "before" or "after"')
    reason: str | None = Field(default=None, description="Optional operator note recorded in the restore summary")


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


class TrafficTrendPoint(BaseModel):
    date: date
    views: int = 0


class TopPageMetric(BaseModel):
    url: str
    views: int = 0
    share: float = 0.0


class DashboardTrafficMetrics(BaseModel):
    total_views: int = 0
    top_pages: list[TopPageMetric] = Field(default_factory=list)
    distribution: list[TopPageMetric] = Field(default_factory=list)
    history: list[TrafficTrendPoint] = Field(default_factory=list)
    last_snapshot_at: datetime | None = None


class VisitorRecordRead(ModelBase):
    id: str
    visited_at: datetime
    path: str
    ip_address: str
    location: str | None = None
    isp: str | None = None
    owner: str | None = None
    status_text: str | None = None
    user_agent: str | None = None
    referer: str | None = None
    status_code: int
    duration_ms: int
    is_bot: bool = False


class DashboardVisitorMetrics(BaseModel):
    total_visits: int = 0
    unique_visitors_24h: int = 0
    unique_visitors_7d: int = 0
    average_request_duration_ms: int = 0
    top_pages: list[TopPageMetric] = Field(default_factory=list)
    history: list[TrafficTrendPoint] = Field(default_factory=list)
    recent_visits: list[VisitorRecordRead] = Field(default_factory=list)
    last_visit_at: datetime | None = None


class DashboardAuxMetrics(BaseModel):
    pending_moderation: int = 0
    published_posts: int = 0
    published_diary_entries: int = 0
    published_thoughts: int = 0
    published_excerpts: int = 0


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
    traffic: DashboardTrafficMetrics = Field(default_factory=DashboardTrafficMetrics)
    visitors: DashboardVisitorMetrics = Field(default_factory=DashboardVisitorMetrics)
    aux_metrics: DashboardAuxMetrics = Field(default_factory=DashboardAuxMetrics)


class SystemInfo(BaseModel):
    version: str = "1.0.0"
    python_version: str
    db_size_bytes: int
    media_dir_size_bytes: int
    uptime_seconds: float
    environment: str
    site_url: str
