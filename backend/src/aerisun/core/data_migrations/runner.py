from __future__ import annotations

import logging

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
from aerisun.core.db import get_session_factory
from aerisun.core.production_baseline import PRODUCTION_BASELINE_ID

logger = logging.getLogger("aerisun.data_migrations")


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
                "failed": bucket("blocking", "failed"),
            },
            "background": {
                "applied": bucket("background", "applied"),
                "pending": pending("background"),
                "scheduled": bucket("background", "scheduled"),
                "running": bucket("background", "running"),
                "failed": bucket("background", "failed"),
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


def apply_pending_data_migrations(*, mode: str) -> list[str]:
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
                continue
            if journal_entry is not None and journal_entry.status == "running":
                continue

            logger.info("Applying data migration %s", spec.migration_key)
            before_snapshots = capture_resource_snapshots(session, spec.resource_keys)
            try:
                mark_data_migration_running(
                    session,
                    migration_key=spec.migration_key,
                    schema_revision=spec.schema_revision,
                    mode=spec.mode,
                    checksum=spec.checksum,
                )
                spec.apply(session)
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
                applied.append(spec.migration_key)
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
    return applied


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
