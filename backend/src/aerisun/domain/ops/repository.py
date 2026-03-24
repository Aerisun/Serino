from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from aerisun.domain.ops.models import AuditLog, BackupSnapshot


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


def find_all_backups(session: Session) -> list[BackupSnapshot]:
    """List all backup snapshots ordered by created_at desc."""
    return list(session.query(BackupSnapshot).order_by(BackupSnapshot.created_at.desc()).all())


def create_backup(session: Session, **kwargs) -> BackupSnapshot:
    """Create a new backup snapshot. Caller must commit."""
    snapshot = BackupSnapshot(**kwargs)
    session.add(snapshot)
    return snapshot


def find_backup_by_id(session: Session, snapshot_id: str) -> BackupSnapshot | None:
    """Find a backup snapshot by ID."""
    return session.get(BackupSnapshot, snapshot_id)


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
