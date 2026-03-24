from __future__ import annotations

import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.settings import get_settings
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.iam.schemas import ApiKeyAdminRead, ApiKeyCreate, ApiKeyCreateResponse, ApiKeyUpdate
from aerisun.domain.iam.service import (
    create_api_key as _create_api_key,
)
from aerisun.domain.iam.service import (
    delete_api_key as _delete_api_key,
)
from aerisun.domain.iam.service import (
    list_api_keys as _list_api_keys,
)
from aerisun.domain.iam.service import (
    update_api_key as _update_api_key,
)
from aerisun.domain.media.models import Asset
from aerisun.domain.ops.models import AuditLog, BackupSnapshot
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

from .deps import get_current_admin
from .schemas import PaginatedResponse

router = APIRouter(prefix="/system", tags=["admin-system"])

_STARTUP_TIME = time.time()


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------


@router.get("/api-keys", response_model=list[ApiKeyAdminRead], summary="获取 API 密钥列表")
def list_api_keys(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return _list_api_keys(session)


@router.post(
    "/api-keys", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED, summary="创建 API 密钥"
)
def create_api_key(
    payload: ApiKeyCreate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return _create_api_key(session, payload.key_name, payload.scopes)


@router.put("/api-keys/{key_id}", response_model=ApiKeyAdminRead, summary="更新 API 密钥")
def update_api_key(
    key_id: str,
    payload: ApiKeyUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    try:
        return _update_api_key(session, key_id, payload)
    except LookupError:
        raise HTTPException(status_code=404, detail="API key not found")


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除 API 密钥")
def delete_api_key(
    key_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    try:
        _delete_api_key(session, key_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="API key not found")


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------


@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogRead], summary="获取审计日志")
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
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
    items = q.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [AuditLogRead.model_validate(a) for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------


@router.get("/backups", response_model=list[BackupSnapshotRead], summary="获取备份列表")
def list_backups(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    snapshots = session.query(BackupSnapshot).order_by(BackupSnapshot.created_at.desc()).all()
    return [BackupSnapshotRead.model_validate(s) for s in snapshots]


@router.post("/backups", response_model=BackupSnapshotRead, status_code=status.HTTP_201_CREATED, summary="创建备份快照")
def trigger_backup(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    settings = get_settings()
    snapshot = BackupSnapshot(
        snapshot_type="manual",
        status="queued",
        db_path=str(settings.db_path),
        replica_url=settings.litestream_replica_url,
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return BackupSnapshotRead.model_validate(snapshot)


@router.post("/backups/{snapshot_id}/restore", response_model=BackupSnapshotRead, summary="从备份恢复")
def restore_backup(
    snapshot_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    snapshot = session.get(BackupSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Backup snapshot not found")
    snapshot.status = "restoring"
    session.commit()
    session.refresh(snapshot)
    return BackupSnapshotRead.model_validate(snapshot)


# ---------------------------------------------------------------------------
# Dashboard Stats
# ---------------------------------------------------------------------------


@router.get("/dashboard/stats", response_model=EnhancedDashboardStats, summary="获取仪表盘统计")
def dashboard_stats(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> EnhancedDashboardStats:
    posts_count = session.query(func.count(PostEntry.id)).scalar() or 0
    diary_count = session.query(func.count(DiaryEntry.id)).scalar() or 0
    thoughts_count = session.query(func.count(ThoughtEntry.id)).scalar() or 0
    excerpts_count = session.query(func.count(ExcerptEntry.id)).scalar() or 0

    status_rows = session.query(PostEntry.status, func.count(PostEntry.id)).group_by(PostEntry.status).all()
    posts_by_status = {s: c for s, c in status_rows}

    now = datetime.now(UTC)
    six_months_ago = now - timedelta(days=180)

    month_data: dict[str, dict[str, int]] = {}
    content_type_map = [
        (PostEntry, "posts"),
        (DiaryEntry, "diary"),
        (ThoughtEntry, "thoughts"),
        (ExcerptEntry, "excerpts"),
    ]
    for model, type_key in content_type_map:
        rows = (
            session.query(func.strftime("%Y-%m", model.created_at), func.count(model.id))
            .filter(model.created_at >= six_months_ago)
            .group_by(func.strftime("%Y-%m", model.created_at))
            .all()
        )
        for month_str, count in rows:
            if month_str not in month_data:
                month_data[month_str] = {"posts": 0, "diary": 0, "thoughts": 0, "excerpts": 0}
            month_data[month_str][type_key] = count

    content_by_month = sorted(
        [MonthlyCount(month=m, **counts) for m, counts in month_data.items()],
        key=lambda x: x.month,
    )

    recent_items: list[RecentContentItem] = []
    recent_type_map = [
        (PostEntry, "post"),
        (DiaryEntry, "diary"),
        (ThoughtEntry, "thought"),
        (ExcerptEntry, "excerpt"),
    ]
    for model, type_key in recent_type_map:
        rows = session.query(model).order_by(model.updated_at.desc()).limit(5).all()
        for row in rows:
            recent_items.append(
                RecentContentItem(
                    id=row.id, title=row.title, content_type=type_key, status=row.status, updated_at=row.updated_at
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
        friends=session.query(func.count(Friend.id)).scalar() or 0,
        assets=session.query(func.count(Asset.id)).scalar() or 0,
        posts_by_status=posts_by_status,
        content_by_month=content_by_month,
        recent_content=recent_content,
    )


# ---------------------------------------------------------------------------
# System Info
# ---------------------------------------------------------------------------


@router.get("/info", response_model=SystemInfo, summary="获取系统信息")
def system_info(
    _admin: AdminUser = Depends(get_current_admin),
) -> SystemInfo:
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
