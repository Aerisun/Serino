from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from aerisun.core.base import utcnow

DATA_MIGRATIONS_TABLE = "_aerisun_data_migrations"


@dataclass(frozen=True, slots=True)
class MigrationJournalEntry:
    migration_key: str
    schema_revision: str
    kind: str
    mode: str
    status: str
    checksum: str
    applied_at: datetime | None
    last_error: str | None


def ensure_migration_journal(session: Session) -> None:
    session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {DATA_MIGRATIONS_TABLE} (
                migration_key VARCHAR(120) PRIMARY KEY NOT NULL,
                schema_revision VARCHAR(64) NOT NULL,
                kind VARCHAR(32) NOT NULL,
                mode VARCHAR(32) NOT NULL,
                status VARCHAR(32) NOT NULL,
                checksum VARCHAR(128) NOT NULL,
                applied_at DATETIME NULL,
                last_error TEXT NULL
            )
            """
        )
    )
    session.flush()


def list_migration_entries(session: Session) -> dict[str, MigrationJournalEntry]:
    ensure_migration_journal(session)

    def normalize_applied_at(value: object) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))

    rows = session.execute(
        text(
            f"""
            SELECT migration_key, schema_revision, kind, mode, status, checksum, applied_at, last_error
            FROM {DATA_MIGRATIONS_TABLE}
            ORDER BY kind, migration_key
            """
        )
    ).fetchall()
    return {
        str(row[0]): MigrationJournalEntry(
            migration_key=str(row[0]),
            schema_revision=str(row[1]),
            kind=str(row[2]),
            mode=str(row[3]),
            status=str(row[4]),
            checksum=str(row[5]),
            applied_at=normalize_applied_at(row[6]),
            last_error=None if row[7] is None else str(row[7]),
        )
        for row in rows
    }


def get_migration_entry(session: Session, migration_key: str) -> MigrationJournalEntry | None:
    return list_migration_entries(session).get(migration_key)


def upsert_migration_entry(
    session: Session,
    *,
    migration_key: str,
    schema_revision: str,
    kind: str,
    mode: str,
    status: str,
    checksum: str,
    applied_at: datetime | None = None,
    last_error: str | None = None,
) -> None:
    ensure_migration_journal(session)
    session.execute(
        text(
            f"""
            INSERT INTO {DATA_MIGRATIONS_TABLE} (
                migration_key,
                schema_revision,
                kind,
                mode,
                status,
                checksum,
                applied_at,
                last_error
            ) VALUES (
                :migration_key,
                :schema_revision,
                :kind,
                :mode,
                :status,
                :checksum,
                :applied_at,
                :last_error
            )
            ON CONFLICT(migration_key) DO UPDATE SET
                schema_revision = excluded.schema_revision,
                kind = excluded.kind,
                mode = excluded.mode,
                status = excluded.status,
                checksum = excluded.checksum,
                applied_at = excluded.applied_at,
                last_error = excluded.last_error
            """
        ),
        {
            "migration_key": migration_key,
            "schema_revision": schema_revision,
            "kind": kind,
            "mode": mode,
            "status": status,
            "checksum": checksum,
            "applied_at": applied_at,
            "last_error": last_error,
        },
    )
    session.flush()


def mark_baseline_applied(
    session: Session,
    *,
    migration_key: str,
    schema_revision: str,
    checksum: str,
) -> None:
    upsert_migration_entry(
        session,
        migration_key=migration_key,
        schema_revision=schema_revision,
        kind="baseline",
        mode="blocking",
        status="applied",
        checksum=checksum,
        applied_at=utcnow(),
        last_error=None,
    )


def mark_data_migration_scheduled(
    session: Session,
    *,
    migration_key: str,
    schema_revision: str,
    mode: str,
    checksum: str,
) -> None:
    upsert_migration_entry(
        session,
        migration_key=migration_key,
        schema_revision=schema_revision,
        kind="data",
        mode=mode,
        status="scheduled",
        checksum=checksum,
        applied_at=None,
        last_error=None,
    )


def mark_data_migration_running(
    session: Session,
    *,
    migration_key: str,
    schema_revision: str,
    mode: str,
    checksum: str,
) -> None:
    upsert_migration_entry(
        session,
        migration_key=migration_key,
        schema_revision=schema_revision,
        kind="data",
        mode=mode,
        status="running",
        checksum=checksum,
        applied_at=None,
        last_error=None,
    )


def mark_data_migration_applied(
    session: Session,
    *,
    migration_key: str,
    schema_revision: str,
    mode: str,
    checksum: str,
) -> None:
    upsert_migration_entry(
        session,
        migration_key=migration_key,
        schema_revision=schema_revision,
        kind="data",
        mode=mode,
        status="applied",
        checksum=checksum,
        applied_at=utcnow(),
        last_error=None,
    )


def mark_data_migration_failed(
    session: Session,
    *,
    migration_key: str,
    schema_revision: str,
    mode: str,
    checksum: str,
    error: str,
) -> None:
    upsert_migration_entry(
        session,
        migration_key=migration_key,
        schema_revision=schema_revision,
        kind="data",
        mode=mode,
        status="failed",
        checksum=checksum,
        applied_at=None,
        last_error=error,
    )


def clear_migration_journal(session: Session) -> None:
    ensure_migration_journal(session)
    session.execute(text(f"DELETE FROM {DATA_MIGRATIONS_TABLE}"))
    session.flush()
