from __future__ import annotations

import logging

from sqlalchemy import inspect

from aerisun.core.backfills.registry import REGISTERED_BACKFILLS
from aerisun.core.backfills.state import (
    ensure_data_migration_table,
    list_applied_data_migrations,
    record_data_migration,
)
from aerisun.core.backfills.utils import (
    capture_resource_snapshots,
    create_backfill_audit_log,
    create_backfill_config_revisions,
)
from aerisun.core.db import get_session_factory

logger = logging.getLogger("aerisun.backfill")


_BACKFILL_REQUIRED_TABLES = (
    "site_profile",
    "resume_basics",
    "community_config",
    "page_copy",
)


def _schema_ready_for_backfills(session) -> bool:
    engine = session.get_bind()
    inspector = inspect(engine)
    missing = [table for table in _BACKFILL_REQUIRED_TABLES if not inspector.has_table(table)]
    if missing:
        logger.warning(
            "Skipping data backfills because schema is not ready yet (missing tables: %s)",
            ", ".join(missing),
        )
        return False
    return True


def run_pending_backfills() -> list[str]:
    session_factory = get_session_factory()
    applied_migrations: list[str] = []
    with session_factory() as session:
        if not _schema_ready_for_backfills(session):
            return []
        ensure_data_migration_table(session)
        bootstrap_records = list_applied_data_migrations(session, kind="bootstrap")
        completed = list_applied_data_migrations(session, kind="backfill")
        if bootstrap_records and not completed:
            for spec in REGISTERED_BACKFILLS:
                record_data_migration(
                    session,
                    migration_key=spec.migration_key,
                    kind="backfill",
                )
            session.commit()
            logger.info("Bootstrap baseline detected; marked existing backfills as already satisfied")
            return []
        for spec in REGISTERED_BACKFILLS:
            if spec.migration_key in completed:
                continue

            logger.info("Applying data backfill %s", spec.migration_key)
            before_snapshots = capture_resource_snapshots(session, spec.resource_keys)
            try:
                spec.apply(session)
                session.flush()
                changed_resources = create_backfill_config_revisions(
                    session,
                    resource_keys=spec.resource_keys,
                    before_snapshots=before_snapshots,
                    summary=spec.summary,
                )
                create_backfill_audit_log(
                    session,
                    migration_key=spec.migration_key,
                    summary=spec.summary,
                    changed_resources=changed_resources,
                )
                record_data_migration(
                    session,
                    migration_key=spec.migration_key,
                    kind="backfill",
                )
                session.commit()
                completed.add(spec.migration_key)
                applied_migrations.append(spec.migration_key)
            except Exception:
                session.rollback()
                logger.exception("Failed to apply data backfill %s", spec.migration_key)
                raise
    return applied_migrations
