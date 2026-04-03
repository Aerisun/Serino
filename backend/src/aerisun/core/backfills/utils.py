from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from aerisun.domain.exceptions import ResourceNotFound
from aerisun.domain.ops.config_revisions import capture_config_resource, create_config_revision
from aerisun.domain.ops.models import AuditLog

_MISSING = object()


def capture_optional_resource(session: Session, resource_key: str) -> Any:
    try:
        return capture_config_resource(session, resource_key)
    except ResourceNotFound:
        return _MISSING


def capture_resource_snapshots(session: Session, resource_keys: tuple[str, ...]) -> dict[str, Any]:
    return {resource_key: capture_optional_resource(session, resource_key) for resource_key in resource_keys}


def create_backfill_config_revisions(
    session: Session,
    *,
    resource_keys: tuple[str, ...],
    before_snapshots: dict[str, Any],
    summary: str,
) -> list[str]:
    changed_resources: list[str] = []
    for resource_key in resource_keys:
        before_snapshot = before_snapshots.get(resource_key, _MISSING)
        after_snapshot = capture_optional_resource(session, resource_key)
        if before_snapshot is _MISSING and after_snapshot is _MISSING:
            continue
        if before_snapshot == after_snapshot:
            continue
        create_config_revision(
            session,
            actor_id=None,
            resource_key=resource_key,
            operation="backfill",
            before_snapshot=None if before_snapshot is _MISSING else before_snapshot,
            after_snapshot=None if after_snapshot is _MISSING else after_snapshot,
            summary_override=f"升级数据回填：{summary}",
            commit=False,
        )
        changed_resources.append(resource_key)
    return changed_resources


def create_backfill_audit_log(
    session: Session,
    *,
    migration_key: str,
    summary: str,
    changed_resources: list[str],
) -> AuditLog:
    log = AuditLog(
        actor_type="system",
        actor_id=None,
        action="DATA BACKFILL APPLY",
        target_type="data_migration",
        target_id=None,
        payload={
            "migration_key": migration_key,
            "summary": summary,
            "changed_resources": changed_resources,
        },
    )
    session.add(log)
    return log
