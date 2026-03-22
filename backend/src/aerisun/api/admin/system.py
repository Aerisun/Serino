from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.models import (
    AdminUser,
    ApiKey,
    Asset,
    AuditLog,
    BackupSnapshot,
    DiaryEntry,
    ExcerptEntry,
    Friend,
    PostEntry,
    ThoughtEntry,
)
from aerisun.domain.waline.service import count_waline_records

from .deps import get_current_admin
from .schemas import (
    ApiKeyAdminRead,
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyUpdate,
    AuditLogRead,
    BackupSnapshotRead,
    DashboardStats,
)

router = APIRouter(prefix="/system", tags=["admin-system"])


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

@router.get("/api-keys", response_model=list[ApiKeyAdminRead])
def list_api_keys(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    keys = session.query(ApiKey).order_by(ApiKey.created_at.desc()).all()
    return [ApiKeyAdminRead.model_validate(k) for k in keys]


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    raw_secret = secrets.token_urlsafe(48)
    prefix = raw_secret[:8]
    hashed = bcrypt.hashpw(raw_secret.encode(), bcrypt.gensalt()).decode()

    key = ApiKey(
        key_name=payload.key_name,
        key_prefix=prefix,
        hashed_secret=hashed,
        scopes=payload.scopes,
    )
    session.add(key)
    session.commit()
    session.refresh(key)
    return ApiKeyCreateResponse(
        item=ApiKeyAdminRead.model_validate(key),
        raw_key=raw_secret,
    )


@router.put("/api-keys/{key_id}", response_model=ApiKeyAdminRead)
def update_api_key(
    key_id: str,
    payload: ApiKeyUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    key = session.get(ApiKey, key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(key, k, v)
    session.commit()
    session.refresh(key)
    return ApiKeyAdminRead.model_validate(key)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_key(
    key_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    key = session.get(ApiKey, key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    session.delete(key)
    session.commit()


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------

@router.get("/audit-logs", response_model=dict)
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    q = session.query(AuditLog)
    total = q.count()
    items = (
        q.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [AuditLogRead.model_validate(a) for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------

@router.get("/backups", response_model=list[BackupSnapshotRead])
def list_backups(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    snapshots = session.query(BackupSnapshot).order_by(BackupSnapshot.created_at.desc()).all()
    return [BackupSnapshotRead.model_validate(s) for s in snapshots]


@router.post("/backups", response_model=BackupSnapshotRead, status_code=status.HTTP_201_CREATED)
def trigger_backup(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    from aerisun.core.settings import get_settings

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


@router.post("/backups/{snapshot_id}/restore", response_model=BackupSnapshotRead)
def restore_backup(
    snapshot_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    snapshot = session.get(BackupSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Backup snapshot not found")
    # Mark as restoring (actual restore would be handled by a background job)
    snapshot.status = "restoring"
    session.commit()
    session.refresh(snapshot)
    return BackupSnapshotRead.model_validate(snapshot)


# ---------------------------------------------------------------------------
# Dashboard Stats
# ---------------------------------------------------------------------------

@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> DashboardStats:
    return DashboardStats(
        posts=session.query(func.count(PostEntry.id)).scalar() or 0,
        diary_entries=session.query(func.count(DiaryEntry.id)).scalar() or 0,
        thoughts=session.query(func.count(ThoughtEntry.id)).scalar() or 0,
        excerpts=session.query(func.count(ExcerptEntry.id)).scalar() or 0,
        comments=count_waline_records(),
        guestbook_entries=count_waline_records(guestbook_only=True),
        friends=session.query(func.count(Friend.id)).scalar() or 0,
        assets=session.query(func.count(Asset.id)).scalar() or 0,
    )
