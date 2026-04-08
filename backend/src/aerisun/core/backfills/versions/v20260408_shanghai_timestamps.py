from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from sqlalchemy import DateTime, text
from sqlalchemy.orm import Session

from aerisun.core.base import Base
from aerisun.core.settings import get_settings
from aerisun.core.time import normalize_shanghai_datetime

migration_key = "20260408_shanghai_timestamps"
summary = "将内部记录时间统一回填为上海时区"
resource_keys: tuple[str, ...] = ()

_WALINE_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "wl_comment": ("insertedAt", "createdAt", "updatedAt"),
    "wl_counter": ("createdAt", "updatedAt"),
    "wl_users": ("createdAt", "updatedAt"),
}


def _parse_legacy_datetime(value: object) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            parsed = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")

    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _format_shanghai_datetime(value: datetime) -> str:
    return normalize_shanghai_datetime(value).isoformat(sep=" ")


def _normalize_main_db(session: Session) -> None:
    connection = session.connection()
    for table in Base.metadata.sorted_tables:
        datetime_columns = [column.name for column in table.columns if isinstance(column.type, DateTime)]
        if not datetime_columns:
            continue

        quoted_columns = ", ".join(f'"{column}"' for column in datetime_columns)
        rows = connection.exec_driver_sql(f'SELECT rowid, {quoted_columns} FROM "{table.name}"').mappings()
        for row in rows:
            updates: dict[str, str] = {}
            for column_name in datetime_columns:
                parsed = _parse_legacy_datetime(row.get(column_name))
                if parsed is None:
                    continue
                normalized = _format_shanghai_datetime(parsed)
                if str(row.get(column_name)) != normalized:
                    updates[column_name] = normalized

            if not updates:
                continue

            set_clause = ", ".join(f'"{column}" = :{column}' for column in updates)
            connection.execute(
                text(f'UPDATE "{table.name}" SET {set_clause} WHERE rowid = :rowid'),
                {"rowid": row["rowid"], **updates},
            )


def _normalize_waline_db() -> None:
    waline_db_path = get_settings().waline_db_path
    if not waline_db_path.exists():
        return

    connection = sqlite3.connect(waline_db_path)
    connection.row_factory = sqlite3.Row
    try:
        for table_name, column_names in _WALINE_TABLE_COLUMNS.items():
            exists = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
            if exists is None:
                continue

            available_columns = {
                str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            target_columns = [column for column in column_names if column in available_columns]
            if not target_columns:
                continue

            quoted_columns = ", ".join(f'"{column}"' for column in target_columns)
            rows = connection.execute(f'SELECT rowid, {quoted_columns} FROM "{table_name}"').fetchall()
            for row in rows:
                updates: dict[str, str] = {}
                for column_name in target_columns:
                    parsed = _parse_legacy_datetime(row[column_name])
                    if parsed is None:
                        continue
                    normalized = _format_shanghai_datetime(parsed)
                    if str(row[column_name]) != normalized:
                        updates[column_name] = normalized

                if not updates:
                    continue

                set_clause = ", ".join(f'"{column}" = ?' for column in updates)
                connection.execute(
                    f'UPDATE "{table_name}" SET {set_clause} WHERE rowid = ?',
                    [*updates.values(), row["rowid"]],
                )
        connection.commit()
    finally:
        connection.close()


def apply(session: Session) -> None:
    _normalize_main_db(session)
    _normalize_waline_db()
