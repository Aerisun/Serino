from __future__ import annotations

import sys
import time
from datetime import UTC, date, datetime, timedelta
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
    DashboardAuxMetrics,
    DashboardTrafficMetrics,
    DashboardVisitorMetrics,
    EnhancedDashboardStats,
    MonthlyCount,
    RecentContentItem,
    SystemInfo,
    TopPageMetric,
    TrafficTrendPoint,
    VisitorRecordRead,
)
from aerisun.domain.ops.ip_geo import lookup_ip_geolocation
from aerisun.domain.social.models import Friend
from aerisun.domain.waline.service import count_waline_records, list_counter_history_by_date, list_counter_stats

_STARTUP_TIME = time.time()
_TRAFFIC_HISTORY_DAYS = 14
_TOP_PAGES_LIMIT = 10
_DISTRIBUTION_LIMIT = 5


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


def _seed_missing_traffic_history(session: Session) -> None:
    history_by_date = list_counter_history_by_date()
    changed = False
    for snapshot_date, stats_by_url in history_by_date.items():
        for url, stats in stats_by_url.items():
            existing = repo.get_latest_traffic_snapshot_for_url(session, url=url, before_date=snapshot_date)
            if existing is not None and existing.snapshot_date == snapshot_date:
                continue

            previous = repo.get_latest_traffic_snapshot_for_url(
                session,
                url=url,
                before_date=snapshot_date - timedelta(days=1),
            )
            previous_views = previous.cumulative_views if previous is not None else 0
            daily_views = max(stats.pageview_count - previous_views, 0)
            repo.upsert_traffic_daily_snapshot(
                session,
                snapshot_date=snapshot_date,
                url=url,
                cumulative_views=stats.pageview_count,
                daily_views=daily_views,
                cumulative_reactions=stats.reaction_count,
            )
            changed = True

    if changed:
        session.commit()


def record_daily_traffic_snapshot(
    session: Session,
    *,
    snapshot_date: date | None = None,
    commit: bool = True,
) -> bool:
    """Persist one daily traffic snapshot from current Waline counters."""
    target_date = snapshot_date or datetime.now(UTC).date()
    current_stats = list_counter_stats()
    changed = False

    for stats in current_stats:
        previous = repo.get_latest_traffic_snapshot_for_url(
            session,
            url=stats.url,
            before_date=target_date - timedelta(days=1),
        )
        previous_views = previous.cumulative_views if previous is not None else 0
        daily_views = max(stats.pageview_count - previous_views, 0)
        repo.upsert_traffic_daily_snapshot(
            session,
            snapshot_date=target_date,
            url=stats.url,
            cumulative_views=stats.pageview_count,
            daily_views=daily_views,
            cumulative_reactions=stats.reaction_count,
        )
        changed = True

    if changed and commit:
        session.commit()
    return changed


def _build_traffic_metrics(session: Session) -> DashboardTrafficMetrics:
    _seed_missing_traffic_history(session)
    record_daily_traffic_snapshot(session, commit=True)

    end_date = datetime.now(UTC).date()
    start_date = end_date - timedelta(days=_TRAFFIC_HISTORY_DAYS - 1)
    snapshots = repo.list_traffic_snapshots_between(session, start_date=start_date, end_date=end_date)

    daily_totals: dict[date, int] = {
        start_date + timedelta(days=index): 0 for index in range(_TRAFFIC_HISTORY_DAYS)
    }
    for snapshot in snapshots:
        daily_totals[snapshot.snapshot_date] = daily_totals.get(snapshot.snapshot_date, 0) + snapshot.daily_views

    history = [
        TrafficTrendPoint(date=day, views=daily_totals.get(day, 0))
        for day in sorted(daily_totals)
    ]

    latest_snapshots = repo.list_latest_traffic_snapshots(session, as_of_date=end_date)
    total_views = sum(item.cumulative_views for item in latest_snapshots)

    ranked_pages = [
        TopPageMetric(
            url=item.url,
            views=item.cumulative_views,
            share=round((item.cumulative_views / total_views), 4) if total_views else 0.0,
        )
        for item in latest_snapshots
        if item.url and item.url != "/guestbook"
    ]

    last_snapshot_at = repo.get_latest_traffic_snapshot_timestamp(session)
    return DashboardTrafficMetrics(
        total_views=total_views,
        top_pages=ranked_pages[:_TOP_PAGES_LIMIT],
        distribution=ranked_pages[:_DISTRIBUTION_LIMIT],
        history=history,
        last_snapshot_at=last_snapshot_at,
    )


def _build_aux_metrics(session: Session) -> DashboardAuxMetrics:
    return DashboardAuxMetrics(
        pending_moderation=count_waline_records(status="waiting")
        + count_waline_records(status="waiting", guestbook_only=True),
        published_posts=repo.count_with_filters(
            session,
            PostEntry,
            PostEntry.status == "published",
            PostEntry.visibility == "public",
        ),
        published_diary_entries=repo.count_with_filters(
            session,
            DiaryEntry,
            DiaryEntry.status == "published",
            DiaryEntry.visibility == "public",
        ),
        published_thoughts=repo.count_with_filters(
            session,
            ThoughtEntry,
            ThoughtEntry.status == "published",
            ThoughtEntry.visibility == "public",
        ),
        published_excerpts=repo.count_with_filters(
            session,
            ExcerptEntry,
            ExcerptEntry.status == "published",
            ExcerptEntry.visibility == "public",
        ),
    )


def _status_text(status_code: int) -> str:
    if 200 <= status_code <= 299:
        return "成功"
    if 300 <= status_code <= 399:
        return "重定向"
    if status_code == 401:
        return "未授权"
    if status_code == 403:
        return "禁止访问"
    if status_code == 404:
        return "未找到"
    if 400 <= status_code <= 499:
        return "请求错误"
    if 500 <= status_code <= 599:
        return "服务异常"
    return "未知"


def _build_visitor_metrics(session: Session) -> DashboardVisitorMetrics:
    now = datetime.now(UTC)
    history_days = 14
    start_date = now.date() - timedelta(days=history_days - 1)
    history_rows = repo.list_visit_history_by_day(session, start_date=start_date, end_date=now.date())
    history_map = {day: views for day, views in history_rows}
    history = [
        TrafficTrendPoint(date=start_date + timedelta(days=index), views=history_map.get(str(start_date + timedelta(days=index)), 0))
        for index in range(history_days)
    ]

    recent_records, _ = repo.find_visit_records_paginated(session, page=1, page_size=10)
    total_visits = repo.count_visit_records_since(session, since=datetime.fromtimestamp(0, UTC))
    unique_visitors_24h = repo.count_unique_visitors_since(session, since=now - timedelta(hours=24))
    unique_visitors_7d = repo.count_unique_visitors_since(session, since=now - timedelta(days=7))
    average_request_duration_ms = repo.average_visit_duration_since(session, since=now - timedelta(days=7))
    top_page_rows = repo.list_visit_top_pages(session, since=now - timedelta(days=14), limit=_TOP_PAGES_LIMIT)
    top_total = sum(views for _, views in top_page_rows)
    top_pages = [
        TopPageMetric(
            url=path,
            views=views,
            share=round((views / top_total), 4) if top_total else 0.0,
        )
        for path, views in top_page_rows
    ]

    recent_visits: list[VisitorRecordRead] = []
    for item in recent_records:
        geo = lookup_ip_geolocation(item.ip_address)
        status_text = _status_text(item.status_code)
        recent_visits.append(
            VisitorRecordRead(
                id=item.id,
                visited_at=item.visited_at,
                path=item.path,
                ip_address=item.ip_address,
                location=geo.location_label,
                isp=geo.isp,
                owner=geo.owner,
                status_text=status_text,
                user_agent=item.user_agent,
                referer=item.referer,
                status_code=item.status_code,
                duration_ms=item.duration_ms,
                is_bot=item.is_bot,
            )
        )

    return DashboardVisitorMetrics(
        total_visits=total_visits,
        unique_visitors_24h=unique_visitors_24h,
        unique_visitors_7d=unique_visitors_7d,
        average_request_duration_ms=average_request_duration_ms,
        top_pages=top_pages,
        history=history,
        recent_visits=recent_visits,
        last_visit_at=repo.get_latest_visit_timestamp(session),
    )


def list_visitor_records(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    path: str | None = None,
    ip: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    include_bots: bool = False,
) -> dict:
    items, total = repo.find_visit_records_paginated(
        session,
        page=page,
        page_size=page_size,
        path=path,
        ip=ip,
        date_from=date_from,
        date_to=date_to,
        include_bots=include_bots,
    )
    enriched_items: list[VisitorRecordRead] = []
    for item in items:
        geo = lookup_ip_geolocation(item.ip_address)
        enriched_items.append(
            VisitorRecordRead(
                id=item.id,
                visited_at=item.visited_at,
                path=item.path,
                ip_address=item.ip_address,
                location=geo.location_label,
                isp=geo.isp,
                owner=geo.owner,
                status_text=_status_text(item.status_code),
                user_agent=item.user_agent,
                referer=item.referer,
                status_code=item.status_code,
                duration_ms=item.duration_ms,
                is_bot=item.is_bot,
            )
        )
    return {
        "items": enriched_items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def cleanup_old_visit_records(session: Session, *, retention_days: int = 30) -> int:
    deleted = repo.delete_visit_records_before(session, before=datetime.now(UTC) - timedelta(days=retention_days))
    if deleted:
        session.commit()
    return deleted


def get_dashboard_stats(session: Session) -> EnhancedDashboardStats:
    """Aggregate dashboard statistics from all domains."""
    now = datetime.now(UTC)
    six_months_ago = now - timedelta(days=180)

    posts_count = repo.count_model(session, PostEntry)
    diary_count = repo.count_model(session, DiaryEntry)
    thoughts_count = repo.count_model(session, ThoughtEntry)
    excerpts_count = repo.count_model(session, ExcerptEntry)
    friends_count = repo.count_model(session, Friend)
    assets_count = repo.count_model(session, Asset)

    posts_by_status = repo.count_by_status(session, PostEntry)

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
        traffic=_build_traffic_metrics(session),
        visitors=_build_visitor_metrics(session),
        aux_metrics=_build_aux_metrics(session),
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
        site_url=settings.site_url,
    )
