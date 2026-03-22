from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from typing import Iterator

from aerisun.settings import get_settings

WALINE_GUESTBOOK_PATH = "/guestbook"


@dataclass(slots=True)
class WalineCommentRecord:
    id: int
    user_id: int | None
    comment: str
    inserted_at: datetime
    ip: str
    link: str | None
    mail: str | None
    nick: str | None
    pid: int | None
    rid: int | None
    sticky: bool
    status: str
    like: int
    ua: str | None
    url: str
    created_at: datetime
    updated_at: datetime


def get_waline_db_path() -> Path:
    settings = get_settings()
    return settings.waline_db_path


def _to_sql_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")
    if isinstance(value, str):
        return value
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.isoformat(sep=" ", timespec="seconds")


def _parse_sql_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_status(value: str | None) -> str:
    normalized = (value or "waiting").strip().lower()
    if normalized in {"approved", "waiting", "spam"}:
        return normalized
    if normalized == "pending":
        return "waiting"
    if normalized == "rejected":
        return "spam"
    return "waiting"


def _normalize_ui_status(value: str | None) -> str:
    normalized = (value or "waiting").strip().lower()
    if normalized == "waiting":
        return "pending"
    if normalized == "spam":
        return "rejected"
    if normalized == "approved":
        return "approved"
    if normalized == "pending":
        return "pending"
    if normalized == "rejected":
        return "rejected"
    return "pending"


def _build_comment_url_path(url: str) -> tuple[str, str]:
    clean = (url or "").strip() or "/"
    if clean == WALINE_GUESTBOOK_PATH:
        return "guestbook", "guestbook"

    parts = [part for part in clean.lstrip("/").split("/", 1) if part]
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], parts[0]
    return "unknown", clean.lstrip("/") or "unknown"


def _build_comment_path(content_type: str, content_slug: str) -> str:
    if content_type == "guestbook":
        return WALINE_GUESTBOOK_PATH
    return f"/{content_type}/{content_slug}"


@contextmanager
def connect_waline_db(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or get_waline_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON;")
    ensure_waline_schema(connection)
    try:
        yield connection
    finally:
        connection.close()


def ensure_waline_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS wl_comment (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            user_id INTEGER DEFAULT NULL,
            comment TEXT,
            insertedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ip VARCHAR(100) DEFAULT '',
            link VARCHAR(255) DEFAULT NULL,
            mail VARCHAR(255) DEFAULT NULL,
            nick VARCHAR(255) DEFAULT NULL,
            pid INTEGER DEFAULT NULL,
            rid INTEGER DEFAULT NULL,
            sticky NUMERIC DEFAULT NULL,
            status VARCHAR(50) NOT NULL DEFAULT '',
            "like" INTEGER DEFAULT NULL,
            ua TEXT,
            url VARCHAR(255) NOT NULL DEFAULT '',
            createdAt TEXT DEFAULT CURRENT_TIMESTAMP,
            updatedAt TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS wl_counter (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            time INTEGER DEFAULT NULL,
            reaction0 INTEGER DEFAULT NULL,
            reaction1 INTEGER DEFAULT NULL,
            reaction2 INTEGER DEFAULT NULL,
            reaction3 INTEGER DEFAULT NULL,
            reaction4 INTEGER DEFAULT NULL,
            reaction5 INTEGER DEFAULT NULL,
            reaction6 INTEGER DEFAULT NULL,
            reaction7 INTEGER DEFAULT NULL,
            reaction8 INTEGER DEFAULT NULL,
            url VARCHAR(255) NOT NULL DEFAULT '',
            createdAt TEXT DEFAULT CURRENT_TIMESTAMP,
            updatedAt TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS wl_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            display_name VARCHAR(255) NOT NULL DEFAULT '',
            email VARCHAR(255) NOT NULL DEFAULT '',
            password VARCHAR(255) NOT NULL DEFAULT '',
            type VARCHAR(50) NOT NULL DEFAULT '',
            label VARCHAR(255) DEFAULT NULL,
            url VARCHAR(255) DEFAULT NULL,
            avatar VARCHAR(255) DEFAULT NULL,
            github VARCHAR(255) DEFAULT NULL,
            twitter VARCHAR(255) DEFAULT NULL,
            facebook VARCHAR(255) DEFAULT NULL,
            google VARCHAR(255) DEFAULT NULL,
            weibo VARCHAR(255) DEFAULT NULL,
            qq VARCHAR(255) DEFAULT NULL,
            oidc VARCHAR(255) DEFAULT NULL,
            huawei VARCHAR(255) DEFAULT NULL,
            "2fa" VARCHAR(32) DEFAULT NULL,
            createdAt TEXT DEFAULT CURRENT_TIMESTAMP,
            updatedAt TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_wl_comment_url_status_insertedAt
            ON wl_comment (url, status, insertedAt DESC);
        CREATE INDEX IF NOT EXISTS idx_wl_comment_pid
            ON wl_comment (pid);
        """
    )


def _row_to_record(row: sqlite3.Row) -> WalineCommentRecord:
    return WalineCommentRecord(
        id=int(row["id"]),
        user_id=row["user_id"],
        comment=row["comment"] or "",
        inserted_at=_parse_sql_timestamp(row["insertedAt"]),
        ip=row["ip"] or "",
        link=row["link"],
        mail=row["mail"],
        nick=row["nick"],
        pid=row["pid"],
        rid=row["rid"],
        sticky=bool(row["sticky"]) if row["sticky"] is not None else False,
        status=_normalize_ui_status(row["status"]),
        like=int(row["like"] or 0),
        ua=row["ua"],
        url=row["url"] or "",
        created_at=_parse_sql_timestamp(row["createdAt"]),
        updated_at=_parse_sql_timestamp(row["updatedAt"]),
    )


def count_waline_records(
    *,
    db_path: Path | None = None,
    status: str | None = None,
    guestbook_only: bool = False,
) -> int:
    with connect_waline_db(db_path) as connection:
        where: list[str] = []
        params: list[object] = []
        if guestbook_only:
            where.append("url = ?")
            params.append(WALINE_GUESTBOOK_PATH)
        else:
            where.append("url != ?")
            params.append(WALINE_GUESTBOOK_PATH)

        if status:
            where.append("status = ?")
            params.append(_normalize_status(status))

        query = "SELECT COUNT(*) FROM wl_comment"
        if where:
            query += " WHERE " + " AND ".join(where)
        value = connection.execute(query, params).fetchone()
        return int(value[0]) if value else 0


def list_waline_records(
    *,
    db_path: Path | None = None,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    guestbook_only: bool = False,
) -> tuple[list[WalineCommentRecord], int]:
    offset = (page - 1) * page_size
    with connect_waline_db(db_path) as connection:
        where: list[str] = []
        params: list[object] = []
        if guestbook_only:
            where.append("url = ?")
            params.append(WALINE_GUESTBOOK_PATH)
        else:
            where.append("url != ?")
            params.append(WALINE_GUESTBOOK_PATH)

        if status:
            where.append("status = ?")
            params.append(_normalize_status(status))

        query = "SELECT * FROM wl_comment"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY insertedAt DESC, id DESC LIMIT ? OFFSET ?"

        count_query = "SELECT COUNT(*) FROM wl_comment"
        if where:
            count_query += " WHERE " + " AND ".join(where)

        total_row = connection.execute(count_query, params).fetchone()
        total = int(total_row[0]) if total_row else 0

        rows = connection.execute(query, [*params, page_size, offset]).fetchall()
        return [_row_to_record(row) for row in rows], total


def list_guestbook_records(
    *,
    db_path: Path | None = None,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
) -> tuple[list[WalineCommentRecord], int]:
    return list_waline_records(
        db_path=db_path,
        page=page,
        page_size=page_size,
        status=status,
        guestbook_only=True,
    )


def _collect_descendant_ids(connection: sqlite3.Connection, root_id: int) -> list[int]:
    pending = [root_id]
    collected: list[int] = []
    seen: set[int] = set()

    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        collected.append(current)
        rows = connection.execute("SELECT id FROM wl_comment WHERE pid = ?", (current,)).fetchall()
        pending.extend(int(row["id"]) for row in rows)

    return collected


def moderate_waline_record(
    *,
    record_id: int,
    action: str,
    db_path: Path | None = None,
) -> WalineCommentRecord | None:
    with connect_waline_db(db_path) as connection:
        row = connection.execute("SELECT * FROM wl_comment WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            return None

        if action == "delete":
            ids = _collect_descendant_ids(connection, record_id)
            if ids:
                placeholders = ",".join("?" for _ in ids)
                connection.execute(
                    f"DELETE FROM wl_comment WHERE id IN ({placeholders})",
                    ids,
                )
            connection.commit()
            return _row_to_record(row)

        normalized = _normalize_status(action)
        if action == "approve":
            normalized = "approved"
        elif action == "reject":
            normalized = "spam"

        connection.execute(
            """
            UPDATE wl_comment
            SET status = ?, updatedAt = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (normalized, record_id),
        )
        connection.commit()
        updated = connection.execute("SELECT * FROM wl_comment WHERE id = ?", (record_id,)).fetchone()
        return _row_to_record(updated) if updated else None


def make_waline_comment_row(
    *,
    comment: str,
    nick: str,
    mail: str | None,
    link: str | None,
    status: str,
    url: str,
    parent_id: int | None = None,
    root_id: int | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    inserted_at: datetime | None = None,
    ip: str = "",
    ua: str = "",
) -> dict[str, object]:
    return {
        "user_id": None,
        "comment": comment,
        "insertedAt": _to_sql_timestamp(inserted_at or created_at),
        "ip": ip,
        "link": link,
        "mail": mail,
        "nick": nick,
        "pid": parent_id,
        "rid": root_id,
        "sticky": None,
        "status": _normalize_status(status),
        "like": 0,
        "ua": ua,
        "url": url,
        "createdAt": _to_sql_timestamp(created_at),
        "updatedAt": _to_sql_timestamp(updated_at),
    }


def parse_comment_path(url: str) -> tuple[str, str]:
    return _build_comment_url_path(url)


def build_comment_path(content_type: str, content_slug: str) -> str:
    return _build_comment_path(content_type, content_slug)
