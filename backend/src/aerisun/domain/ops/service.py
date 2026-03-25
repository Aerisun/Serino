from __future__ import annotations

import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.exceptions import ResourceNotFound
from aerisun.domain.media.models import Asset
from aerisun.domain.ops import repository as repo
from aerisun.domain.ops.schemas import (
    AuditLogRead,
    BackupSnapshotRead,
    EnhancedDashboardStats,
    MonthlyCount,
    RecentContentItem,
    SystemInfo,
)
from aerisun.domain.social.models import Friend
from aerisun.domain.waline.service import count_waline_records

_STARTUP_TIME = time.time()


def list_audit_logs(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    action: str | None = None,
    actor_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """List audit logs with pagination and filters."""
    items, total = repo.find_audit_logs_paginated(
        session,
        page=page,
        page_size=page_size,
        action=action,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "items": [AuditLogRead.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_backups(session: Session) -> list[BackupSnapshotRead]:
    """List all backup snapshots."""
    return [BackupSnapshotRead.model_validate(s) for s in repo.find_all_backups(session)]


def create_backup_snapshot(session: Session) -> BackupSnapshotRead:
    """Create a manual backup snapshot. Commits."""
    settings = get_settings()
    snapshot = repo.create_backup(
        session,
        snapshot_type="manual",
        status="queued",
        db_path=str(settings.db_path),
        replica_url=settings.litestream_replica_url,
    )
    session.commit()
    session.refresh(snapshot)
    return BackupSnapshotRead.model_validate(snapshot)


def restore_backup(session: Session, snapshot_id: str) -> BackupSnapshotRead:
    """Mark a backup as restoring. Raises LookupError if not found. Commits."""
    snapshot = repo.find_backup_by_id(session, snapshot_id)
    if snapshot is None:
        raise ResourceNotFound("Backup snapshot not found")
    snapshot.status = "restoring"
    session.commit()
    session.refresh(snapshot)
    return BackupSnapshotRead.model_validate(snapshot)


def get_dashboard_stats(session: Session) -> EnhancedDashboardStats:
    """Aggregate dashboard statistics from all domains."""
    now = datetime.now(UTC)
    six_months_ago = now - timedelta(days=180)

    # Basic counts
    posts_count = repo.count_model(session, PostEntry)
    diary_count = repo.count_model(session, DiaryEntry)
    thoughts_count = repo.count_model(session, ThoughtEntry)
    excerpts_count = repo.count_model(session, ExcerptEntry)
    friends_count = repo.count_model(session, Friend)
    assets_count = repo.count_model(session, Asset)

    # Posts by status
    posts_by_status = repo.count_by_status(session, PostEntry)

    # Content by month (last 6 months)
    content_type_map = [
        (PostEntry, "posts"),
        (DiaryEntry, "diary"),
        (ThoughtEntry, "thoughts"),
        (ExcerptEntry, "excerpts"),
    ]
    month_data: dict[str, dict[str, int]] = {}
    for model, type_key in content_type_map:
        rows = repo.count_by_month(session, model, since=six_months_ago)
        for month_str, count in rows:
            if month_str not in month_data:
                month_data[month_str] = {
                    "posts": 0,
                    "diary": 0,
                    "thoughts": 0,
                    "excerpts": 0,
                }
            month_data[month_str][type_key] = count

    content_by_month = sorted(
        [MonthlyCount(month=m, **counts) for m, counts in month_data.items()],
        key=lambda x: x.month,
    )

    # Recent content (last 5 most recently updated across all types)
    recent_type_map = [
        (PostEntry, "post"),
        (DiaryEntry, "diary"),
        (ThoughtEntry, "thought"),
        (ExcerptEntry, "excerpt"),
    ]
    recent_items: list[RecentContentItem] = []
    for model, type_key in recent_type_map:
        for row in repo.find_recent(session, model, limit=5):
            recent_items.append(
                RecentContentItem(
                    id=row.id,
                    title=row.title,
                    content_type=type_key,
                    status=row.status,
                    updated_at=row.updated_at,
                )
            )
    recent_items.sort(key=lambda x: x.updated_at, reverse=True)
    recent_content = recent_items[:5]

    return EnhancedDashboardStats(
        posts=posts_count,
        diary_entries=diary_count,
        thoughts=thoughts_count,
        excerpts=excerpts_count,
        comments=count_waline_records(),
        guestbook_entries=count_waline_records(guestbook_only=True),
        friends=friends_count,
        assets=assets_count,
        posts_by_status=posts_by_status,
        content_by_month=content_by_month,
        recent_content=recent_content,
    )


def get_system_info() -> SystemInfo:
    """Gather system runtime information."""
    settings = get_settings()

    db_size = 0
    db_path = Path(settings.db_path)
    if db_path.exists():
        db_size = db_path.stat().st_size

    media_size = 0
    media_path = Path(settings.media_dir)
    if media_path.exists():
        for f in media_path.rglob("*"):
            if f.is_file():
                media_size += f.stat().st_size

    return SystemInfo(
        python_version=sys.version.split()[0],
        db_size_bytes=db_size,
        media_dir_size_bytes=media_size,
        uptime_seconds=time.time() - _STARTUP_TIME,
        environment=settings.environment,
    )
