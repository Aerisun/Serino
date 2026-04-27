from __future__ import annotations

import asyncio
import contextlib
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import structlog
from sqlalchemy.orm import Session

from aerisun.core.runtime_version import get_runtime_version
from aerisun.core.settings import get_settings
from aerisun.core.time import BEIJING_TZ, beijing_today, shanghai_now
from aerisun.domain.activity.repository import batch_resolve_titles
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.media.models import Asset
from aerisun.domain.ops import repository as repo
from aerisun.domain.ops.config_revisions import (
    build_diff_lines,
    get_config_revision,
)
from aerisun.domain.ops.config_revisions import (
    list_config_revisions as _list_config_revisions,
)
from aerisun.domain.ops.config_revisions import (
    restore_config_revision as _restore_config_revision,
)
from aerisun.domain.ops.ip_geo import lookup_ip_geolocation
from aerisun.domain.ops.schemas import (
    AuditLogRead,
    ConfigDiffLineRead,
    ConfigRevisionDetailRead,
    ConfigRevisionListItemRead,
    ConfigRevisionRestoreWrite,
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
from aerisun.domain.social.models import Friend
from aerisun.domain.waline.service import count_waline_records, list_counter_history_by_date, list_counter_stats

_STARTUP_TIME = time.time()
_UPTIME_STARTED_AT_FILENAME = ".serino-uptime-started-at"
_TRAFFIC_HISTORY_DAYS = 14
_TOP_PAGES_LIMIT = 10
_DISTRIBUTION_LIMIT = 5
_VISIT_RECORD_QUEUE_MAXSIZE = 1000
_VISIT_RECORD_QUEUE_DRAIN_TIMEOUT_SECONDS = 5.0

_CONTENT_PATH_TO_TYPE: dict[str, str] = {
    "posts": "posts",
    "diary": "diary",
    "thoughts": "thoughts",
    "excerpts": "excerpts",
}

logger = structlog.get_logger("aerisun.ops")
_visit_logger = structlog.stdlib.get_logger("aerisun.ops.visit")


def _parse_uptime_started_at(raw: str, now: float) -> float | None:
    try:
        started_at = float(raw.strip())
    except ValueError:
        return None
    if started_at <= 0:
        return None
    return min(started_at, now)


def _write_uptime_started_at(marker_path: Path, now: float) -> float:
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with marker_path.open("x", encoding="utf-8") as marker:
            marker.write(f"{now:.6f}\n")
        return now
    except FileExistsError:
        raw = marker_path.read_text(encoding="utf-8")
        existing = _parse_uptime_started_at(raw, now)
        if existing is not None:
            return existing
        marker_path.write_text(f"{now:.6f}\n", encoding="utf-8")
        return now


def _get_persistent_uptime_started_at(data_dir: Path, now: float) -> float:
    marker_path = data_dir / _UPTIME_STARTED_AT_FILENAME
    try:
        raw = marker_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        pass
    except OSError:
        return _STARTUP_TIME
    else:
        started_at = _parse_uptime_started_at(raw, now)
        if started_at is not None:
            return started_at

    try:
        return _write_uptime_started_at(marker_path, now)
    except OSError:
        return _STARTUP_TIME


@dataclass(slots=True)
class VisitRecordPayload:
    visited_at: datetime
    path: str
    ip_address: str
    user_agent: str | None
    referer: str | None
    status_code: int
    duration_ms: int
    is_bot: bool


class VisitRecordQueue:
    def __init__(self, *, maxsize: int = _VISIT_RECORD_QUEUE_MAXSIZE) -> None:
        self._maxsize = maxsize
        self._queue: asyncio.Queue[VisitRecordPayload | None] | None = None
        self._worker: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._worker is not None and not self._worker.done():
            return
        self._queue = asyncio.Queue(maxsize=self._maxsize)
        self._worker = asyncio.create_task(self._run(), name="visit-record-worker")
        _visit_logger.info("visit_record_worker_started", maxsize=self._maxsize)

    async def stop(self) -> None:
        worker = self._worker
        queue = self._queue
        self._worker = None
        self._queue = None

        if worker is None:
            return

        if queue is not None:
            try:
                await asyncio.wait_for(queue.put(None), timeout=_VISIT_RECORD_QUEUE_DRAIN_TIMEOUT_SECONDS)
            except TimeoutError:
                _visit_logger.warning("visit_record_worker_stop_timeout")

        try:
            await asyncio.wait_for(worker, timeout=_VISIT_RECORD_QUEUE_DRAIN_TIMEOUT_SECONDS)
        except TimeoutError:
            _visit_logger.warning("visit_record_worker_cancelled")
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker

    def enqueue(self, payload: VisitRecordPayload) -> bool:
        queue = self._queue
        if queue is None:
            _visit_logger.warning("visit_record_worker_not_started", path=payload.path)
            return False
        try:
            queue.put_nowait(payload)
            return True
        except asyncio.QueueFull:
            _visit_logger.warning("visit_record_queue_full", path=payload.path, maxsize=self._maxsize)
            return False

    async def _run(self) -> None:
        queue = self._queue
        if queue is None:
            return

        from aerisun.core.db import get_session_factory

        session_factory = get_session_factory()
        while True:
            payload = await queue.get()
            if payload is None:
                queue.task_done()
                break
            try:
                with session_factory() as session:
                    repo.create_visit_record(
                        session,
                        visited_at=payload.visited_at,
                        path=payload.path,
                        ip_address=payload.ip_address,
                        user_agent=payload.user_agent,
                        referer=payload.referer,
                        status_code=payload.status_code,
                        duration_ms=payload.duration_ms,
                        is_bot=payload.is_bot,
                    )
                    session.commit()
            except Exception:
                _visit_logger.exception("visit_record_persist_failed", path=payload.path)
            finally:
                queue.task_done()


_visit_record_queue = VisitRecordQueue()


def enqueue_visit_record(payload: VisitRecordPayload) -> bool:
    return _visit_record_queue.enqueue(payload)


async def start_visit_record_worker() -> None:
    await _visit_record_queue.start()


async def stop_visit_record_worker() -> None:
    await _visit_record_queue.stop()


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


def list_config_revisions(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    resource_key: str | None = None,
    actor_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, object]:
    items, total = _list_config_revisions(
        session,
        page=page,
        page_size=page_size,
        resource_key=resource_key,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "items": [ConfigRevisionListItemRead.model_validate(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_config_revision_detail(session: Session, revision_id: str) -> ConfigRevisionDetailRead:
    revision = get_config_revision(session, revision_id)
    return ConfigRevisionDetailRead(
        id=revision.id,
        actor_id=revision.actor_id,
        resource_key=revision.resource_key,
        resource_label=revision.resource_label,
        operation=revision.operation,
        resource_version=revision.resource_version,
        summary=revision.summary,
        changed_fields=list(revision.changed_fields or []),
        sensitive_fields=list(revision.sensitive_fields or []),
        restored_from_revision_id=revision.restored_from_revision_id,
        created_at=revision.created_at,
        before_preview=revision.before_preview,
        after_preview=revision.after_preview,
        diff_lines=[
            ConfigDiffLineRead.model_validate(item)
            for item in build_diff_lines(revision.before_preview, revision.after_preview)
        ],
        restorable=bool(revision.before_snapshot is not None or revision.after_snapshot is not None),
    )


def restore_config_revision(
    session: Session,
    *,
    revision_id: str,
    actor_id: str | None,
    payload: ConfigRevisionRestoreWrite,
) -> ConfigRevisionDetailRead:
    revision = _restore_config_revision(
        session,
        revision_id=revision_id,
        actor_id=actor_id,
        target="after" if payload.target == "after" else "before",
        reason=payload.reason,
    )
    return get_config_revision_detail(session, revision.id)


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
    target_date = snapshot_date or beijing_today()
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

    end_date = beijing_today()
    start_date = end_date - timedelta(days=_TRAFFIC_HISTORY_DAYS - 1)
    snapshots = repo.list_traffic_snapshots_between(session, start_date=start_date, end_date=end_date)

    daily_totals: dict[date, int] = {start_date + timedelta(days=index): 0 for index in range(_TRAFFIC_HISTORY_DAYS)}
    for snapshot in snapshots:
        daily_totals[snapshot.snapshot_date] = daily_totals.get(snapshot.snapshot_date, 0) + snapshot.daily_views

    history = [TrafficTrendPoint(date=day, views=daily_totals.get(day, 0)) for day in sorted(daily_totals)]

    latest_snapshots = repo.list_latest_traffic_snapshots(session, as_of_date=end_date)
    total_views = sum(item.cumulative_views for item in latest_snapshots)

    ranked_page_urls = [item.url for item in latest_snapshots if item.url and item.url != "/guestbook"]
    resolved_titles = _resolve_content_titles_for_paths(session, ranked_page_urls)

    ranked_pages = [
        TopPageMetric(
            url=item.url,
            views=item.cumulative_views,
            share=round((item.cumulative_views / total_views), 4) if total_views else 0.0,
            title=resolved_titles.get(item.url),
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


def _extract_content_pair_from_path(path: str) -> tuple[str, str] | None:
    normalized_path = path.split("?", 1)[0].split("#", 1)[0]
    segments = [segment for segment in normalized_path.split("/") if segment]
    if len(segments) < 2:
        return None

    content_type = _CONTENT_PATH_TO_TYPE.get(segments[0])
    if content_type is None:
        return None

    slug = segments[-1]
    if not slug:
        return None
    return content_type, slug


def _resolve_content_titles_for_paths(session: Session, paths: list[str]) -> dict[str, str]:
    path_to_pair: dict[str, tuple[str, str]] = {}
    unique_pairs: set[tuple[str, str]] = set()

    for path in paths:
        pair = _extract_content_pair_from_path(path)
        if pair is None:
            continue
        path_to_pair[path] = pair
        unique_pairs.add(pair)

    if not unique_pairs:
        return {}

    resolved = batch_resolve_titles(session, list(unique_pairs))
    result: dict[str, str] = {}
    for path, pair in path_to_pair.items():
        title = resolved.get(pair)
        if title:
            result[path] = title
    return result


def _build_visitor_metrics(session: Session) -> DashboardVisitorMetrics:
    now = shanghai_now()
    history_days = 14
    start_date = now.date() - timedelta(days=history_days - 1)
    history_rows = repo.list_visit_history_by_day(session, start_date=start_date, end_date=now.date())
    history_map = {day: views for day, views in history_rows}
    history = []
    for index in range(history_days):
        current_date = start_date + timedelta(days=index)
        history.append(
            TrafficTrendPoint(
                date=current_date,
                views=history_map.get(str(current_date), 0),
            )
        )

    recent_records, _ = repo.find_visit_records_paginated(session, page=1, page_size=10)
    total_visits = repo.count_visit_records_since(session, since=datetime.fromtimestamp(0, BEIJING_TZ))
    unique_visitors_24h = repo.count_unique_visitors_since(session, since=now - timedelta(hours=24))
    unique_visitors_7d = repo.count_unique_visitors_since(session, since=now - timedelta(days=7))
    average_request_duration_ms = repo.average_visit_duration_since(session, since=now - timedelta(days=7))
    top_page_rows = repo.list_visit_top_pages(session, since=now - timedelta(days=14), limit=_TOP_PAGES_LIMIT)
    resolved_titles = _resolve_content_titles_for_paths(session, [path for path, _ in top_page_rows])
    top_total = sum(views for _, views in top_page_rows)
    top_pages = [
        TopPageMetric(
            url=path,
            views=views,
            share=round((views / top_total), 4) if top_total else 0.0,
            title=resolved_titles.get(path),
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
    deleted = repo.delete_visit_records_before(session, before=shanghai_now() - timedelta(days=retention_days))
    if deleted:
        session.commit()
    return deleted


def get_dashboard_stats(session: Session) -> EnhancedDashboardStats:
    """Aggregate dashboard statistics from all domains."""
    now = shanghai_now()
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
    now = time.time()
    uptime_started_at = _get_persistent_uptime_started_at(Path(settings.data_dir), now)

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
        version=get_runtime_version(settings),
        python_version=sys.version.split()[0],
        db_size_bytes=db_size,
        media_dir_size_bytes=media_size,
        uptime_seconds=max(0.0, now - uptime_started_at),
        environment=settings.environment,
        site_url=settings.site_url,
    )
