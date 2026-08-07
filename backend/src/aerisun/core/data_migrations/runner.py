from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from aerisun.core.data_migrations.registry import DataMigrationSpec, get_registered_data_migrations
from aerisun.core.data_migrations.schema import get_current_schema_revision, get_head_revisions, revision_is_reachable
from aerisun.core.data_migrations.state import (
    ensure_migration_journal,
    get_migration_entry,
    list_migration_entries,
    mark_data_migration_applied,
    mark_data_migration_failed,
    mark_data_migration_running,
    mark_data_migration_scheduled,
)
from aerisun.core.data_migrations.utils import (
    capture_resource_snapshots,
    create_data_migration_audit_log,
    create_data_migration_config_revisions,
)
from aerisun.core.data_storage_lock import exclusive_data_storage_lock
from aerisun.core.db import get_session_factory
from aerisun.core.production_baseline import PRODUCTION_BASELINE_ID

logger = logging.getLogger("aerisun.data_migrations")
ResultT = TypeVar("ResultT")


def _locked(operation: Callable[..., ResultT]) -> Callable[..., ResultT]:
    @wraps(operation)
    def wrapped(*args: Any, **kwargs: Any) -> ResultT:
        with exclusive_data_storage_lock():
            return operation(*args, **kwargs)

    return wrapped


def _reachable_specs(current_revision: str | None) -> tuple[DataMigrationSpec, ...]:
    return tuple(
        spec
        for spec in get_registered_data_migrations()
        if revision_is_reachable(spec.schema_revision, current_revision)
    )


def collect_migration_status() -> dict[str, object]:
    session_factory = get_session_factory()
    with session_factory() as session:
        ensure_migration_journal(session)
        current_revision = get_current_schema_revision(session)
        heads = list(get_head_revisions())
        entries = list_migration_entries(session)
        baseline_entry = entries.get(PRODUCTION_BASELINE_ID)
        reachable = _reachable_specs(current_revision)

        def bucket(mode: str, status: str) -> list[str]:
            return [
                spec.migration_key
                for spec in reachable
                if spec.mode == mode
                and entries.get(spec.migration_key) is not None
                and entries[spec.migration_key].status == status
            ]

        def pending(mode: str) -> list[str]:
            return [
                spec.migration_key
                for spec in reachable
                if spec.mode == mode and entries.get(spec.migration_key) is None
            ]

        return {
            "current_revision": current_revision,
            "head_revisions": heads,
            "baseline": None
            if baseline_entry is None
            else {
                "migration_key": baseline_entry.migration_key,
                "schema_revision": baseline_entry.schema_revision,
                "status": baseline_entry.status,
                "applied_at": None if baseline_entry.applied_at is None else baseline_entry.applied_at.isoformat(),
            },
            "blocking": {
                "applied": bucket("blocking", "applied"),
                "pending": pending("blocking"),
                "running": bucket("blocking", "running"),
                "failed": bucket("blocking", "failed"),
                "cleanup_pending": [
                    spec.migration_key
                    for spec in reachable
                    if spec.mode == "blocking"
                    and entries.get(spec.migration_key) is not None
                    and entries[spec.migration_key].status == "applied"
                    and spec.cleanup_pending is not None
                    and spec.cleanup_pending()
                ],
            },
            "background": {
                "applied": bucket("background", "applied"),
                "pending": pending("background"),
                "scheduled": bucket("background", "scheduled"),
                "running": bucket("background", "running"),
                "failed": bucket("background", "failed"),
                "cleanup_pending": [
                    spec.migration_key
                    for spec in reachable
                    if spec.mode == "background"
                    and entries.get(spec.migration_key) is not None
                    and entries[spec.migration_key].status == "applied"
                    and spec.cleanup_pending is not None
                    and spec.cleanup_pending()
                ],
            },
            "registered": [
                {
                    "migration_key": spec.migration_key,
                    "schema_revision": spec.schema_revision,
                    "mode": spec.mode,
                    "summary": spec.summary,
                }
                for spec in get_registered_data_migrations()
            ],
        }


@_locked
def apply_pending_data_migrations(
    *,
    mode: str,
    on_applied: Callable[[DataMigrationSpec], None] | None = None,
    defer_cleanup: bool = False,
) -> list[str]:
    if mode not in {"blocking", "background", "all"}:
        raise ValueError(f"Unsupported data migration mode: {mode}")

    session_factory = get_session_factory()
    applied: list[str] = []
    with session_factory() as session:
        ensure_migration_journal(session)
        current_revision = get_current_schema_revision(session)
        if current_revision is None:
            raise RuntimeError("Cannot apply data migrations before schema migrations are installed.")

        for spec in _reachable_specs(current_revision):
            if mode != "all" and spec.mode != mode:
                continue

            journal_entry = get_migration_entry(session, spec.migration_key)
            if journal_entry is not None and journal_entry.status == "applied":
                if spec.cleanup is not None and not defer_cleanup:
                    spec.cleanup(session)
                    session.commit()
                continue
            resume_finalize = (
                journal_entry is not None and journal_entry.status == "running" and spec.finalize is not None
            )
            if journal_entry is not None and journal_entry.status == "running" and not resume_finalize:
                continue

            logger.info(
                "%s data migration %s",
                "Finalizing" if resume_finalize else "Applying",
                spec.migration_key,
            )
            before_snapshots = {} if resume_finalize else capture_resource_snapshots(session, spec.resource_keys)
            try:
                if not resume_finalize:
                    mark_data_migration_running(
                        session,
                        migration_key=spec.migration_key,
                        schema_revision=spec.schema_revision,
                        mode=spec.mode,
                        checksum=spec.checksum,
                    )
                    spec.apply(session)
                    session.flush()
                    if spec.finalize is not None:
                        session.commit()

                if spec.finalize is not None:
                    spec.finalize(session)
                    session.flush()
                changed_resources = create_data_migration_config_revisions(
                    session,
                    resource_keys=spec.resource_keys,
                    before_snapshots=before_snapshots,
                    summary=spec.summary,
                )
                create_data_migration_audit_log(
                    session,
                    migration_key=spec.migration_key,
                    summary=spec.summary,
                    mode=spec.mode,
                    changed_resources=changed_resources,
                )
                mark_data_migration_applied(
                    session,
                    migration_key=spec.migration_key,
                    schema_revision=spec.schema_revision,
                    mode=spec.mode,
                    checksum=spec.checksum,
                )
                session.commit()
            except Exception as exc:
                session.rollback()
                with session_factory() as error_session:
                    ensure_migration_journal(error_session)
                    mark_data_migration_failed(
                        error_session,
                        migration_key=spec.migration_key,
                        schema_revision=spec.schema_revision,
                        mode=spec.mode,
                        checksum=spec.checksum,
                        error=str(exc),
                    )
                    error_session.commit()
                logger.exception("Failed to apply data migration %s", spec.migration_key)
                raise
            applied.append(spec.migration_key)
            if spec.cleanup is not None and not defer_cleanup:
                spec.cleanup(session)
                session.commit()
            if on_applied is not None:
                on_applied(spec)
    return applied


@_locked
def cleanup_applied_data_migrations(*, mode: str) -> list[str]:
    if mode not in {"blocking", "background", "all"}:
        raise ValueError(f"Unsupported data migration mode: {mode}")

    session_factory = get_session_factory()
    cleaned: list[str] = []
    with session_factory() as session:
        ensure_migration_journal(session)
        current_revision = get_current_schema_revision(session)
        if current_revision is None:
            raise RuntimeError("Cannot clean data migrations before schema migrations are installed.")
        for spec in _reachable_specs(current_revision):
            if mode != "all" and spec.mode != mode:
                continue
            entry = get_migration_entry(session, spec.migration_key)
            if entry is None or entry.status != "applied" or spec.cleanup is None:
                continue
            spec.cleanup(session)
            session.commit()
            cleaned.append(spec.migration_key)
    return cleaned


@_locked
def rollback_external_data_migrations(*, mode: str) -> list[str]:
    if mode not in {"blocking", "background", "all"}:
        raise ValueError(f"Unsupported data migration mode: {mode}")

    session_factory = get_session_factory()
    rolled_back: list[str] = []
    with session_factory() as session:
        ensure_migration_journal(session)
        current_revision = get_current_schema_revision(session)
        if current_revision is None:
            return rolled_back
        for spec in reversed(_reachable_specs(current_revision)):
            if mode != "all" and spec.mode != mode:
                continue
            if spec.rollback_external is None:
                continue
            spec.rollback_external(session)
            session.commit()
            rolled_back.append(spec.migration_key)
    return rolled_back


def schedule_pending_background_data_migrations() -> list[str]:
    session_factory = get_session_factory()
    scheduled: list[str] = []
    with session_factory() as session:
        ensure_migration_journal(session)
        current_revision = get_current_schema_revision(session)
        if current_revision is None:
            raise RuntimeError("Cannot schedule data migrations before schema migrations are installed.")

        for spec in _reachable_specs(current_revision):
            if spec.mode != "background":
                continue
            journal_entry = get_migration_entry(session, spec.migration_key)
            if journal_entry is not None and journal_entry.status in {"applied", "scheduled", "running"}:
                continue
            mark_data_migration_scheduled(
                session,
                migration_key=spec.migration_key,
                schema_revision=spec.schema_revision,
                mode=spec.mode,
                checksum=spec.checksum,
            )
            scheduled.append(spec.migration_key)
        session.commit()
    return scheduled
