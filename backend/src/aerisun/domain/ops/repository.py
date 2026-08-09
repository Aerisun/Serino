from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from aerisun.core.time import beijing_date, beijing_day_bounds, beijing_today, normalize_shanghai_datetime
from aerisun.domain.ops.models import (
    AuditLog,
    BackupBootstrapClaim,
    BackupCommit,
    BackupQueueItem,
    BackupRecoveryKey,
    BackupTargetConfig,
    SyncRun,
    TrafficDailySnapshot,
    VisitRecord,
)


@dataclass(frozen=True, slots=True)
class VisitRecordGroupSummary:
    group_number: int
    ip_address: str
    record_count: int
    newest_record_id: str
    oldest_record_id: str
    newest_visited_at: datetime
    oldest_visited_at: datetime
    ok_count: int
    error_count: int


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
        query = query.filter(VisitRecord.visited_at >= normalize_shanghai_datetime(datetime.fromisoformat(date_from)))
    if date_to:
        query = query.filter(VisitRecord.visited_at <= normalize_shanghai_datetime(datetime.fromisoformat(date_to)))
    if not include_bots:
        query = query.filter(VisitRecord.is_bot.is_(False))
    return query


def _visit_order_columns():
    return (VisitRecord.visited_at.desc(), VisitRecord.id.desc())


def _build_visit_record_group_subquery(
    session: Session,
    *,
    path: str | None = None,
    ip: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    include_bots: bool = True,
):
    base_query = _apply_visit_filters(
        session.query(
            VisitRecord.id.label("id"),
            VisitRecord.ip_address.label("ip_address"),
            VisitRecord.visited_at.label("visited_at"),
            VisitRecord.status_code.label("status_code"),
        ),
        path=path,
        ip=ip,
        date_from=date_from,
        date_to=date_to,
        include_bots=include_bots,
    )
    base = base_query.subquery()
    base_order = (base.c.visited_at.desc(), base.c.id.desc())
    previous_ip = func.lag(base.c.ip_address).over(order_by=base_order)
    starts_group = case(
        (previous_ip.is_(None), 1),
        (base.c.ip_address != previous_ip, 1),
        else_=0,
    ).label("starts_group")
    marked = select(
        base.c.id,
        base.c.ip_address,
        base.c.visited_at,
        base.c.status_code,
        starts_group,
    ).subquery()
    marked_order = (marked.c.visited_at.desc(), marked.c.id.desc())
    group_number = func.sum(marked.c.starts_group).over(order_by=marked_order, rows=(None, 0)).label("group_number")
    grouped = select(
        marked.c.id,
        marked.c.ip_address,
        marked.c.visited_at,
        marked.c.status_code,
        group_number,
    ).subquery()
    newest_rank = (
        func.row_number()
        .over(partition_by=grouped.c.group_number, order_by=(grouped.c.visited_at.desc(), grouped.c.id.desc()))
        .label("newest_rank")
    )
    oldest_rank = (
        func.row_number()
        .over(partition_by=grouped.c.group_number, order_by=(grouped.c.visited_at.asc(), grouped.c.id.asc()))
        .label("oldest_rank")
    )
    ranked = select(
        grouped.c.id,
        grouped.c.ip_address,
        grouped.c.visited_at,
        grouped.c.status_code,
        grouped.c.group_number,
        newest_rank,
        oldest_rank,
    ).subquery()
    return (
        select(
            ranked.c.group_number.label("group_number"),
            ranked.c.ip_address.label("ip_address"),
            func.count(ranked.c.id).label("record_count"),
            func.max(case((ranked.c.newest_rank == 1, ranked.c.id), else_=None)).label("newest_record_id"),
            func.max(case((ranked.c.oldest_rank == 1, ranked.c.id), else_=None)).label("oldest_record_id"),
            func.max(ranked.c.visited_at).label("newest_visited_at"),
            func.min(ranked.c.visited_at).label("oldest_visited_at"),
            func.sum(case((ranked.c.status_code < 400, 1), else_=0)).label("ok_count"),
            func.sum(case((ranked.c.status_code >= 400, 1), else_=0)).label("error_count"),
        )
        .group_by(ranked.c.group_number, ranked.c.ip_address)
        .subquery()
    )


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
        q = q.filter(AuditLog.created_at >= normalize_shanghai_datetime(datetime.fromisoformat(date_from)))
    if date_to:
        q = q.filter(AuditLog.created_at <= normalize_shanghai_datetime(datetime.fromisoformat(date_to)))
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


def list_backup_commits(session: Session, *, include_retention_tombstones: bool = False) -> list[BackupCommit]:
    query = session.query(BackupCommit)
    if not include_retention_tombstones:
        query = query.filter(BackupCommit.trigger_kind != "retention-pruned")
    return list(query.order_by(BackupCommit.created_at.desc()).all())


def create_backup_commit(session: Session, **kwargs) -> BackupCommit:
    item = BackupCommit(**kwargs)
    session.add(item)
    return item


def get_backup_commit(session: Session, commit_id: str) -> BackupCommit | None:
    return session.get(BackupCommit, commit_id)


def clear_backup_history_records(session: Session, *, job_name: str) -> None:
    session.query(BackupQueueItem).delete(synchronize_session=False)
    session.query(BackupCommit).delete(synchronize_session=False)
    session.query(SyncRun).filter(SyncRun.job_name == job_name).delete(synchronize_session=False)


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


def create_backup_bootstrap_claim(session: Session, **kwargs) -> BackupBootstrapClaim:
    item = BackupBootstrapClaim(**kwargs)
    session.add(item)
    return item


def get_backup_bootstrap_claim(session: Session, claim_id: str) -> BackupBootstrapClaim | None:
    return session.get(BackupBootstrapClaim, claim_id)


def get_backup_bootstrap_claim_by_token_hash(session: Session, token_hash: str) -> BackupBootstrapClaim | None:
    return (
        session.query(BackupBootstrapClaim)
        .filter(BackupBootstrapClaim.token_hash == token_hash)
        .order_by(BackupBootstrapClaim.created_at.desc())
        .first()
    )


def list_pending_backup_bootstrap_claims_for_target(
    session: Session,
    *,
    created_by_admin_id: str | None,
    remote_host: str,
    remote_port: int,
    remote_username: str,
    remote_path: str,
) -> list[BackupBootstrapClaim]:
    query = session.query(BackupBootstrapClaim).filter(
        BackupBootstrapClaim.status == "pending",
        BackupBootstrapClaim.remote_host == remote_host,
        BackupBootstrapClaim.remote_port == remote_port,
        BackupBootstrapClaim.remote_username == remote_username,
        BackupBootstrapClaim.remote_path == remote_path,
    )
    if created_by_admin_id is None:
        query = query.filter(BackupBootstrapClaim.created_by_admin_id.is_(None))
    else:
        query = query.filter(BackupBootstrapClaim.created_by_admin_id == created_by_admin_id)
    return list(query.order_by(BackupBootstrapClaim.created_at.desc()).all())


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


def reset_backup_sync_records(session: Session, *, credential_ref: str, job_name: str) -> None:
    clear_backup_history_records(session, job_name=job_name)
    session.query(BackupRecoveryKey).filter(BackupRecoveryKey.credential_ref == credential_ref).delete(
        synchronize_session=False
    )
    for claim in session.query(BackupBootstrapClaim).filter(BackupBootstrapClaim.status.in_(("pending", "failed"))):
        claim.status = "revoked"
        claim.revoked_at = normalize_shanghai_datetime(datetime.now())
        claim.last_error = "备份系统已重置，临时命令自动失效。"


# -- Stats helpers --


def count_model(session: Session, model: type) -> int:
    """Count total rows for a given model."""
    return session.query(func.count(model.id)).scalar() or 0


def count_by_status(session: Session, model: type) -> dict[str, int]:
    """Group by status field and count. Returns {status: count}."""
    rows = session.query(model.status, func.count(model.id)).group_by(model.status).all()
    return {s: c for s, c in rows}


def count_by_visibility(session: Session, model: type) -> dict[str, int]:
    """Group by visibility field and count. Returns {visibility: count}."""
    rows = session.query(model.visibility, func.count(model.id)).group_by(model.visibility).all()
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
    return normalize_shanghai_datetime(value)


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
    query: str | None = None,
    visitor_id: str | None = None,
    browser: str | None = None,
    browser_version: str | None = None,
    os: str | None = None,
    os_version: str | None = None,
    device_type: str | None = None,
    screen: str | None = None,
    language: str | None = None,
    referer_domain: str | None = None,
    utm_source: str | None = None,
    utm_medium: str | None = None,
    utm_campaign: str | None = None,
    utm_term: str | None = None,
    utm_content: str | None = None,
) -> VisitRecord:
    record = VisitRecord(
        visited_at=visited_at,
        path=path,
        query=query,
        ip_address=ip_address,
        visitor_id=visitor_id,
        user_agent=user_agent,
        browser=browser,
        browser_version=browser_version,
        os=os,
        os_version=os_version,
        device_type=device_type,
        screen=screen,
        language=language,
        referer=referer,
        referer_domain=referer_domain,
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        utm_term=utm_term,
        utm_content=utm_content,
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
    items = list(query.order_by(*_visit_order_columns()).offset((page - 1) * page_size).limit(page_size).all())
    return items, total


def find_visit_records_by_ids(session: Session, record_ids: set[str]) -> list[VisitRecord]:
    if not record_ids:
        return []
    return list(session.query(VisitRecord).filter(VisitRecord.id.in_(record_ids)).all())


def find_visit_record_groups_paginated(
    session: Session,
    *,
    page: int,
    page_size: int,
    path: str | None = None,
    ip: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    include_total: bool = True,
    include_bots: bool = True,
) -> tuple[list[VisitRecordGroupSummary], int]:
    groups = _build_visit_record_group_subquery(
        session,
        path=path,
        ip=ip,
        date_from=date_from,
        date_to=date_to,
        include_bots=include_bots,
    )
    offset = (page - 1) * page_size
    row_limit = page_size if include_total else page_size + 1
    rows = list(
        session.execute(select(groups).order_by(groups.c.group_number.asc()).offset(offset).limit(row_limit)).mappings()
    )
    if include_total:
        total = int(session.execute(select(func.count()).select_from(groups)).scalar_one())
    else:
        has_more = len(rows) > page_size
        rows = rows[:page_size]
        total = offset + len(rows) + (1 if has_more else 0)
        if not rows and offset:
            total = int(session.execute(select(func.count()).select_from(groups)).scalar_one())

    items = [
        VisitRecordGroupSummary(
            group_number=int(row["group_number"]),
            ip_address=str(row["ip_address"]),
            record_count=int(row["record_count"]),
            newest_record_id=str(row["newest_record_id"]),
            oldest_record_id=str(row["oldest_record_id"]),
            newest_visited_at=row["newest_visited_at"],
            oldest_visited_at=row["oldest_visited_at"],
            ok_count=int(row["ok_count"] or 0),
            error_count=int(row["error_count"] or 0),
        )
        for row in rows
    ]
    return items, total


def _visit_record_boundary_filter(newest: VisitRecord, oldest: VisitRecord):
    after_newest_or_self = or_(
        VisitRecord.visited_at < newest.visited_at,
        and_(VisitRecord.visited_at == newest.visited_at, VisitRecord.id <= newest.id),
    )
    before_oldest_or_self = or_(
        VisitRecord.visited_at > oldest.visited_at,
        and_(VisitRecord.visited_at == oldest.visited_at, VisitRecord.id >= oldest.id),
    )
    return and_(after_newest_or_self, before_oldest_or_self)


def find_visit_records_for_group_paginated(
    session: Session,
    *,
    newest_record_id: str,
    oldest_record_id: str,
    page: int,
    page_size: int,
    path: str | None = None,
    ip: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    include_bots: bool = True,
) -> tuple[list[VisitRecord], int]:
    newest = session.get(VisitRecord, newest_record_id)
    oldest = session.get(VisitRecord, oldest_record_id)
    if newest is None or oldest is None or newest.ip_address != oldest.ip_address:
        return [], 0

    boundary_ids = {newest_record_id, oldest_record_id}
    visible_boundary_count = (
        _apply_visit_filters(
            session.query(VisitRecord.id),
            path=path,
            ip=ip,
            date_from=date_from,
            date_to=date_to,
            include_bots=include_bots,
        )
        .filter(VisitRecord.id.in_(boundary_ids))
        .count()
    )
    if visible_boundary_count != len(boundary_ids):
        return [], 0

    query = _apply_visit_filters(
        session.query(VisitRecord),
        path=path,
        ip=ip,
        date_from=date_from,
        date_to=date_to,
        include_bots=include_bots,
    ).filter(
        VisitRecord.ip_address == newest.ip_address,
        _visit_record_boundary_filter(newest, oldest),
    )
    total = query.count()
    items = list(query.order_by(*_visit_order_columns()).offset((page - 1) * page_size).limit(page_size).all())
    return items, total


def count_visit_records_since(session: Session, *, since: datetime, include_bots: bool = False) -> int:
    query = session.query(func.count(VisitRecord.id)).filter(VisitRecord.visited_at >= since)
    if not include_bots:
        query = query.filter(VisitRecord.is_bot.is_(False))
    return query.scalar() or 0


def count_unique_visitors_since(session: Session, *, since: datetime, include_bots: bool = False) -> int:
    # Prefer the monthly-rotating visitor fingerprint; fall back to IP for legacy
    # rows that predate the fingerprint column.
    identity = func.coalesce(VisitRecord.visitor_id, VisitRecord.ip_address)
    query = session.query(func.count(func.distinct(identity))).filter(VisitRecord.visited_at >= since)
    if not include_bots:
        query = query.filter(VisitRecord.is_bot.is_(False))
    return query.scalar() or 0


def _visit_breakdown(
    session: Session,
    *,
    column,
    since: datetime,
    limit: int,
    include_bots: bool = False,
) -> list[tuple[str, int]]:
    query = session.query(column, func.count(VisitRecord.id).label("count")).filter(
        VisitRecord.visited_at >= since,
        column.isnot(None),
        column != "",
    )
    if not include_bots:
        query = query.filter(VisitRecord.is_bot.is_(False))
    query = query.group_by(column).order_by(func.count(VisitRecord.id).desc(), column.asc()).limit(limit)
    return [(label, count) for label, count in query.all()]


def list_visit_device_breakdown(
    session: Session, *, since: datetime, limit: int = 10, include_bots: bool = False
) -> list[tuple[str, int]]:
    return _visit_breakdown(
        session, column=VisitRecord.device_type, since=since, limit=limit, include_bots=include_bots
    )


def list_visit_browser_breakdown(
    session: Session, *, since: datetime, limit: int = 10, include_bots: bool = False
) -> list[tuple[str, int]]:
    return _visit_breakdown(session, column=VisitRecord.browser, since=since, limit=limit, include_bots=include_bots)


def list_visit_referrer_breakdown(
    session: Session, *, since: datetime, limit: int = 10, include_bots: bool = False
) -> list[tuple[str, int]]:
    return _visit_breakdown(
        session, column=VisitRecord.referer_domain, since=since, limit=limit, include_bots=include_bots
    )


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


def count_successful_visit_records_by_paths(session: Session, *, paths: list[str]) -> dict[str, int]:
    if not paths:
        return {}

    rows = (
        session.query(VisitRecord.path, func.count(VisitRecord.id).label("views"))
        .filter(
            VisitRecord.path.in_(paths),
            VisitRecord.status_code < 400,
            VisitRecord.is_bot.is_(False),
        )
        .group_by(VisitRecord.path)
        .all()
    )
    return {str(path): int(views) for path, views in rows}


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
    return normalize_shanghai_datetime(value)


def delete_visit_records_before(session: Session, *, before: datetime) -> int:
    return session.query(VisitRecord).filter(VisitRecord.visited_at < before).delete()
