from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from aerisun.core.time import beijing_date, beijing_day_bounds, beijing_today
from aerisun.domain.ops.models import (
    AuditLog,
    BackupCommit,
    BackupQueueItem,
    BackupRecoveryKey,
    BackupTargetConfig,
    SyncRun,
    TrafficDailySnapshot,
    VisitRecord,
)


def _apply_visit_filters(
    query,
    *,
    path: str | None = None,
    ip: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    include_bots: bool = False,
):
    if path:
        query = query.filter(VisitRecord.path.contains(path))
    if ip:
        query = query.filter(VisitRecord.ip_address.contains(ip))
    if date_from:
        query = query.filter(VisitRecord.visited_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(VisitRecord.visited_at <= datetime.fromisoformat(date_to))
    if not include_bots:
        query = query.filter(VisitRecord.is_bot.is_(False))
    return query


def find_audit_logs_paginated(
    session: Session,
    *,
    page: int,
    page_size: int,
    action: str | None = None,
    actor_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[AuditLog], int]:
    """Filtered, paginated query for audit logs. Returns (items, total)."""
    q = session.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action.contains(action))
    if actor_id:
        q = q.filter(AuditLog.actor_id == actor_id)
    if date_from:
        q = q.filter(AuditLog.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(AuditLog.created_at <= datetime.fromisoformat(date_to))
    total = q.count()
    items = list(q.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all())
    return items, total


def get_backup_target_config(session: Session) -> BackupTargetConfig | None:
    return session.query(BackupTargetConfig).order_by(BackupTargetConfig.created_at.asc()).first()


def create_backup_target_config(session: Session, **kwargs) -> BackupTargetConfig:
    item = BackupTargetConfig(**kwargs)
    session.add(item)
    return item


def list_backup_queue_items(session: Session) -> list[BackupQueueItem]:
    return list(session.query(BackupQueueItem).order_by(BackupQueueItem.created_at.asc()).all())


def create_backup_queue_item(session: Session, **kwargs) -> BackupQueueItem:
    item = BackupQueueItem(**kwargs)
    session.add(item)
    return item


def get_backup_queue_item(session: Session, queue_item_id: str) -> BackupQueueItem | None:
    return session.get(BackupQueueItem, queue_item_id)


def find_active_backup_queue_item(session: Session) -> BackupQueueItem | None:
    return (
        session.query(BackupQueueItem)
        .filter(BackupQueueItem.status.in_(("queued", "running", "retrying")))
        .order_by(BackupQueueItem.created_at.asc())
        .first()
    )


def find_due_backup_queue_item(session: Session, *, now: datetime) -> BackupQueueItem | None:
    return (
        session.query(BackupQueueItem)
        .filter(BackupQueueItem.status.in_(("queued", "retrying")))
        .filter((BackupQueueItem.next_retry_at.is_(None)) | (BackupQueueItem.next_retry_at <= now))
        .order_by(BackupQueueItem.created_at.asc())
        .first()
    )


def list_backup_commits(session: Session) -> list[BackupCommit]:
    return list(session.query(BackupCommit).order_by(BackupCommit.created_at.desc()).all())


def create_backup_commit(session: Session, **kwargs) -> BackupCommit:
    item = BackupCommit(**kwargs)
    session.add(item)
    return item


def get_backup_commit(session: Session, commit_id: str) -> BackupCommit | None:
    return session.get(BackupCommit, commit_id)


def list_backup_recovery_keys(session: Session, *, credential_ref: str) -> list[BackupRecoveryKey]:
    return list(
        session.query(BackupRecoveryKey)
        .filter(BackupRecoveryKey.credential_ref == credential_ref)
        .order_by(BackupRecoveryKey.created_at.desc())
        .all()
    )


def get_active_backup_recovery_key(session: Session, *, credential_ref: str) -> BackupRecoveryKey | None:
    return (
        session.query(BackupRecoveryKey)
        .filter(
            BackupRecoveryKey.credential_ref == credential_ref,
            BackupRecoveryKey.status == "active",
        )
        .order_by(BackupRecoveryKey.created_at.desc())
        .first()
    )


def get_backup_recovery_key_by_fingerprint(
    session: Session, *, credential_ref: str, secrets_fingerprint: str
) -> BackupRecoveryKey | None:
    return (
        session.query(BackupRecoveryKey)
        .filter(
            BackupRecoveryKey.credential_ref == credential_ref,
            BackupRecoveryKey.secrets_fingerprint == secrets_fingerprint,
        )
        .order_by(BackupRecoveryKey.created_at.desc())
        .first()
    )


def create_backup_recovery_key(session: Session, **kwargs) -> BackupRecoveryKey:
    item = BackupRecoveryKey(**kwargs)
    session.add(item)
    return item


def list_sync_runs(session: Session) -> list[SyncRun]:
    return list(session.query(SyncRun).order_by(SyncRun.created_at.desc()).all())


def create_sync_run(session: Session, **kwargs) -> SyncRun:
    item = SyncRun(**kwargs)
    session.add(item)
    return item


def get_sync_run(session: Session, run_id: str) -> SyncRun | None:
    return session.get(SyncRun, run_id)


def find_running_sync_run(session: Session, *, job_name: str) -> SyncRun | None:
    return (
        session.query(SyncRun)
        .filter(SyncRun.job_name == job_name, SyncRun.status == "running")
        .order_by(SyncRun.created_at.asc())
        .first()
    )


# -- Stats helpers --


def count_model(session: Session, model: type) -> int:
    """Count total rows for a given model."""
    return session.query(func.count(model.id)).scalar() or 0


def count_by_status(session: Session, model: type) -> dict[str, int]:
    """Group by status field and count. Returns {status: count}."""
    rows = session.query(model.status, func.count(model.id)).group_by(model.status).all()
    return {s: c for s, c in rows}


def count_by_month(
    session: Session,
    model: type,
    *,
    since: datetime,
) -> list[tuple[str, int]]:
    """Group by year-month and count items created since a date."""
    return list(
        session.query(
            func.strftime("%Y-%m", model.created_at),
            func.count(model.id),
        )
        .filter(model.created_at >= since)
        .group_by(func.strftime("%Y-%m", model.created_at))
        .all()
    )


def find_recent(session: Session, model: type, *, limit: int = 5) -> list[Any]:
    """Find most recently updated items for a model."""
    return list(session.query(model).order_by(model.updated_at.desc()).limit(limit).all())


def count_with_filters(session: Session, model: type, /, *criteria: Any) -> int:
    """Count rows for a model with optional SQLAlchemy filter criteria."""
    query = session.query(func.count(model.id))
    if criteria:
        query = query.filter(*criteria)
    return query.scalar() or 0


def upsert_traffic_daily_snapshot(
    session: Session,
    *,
    snapshot_date: date,
    url: str,
    cumulative_views: int,
    daily_views: int,
    cumulative_reactions: int,
) -> TrafficDailySnapshot:
    snapshot = (
        session.query(TrafficDailySnapshot)
        .filter(
            TrafficDailySnapshot.snapshot_date == snapshot_date,
            TrafficDailySnapshot.url == url,
        )
        .one_or_none()
    )
    if snapshot is None:
        snapshot = TrafficDailySnapshot(
            snapshot_date=snapshot_date,
            url=url,
            cumulative_views=cumulative_views,
            daily_views=daily_views,
            cumulative_reactions=cumulative_reactions,
        )
        session.add(snapshot)
        return snapshot

    snapshot.cumulative_views = cumulative_views
    snapshot.daily_views = daily_views
    snapshot.cumulative_reactions = cumulative_reactions
    return snapshot


def get_latest_traffic_snapshot_for_url(
    session: Session,
    *,
    url: str,
    before_date: date | None = None,
) -> TrafficDailySnapshot | None:
    query = session.query(TrafficDailySnapshot).filter(TrafficDailySnapshot.url == url)
    if before_date is not None:
        query = query.filter(TrafficDailySnapshot.snapshot_date <= before_date)
    return query.order_by(TrafficDailySnapshot.snapshot_date.desc(), TrafficDailySnapshot.created_at.desc()).first()


def list_traffic_snapshots_between(
    session: Session,
    *,
    start_date: date,
    end_date: date,
) -> list[TrafficDailySnapshot]:
    return list(
        session.query(TrafficDailySnapshot)
        .filter(
            TrafficDailySnapshot.snapshot_date >= start_date,
            TrafficDailySnapshot.snapshot_date <= end_date,
        )
        .order_by(TrafficDailySnapshot.snapshot_date.asc(), TrafficDailySnapshot.url.asc())
        .all()
    )


def list_latest_traffic_snapshots(
    session: Session,
    *,
    as_of_date: date | None = None,
) -> list[TrafficDailySnapshot]:
    subquery = session.query(
        TrafficDailySnapshot.url.label("url"),
        func.max(TrafficDailySnapshot.snapshot_date).label("snapshot_date"),
    )
    if as_of_date is not None:
        subquery = subquery.filter(TrafficDailySnapshot.snapshot_date <= as_of_date)
    subquery = subquery.group_by(TrafficDailySnapshot.url).subquery()

    return list(
        session.query(TrafficDailySnapshot)
        .join(
            subquery,
            (TrafficDailySnapshot.url == subquery.c.url)
            & (TrafficDailySnapshot.snapshot_date == subquery.c.snapshot_date),
        )
        .order_by(TrafficDailySnapshot.cumulative_views.desc(), TrafficDailySnapshot.url.asc())
        .all()
    )


def get_latest_traffic_snapshot_timestamp(session: Session) -> datetime | None:
    value = session.query(func.max(TrafficDailySnapshot.updated_at)).scalar()
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def has_traffic_snapshot_for_date(session: Session, *, snapshot_date: date) -> bool:
    return (
        session.query(TrafficDailySnapshot.id).filter(TrafficDailySnapshot.snapshot_date == snapshot_date).first()
        is not None
    )


def default_traffic_history_start(days: int) -> date:
    return beijing_today() - timedelta(days=max(days - 1, 0))


def create_visit_record(
    session: Session,
    *,
    visited_at: datetime,
    path: str,
    ip_address: str,
    user_agent: str | None,
    referer: str | None,
    status_code: int,
    duration_ms: int,
    is_bot: bool,
) -> VisitRecord:
    record = VisitRecord(
        visited_at=visited_at,
        path=path,
        ip_address=ip_address,
        user_agent=user_agent,
        referer=referer,
        status_code=status_code,
        duration_ms=duration_ms,
        is_bot=is_bot,
    )
    session.add(record)
    return record


def find_visit_records_paginated(
    session: Session,
    *,
    page: int,
    page_size: int,
    path: str | None = None,
    ip: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    include_bots: bool = False,
) -> tuple[list[VisitRecord], int]:
    query = _apply_visit_filters(
        session.query(VisitRecord),
        path=path,
        ip=ip,
        date_from=date_from,
        date_to=date_to,
        include_bots=include_bots,
    )
    total = query.count()
    items = list(query.order_by(VisitRecord.visited_at.desc()).offset((page - 1) * page_size).limit(page_size).all())
    return items, total


def count_visit_records_since(session: Session, *, since: datetime, include_bots: bool = False) -> int:
    query = session.query(func.count(VisitRecord.id)).filter(VisitRecord.visited_at >= since)
    if not include_bots:
        query = query.filter(VisitRecord.is_bot.is_(False))
    return query.scalar() or 0


def count_unique_visitors_since(session: Session, *, since: datetime, include_bots: bool = False) -> int:
    query = session.query(func.count(func.distinct(VisitRecord.ip_address))).filter(VisitRecord.visited_at >= since)
    if not include_bots:
        query = query.filter(VisitRecord.is_bot.is_(False))
    return query.scalar() or 0


def average_visit_duration_since(session: Session, *, since: datetime, include_bots: bool = False) -> int:
    query = session.query(func.avg(VisitRecord.duration_ms)).filter(VisitRecord.visited_at >= since)
    if not include_bots:
        query = query.filter(VisitRecord.is_bot.is_(False))
    value = query.scalar()
    return round(value) if value is not None else 0


def list_visit_top_pages(
    session: Session,
    *,
    since: datetime,
    limit: int,
    include_bots: bool = False,
) -> list[tuple[str, int]]:
    query = session.query(VisitRecord.path, func.count(VisitRecord.id).label("views")).filter(
        VisitRecord.visited_at >= since
    )
    if not include_bots:
        query = query.filter(VisitRecord.is_bot.is_(False))
    query = (
        query.group_by(VisitRecord.path)
        .order_by(
            func.count(VisitRecord.id).desc(),
            VisitRecord.path.asc(),
        )
        .limit(limit)
    )
    return list(query.all())


def list_visit_history_by_day(
    session: Session,
    *,
    start_date: date,
    end_date: date,
    include_bots: bool = False,
) -> list[tuple[str, int]]:
    start_at, _ = beijing_day_bounds(start_date)
    _, end_at = beijing_day_bounds(end_date)
    query = session.query(VisitRecord.visited_at).filter(
        VisitRecord.visited_at >= start_at,
        VisitRecord.visited_at < end_at,
    )
    if not include_bots:
        query = query.filter(VisitRecord.is_bot.is_(False))

    counts: dict[str, int] = {}
    for (visited_at,) in query.all():
        key = beijing_date(visited_at).isoformat()
        counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda item: item[0])


def get_latest_visit_timestamp(session: Session, *, include_bots: bool = False) -> datetime | None:
    query = session.query(func.max(VisitRecord.visited_at))
    if not include_bots:
        query = query.filter(VisitRecord.is_bot.is_(False))
    value = query.scalar()
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def delete_visit_records_before(session: Session, *, before: datetime) -> int:
    return session.query(VisitRecord).filter(VisitRecord.visited_at < before).delete()
