from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

DATA_MIGRATIONS_TABLE = "_aerisun_data_migrations"
BOOTSTRAP_MIGRATION_KEY = "bootstrap_seed_v1"


def ensure_data_migration_table(session: Session) -> None:
    session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {DATA_MIGRATIONS_TABLE} (
                migration_key VARCHAR(120) PRIMARY KEY NOT NULL,
                kind VARCHAR(32) NOT NULL,
                applied_at DATETIME NOT NULL
            )
            """
        )
    )
    session.flush()


def list_applied_data_migrations(session: Session, *, kind: str | None = None) -> set[str]:
    ensure_data_migration_table(session)
    if kind is None:
        rows = session.execute(text(f"SELECT migration_key FROM {DATA_MIGRATIONS_TABLE}"))
    else:
        rows = session.execute(
            text(f"SELECT migration_key FROM {DATA_MIGRATIONS_TABLE} WHERE kind = :kind"),
            {"kind": kind},
        )
    return {str(row[0]) for row in rows}


def record_data_migration(session: Session, *, migration_key: str, kind: str) -> bool:
    ensure_data_migration_table(session)
    if migration_key in list_applied_data_migrations(session):
        return False
    session.execute(
        text(
            f"""
            INSERT INTO {DATA_MIGRATIONS_TABLE} (migration_key, kind, applied_at)
            VALUES (:migration_key, :kind, :applied_at)
            """
        ),
        {
            "migration_key": migration_key,
            "kind": kind,
            "applied_at": datetime.now(UTC),
        },
    )
    session.flush()
    return True


def mark_bootstrap_seed_applied(session: Session) -> bool:
    return record_data_migration(
        session,
        migration_key=BOOTSTRAP_MIGRATION_KEY,
        kind="bootstrap",
    )


def clear_data_migration_records(session: Session) -> None:
    ensure_data_migration_table(session)
    session.execute(text(f"DELETE FROM {DATA_MIGRATIONS_TABLE}"))
    session.flush()
