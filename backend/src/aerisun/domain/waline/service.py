from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from aerisun.core.settings import get_settings

WALINE_GUESTBOOK_PATH = "/guestbook"
WALINE_REACTION_COLUMNS = tuple(f"reaction{index}" for index in range(9))


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
    avatar_key: str | None
    avatar_url: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class WalineCounterStats:
    url: str = ""
    pageview_count: int = 0
    reaction_count: int = 0


@dataclass(slots=True)
class WalineNickIdentity:
    nick_key: str
    nick: str
    mail: str
    created_at: datetime
    updated_at: datetime


def get_waline_db_path() -> Path:
    settings = get_settings()
    return settings.waline_db_path


def _to_sql_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")
    if isinstance(value, str):
        return value
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.isoformat(sep=" ", timespec="seconds")


def _parse_sql_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _normalize_status(value: str | None) -> str:
    normalized = (value or "waiting").strip().lower()
    if normalized in {"approved", "waiting", "spam"}:
        return normalized
    if normalized == "pending":
        return "waiting"
    if normalized == "rejected":
        return "spam"
    return "waiting"


def normalize_comment_nick(value: str | None) -> str:
    return " ".join((value or "").strip().split()).casefold()


def normalize_comment_mail(value: str | None) -> str:
    return (value or "").strip().lower()


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


def _build_list_order(sort: str | None) -> str:
    normalized = (sort or "").strip().lower()
    if normalized == "created_asc":
        return "insertedAt ASC, id ASC"
    if normalized == "status":
        return "status ASC, insertedAt DESC, id DESC"
    if normalized == "path":
        return "url ASC, insertedAt DESC, id DESC"
    return "insertedAt DESC, id DESC"


def _sqlite_table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


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

        CREATE TABLE IF NOT EXISTS wl_comment_identity (
            nick_key TEXT PRIMARY KEY NOT NULL,
            nick VARCHAR(255) NOT NULL DEFAULT '',
            mail VARCHAR(255) NOT NULL DEFAULT '',
            createdAt TEXT DEFAULT CURRENT_TIMESTAMP,
            updatedAt TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_wl_comment_identity_mail
            ON wl_comment_identity (mail);
        """
    )

    comment_columns = _sqlite_table_columns(connection, "wl_comment")
    if "avatar" not in comment_columns:
        connection.execute("ALTER TABLE wl_comment ADD COLUMN avatar VARCHAR(255) DEFAULT NULL")
    if "avatar_key" not in comment_columns:
        connection.execute("ALTER TABLE wl_comment ADD COLUMN avatar_key VARCHAR(80) DEFAULT NULL")


def _row_to_record(row: sqlite3.Row) -> WalineCommentRecord:
    columns = set(row.keys())
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
        avatar_key=str(row["avatar_key"]) if "avatar_key" in columns and row["avatar_key"] else None,
        avatar_url=str(row["avatar"]) if "avatar" in columns and row["avatar"] else None,
        created_at=_parse_sql_timestamp(row["createdAt"]),
        updated_at=_parse_sql_timestamp(row["updatedAt"]),
    )


def _row_to_identity(row: sqlite3.Row) -> WalineNickIdentity:
    return WalineNickIdentity(
        nick_key=str(row["nick_key"]),
        nick=str(row["nick"] or ""),
        mail=str(row["mail"] or ""),
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
    keyword: str | None = None,
    author: str | None = None,
    email: str | None = None,
    path: str | None = None,
    surface: str | None = None,
    sort: str | None = None,
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

        if keyword:
            where.append("comment LIKE ?")
            params.append(f"%{keyword.strip()}%")

        if author:
            where.append("nick LIKE ?")
            params.append(f"%{author.strip()}%")

        if email:
            where.append("mail LIKE ?")
            params.append(f"%{email.strip()}%")

        if path:
            where.append("url LIKE ?")
            params.append(f"%{path.strip()}%")

        if surface and not guestbook_only:
            normalized_surface = surface.strip().strip("/")
            if normalized_surface:
                where.append("url LIKE ?")
                params.append(f"/{normalized_surface}/%")

        query = "SELECT * FROM wl_comment"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += f" ORDER BY {_build_list_order(sort)} LIMIT ? OFFSET ?"

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
    keyword: str | None = None,
    author: str | None = None,
    email: str | None = None,
    path: str | None = None,
    sort: str | None = None,
) -> tuple[list[WalineCommentRecord], int]:
    return list_waline_records(
        db_path=db_path,
        page=page,
        page_size=page_size,
        status=status,
        guestbook_only=True,
        keyword=keyword,
        author=author,
        email=email,
        path=path,
        sort=sort,
    )


def list_records_for_url(
    *,
    url: str,
    db_path: Path | None = None,
    status: str | None = None,
    order: str = "asc",
) -> list[WalineCommentRecord]:
    normalized_order = "ASC" if order.lower() == "asc" else "DESC"

    with connect_waline_db(db_path) as connection:
        where = ["url = ?"]
        params: list[object] = [url]
        if status:
            where.append("status = ?")
            params.append(_normalize_status(status))

        query = "SELECT * FROM wl_comment WHERE " + " AND ".join(where)
        query += f" ORDER BY insertedAt {normalized_order}, id {normalized_order}"
        rows = connection.execute(query, params).fetchall()
        return [_row_to_record(row) for row in rows]


def list_all_waline_records(
    *,
    db_path: Path | None = None,
    status: str | None = None,
    guestbook_only: bool = False,
) -> list[WalineCommentRecord]:
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
        query += " ORDER BY insertedAt DESC, id DESC"

        rows = connection.execute(query, params).fetchall()
        return [_row_to_record(row) for row in rows]


def count_records_by_urls(
    *,
    urls: list[str],
    db_path: Path | None = None,
    status: str | None = None,
) -> dict[str, int]:
    if not urls:
        return {}

    with connect_waline_db(db_path) as connection:
        placeholders = ",".join("?" for _ in urls)
        params: list[object] = [*urls]
        query = f"SELECT url, COUNT(*) AS total FROM wl_comment WHERE url IN ({placeholders})"
        if status:
            query += " AND status = ?"
            params.append(_normalize_status(status))
        query += " GROUP BY url"

        rows = connection.execute(query, params).fetchall()
        return {str(row["url"]): int(row["total"]) for row in rows}


def get_counter_stats_by_urls(
    *,
    urls: list[str],
    db_path: Path | None = None,
) -> dict[str, WalineCounterStats]:
    if not urls:
        return {}

    reaction_sum = " + ".join(f"COALESCE({column}, 0)" for column in WALINE_REACTION_COLUMNS)

    with connect_waline_db(db_path) as connection:
        placeholders = ",".join("?" for _ in urls)
        rows = connection.execute(
            f"""
            SELECT
                url,
                SUM(COALESCE(time, 0)) AS pageview_count,
                SUM({reaction_sum}) AS reaction_count
            FROM wl_counter
            WHERE url IN ({placeholders})
            GROUP BY url
            """,
            urls,
        ).fetchall()
        return {
            str(row["url"]): WalineCounterStats(
                url=str(row["url"]),
                pageview_count=int(row["pageview_count"] or 0),
                reaction_count=int(row["reaction_count"] or 0),
            )
            for row in rows
        }


def list_counter_stats(
    *,
    db_path: Path | None = None,
    exclude_guestbook: bool = False,
) -> list[WalineCounterStats]:
    reaction_sum = " + ".join(f"COALESCE({column}, 0)" for column in WALINE_REACTION_COLUMNS)
    query = f"""
        SELECT
            url,
            SUM(COALESCE(time, 0)) AS pageview_count,
            SUM({reaction_sum}) AS reaction_count
        FROM wl_counter
    """
    params: list[object] = []
    if exclude_guestbook:
        query += " WHERE url != ?"
        params.append(WALINE_GUESTBOOK_PATH)
    query += " GROUP BY url ORDER BY pageview_count DESC, url ASC"

    with connect_waline_db(db_path) as connection:
        rows = connection.execute(query, params).fetchall()
        return [
            WalineCounterStats(
                url=str(row["url"]),
                pageview_count=int(row["pageview_count"] or 0),
                reaction_count=int(row["reaction_count"] or 0),
            )
            for row in rows
        ]


def set_counter_value(
    *,
    url: str,
    pageview_count: int,
    reaction_counts: dict[int, int] | None = None,
    db_path: Path | None = None,
) -> None:
    reaction_counts = reaction_counts or {}
    columns = ["url", "time", *WALINE_REACTION_COLUMNS]
    placeholders = ", ".join("?" for _ in columns)
    values = [url, pageview_count, *[reaction_counts.get(index, 0) for index in range(9)]]

    with connect_waline_db(db_path) as connection:
        connection.execute("DELETE FROM wl_counter WHERE url = ?", (url,))
        connection.execute(
            f"""
            INSERT INTO wl_counter ({", ".join(columns)}, createdAt, updatedAt)
            VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            values,
        )
        connection.commit()


def list_counter_history_by_date(
    *,
    db_path: Path | None = None,
) -> dict[date, dict[str, WalineCounterStats]]:
    reaction_sum = " + ".join(f"COALESCE({column}, 0)" for column in WALINE_REACTION_COLUMNS)
    with connect_waline_db(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                DATE(updatedAt) AS snapshot_date,
                url,
                SUM(COALESCE(time, 0)) AS pageview_count,
                SUM({reaction_sum}) AS reaction_count
            FROM wl_counter
            GROUP BY DATE(updatedAt), url
            ORDER BY DATE(updatedAt) ASC, url ASC
            """
        ).fetchall()

    history: dict[date, dict[str, WalineCounterStats]] = {}
    for row in rows:
        snapshot_date = date.fromisoformat(str(row["snapshot_date"]))
        history.setdefault(snapshot_date, {})[str(row["url"])] = WalineCounterStats(
            url=str(row["url"]),
            pageview_count=int(row["pageview_count"] or 0),
            reaction_count=int(row["reaction_count"] or 0),
        )
    return history


def get_waline_record_by_id(
    *,
    record_id: int,
    db_path: Path | None = None,
) -> WalineCommentRecord | None:
    with connect_waline_db(db_path) as connection:
        row = connection.execute("SELECT * FROM wl_comment WHERE id = ?", (record_id,)).fetchone()
        return _row_to_record(row) if row is not None else None


def get_waline_nick_identity(
    *,
    nick: str,
    db_path: Path | None = None,
) -> WalineNickIdentity | None:
    nick_key = normalize_comment_nick(nick)
    if not nick_key:
        return None

    with connect_waline_db(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM wl_comment_identity WHERE nick_key = ?",
            (nick_key,),
        ).fetchone()
        return _row_to_identity(row) if row is not None else None


def upsert_waline_nick_identity(
    *,
    nick: str,
    mail: str,
    db_path: Path | None = None,
) -> WalineNickIdentity:
    nick_key = normalize_comment_nick(nick)
    normalized_mail = normalize_comment_mail(mail)
    if not nick_key:
        raise ValueError("Comment nickname cannot be empty")
    if not normalized_mail:
        raise ValueError("Comment email cannot be empty")

    display_nick = " ".join(nick.strip().split())

    with connect_waline_db(db_path) as connection:
        connection.execute(
            """
            INSERT INTO wl_comment_identity (nick_key, nick, mail, createdAt, updatedAt)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(nick_key) DO UPDATE SET
                nick = excluded.nick,
                mail = excluded.mail,
                updatedAt = CURRENT_TIMESTAMP
            """,
            (nick_key, display_nick, normalized_mail),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM wl_comment_identity WHERE nick_key = ?",
            (nick_key,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Failed to persist Waline nick identity")
        return _row_to_identity(row)


def update_waline_comment_avatars(
    *,
    assignments: dict[int, tuple[str, str]],
    db_path: Path | None = None,
) -> None:
    if not assignments:
        return

    with connect_waline_db(db_path) as connection:
        connection.executemany(
            """
            UPDATE wl_comment
            SET avatar_key = ?, avatar = ?, updatedAt = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            [(avatar_key, avatar_url, record_id) for record_id, (avatar_key, avatar_url) in assignments.items()],
        )
        connection.commit()


def sync_site_user_comment_profile(
    *,
    site_user_id: str,
    nick: str,
    avatar_url: str,
    db_path: Path | None = None,
) -> int:
    avatar_key = f"site-user-{site_user_id}"
    display_nick = " ".join((nick or "").strip().split())
    if not avatar_key or not display_nick or not avatar_url.strip():
        return 0

    with connect_waline_db(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE wl_comment
            SET nick = ?, avatar = ?, updatedAt = CURRENT_TIMESTAMP
            WHERE avatar_key = ?
            """,
            (display_nick, avatar_url.strip(), avatar_key),
        )
        connection.commit()
        return int(cursor.rowcount or 0)


def sync_admin_comment_profile(
    *,
    nick: str,
    avatar_url: str,
    db_path: Path | None = None,
) -> int:
    display_nick = " ".join((nick or "").strip().split())
    if not display_nick or not avatar_url.strip():
        return 0

    with connect_waline_db(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE wl_comment
            SET nick = ?, avatar = ?, updatedAt = CURRENT_TIMESTAMP
            WHERE avatar_key = ?
            """,
            (display_nick, avatar_url.strip(), "site-admin"),
        )
        connection.commit()
        return int(cursor.rowcount or 0)


def create_waline_record(
    *,
    comment: str,
    nick: str,
    mail: str | None,
    link: str | None,
    status: str,
    url: str,
    parent_id: int | None = None,
    avatar_key: str | None = None,
    avatar_url: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    inserted_at: datetime | None = None,
    db_path: Path | None = None,
) -> WalineCommentRecord:
    with connect_waline_db(db_path) as connection:
        root_id = parent_id
        if parent_id is not None:
            root_row = connection.execute("SELECT rid FROM wl_comment WHERE id = ?", (parent_id,)).fetchone()
            root_id = int(root_row["rid"]) if root_row and root_row["rid"] is not None else parent_id

        row = make_waline_comment_row(
            comment=comment,
            nick=nick,
            mail=mail,
            link=link,
            status=status,
            url=url,
            parent_id=parent_id,
            root_id=root_id,
            avatar_key=avatar_key,
            avatar_url=avatar_url,
            created_at=created_at,
            updated_at=updated_at,
            inserted_at=inserted_at,
        )
        cursor = connection.execute(
            """
            INSERT INTO wl_comment (
                user_id, comment, insertedAt, ip, link, mail, nick, pid, rid,
                sticky, status, "like", ua, url, avatar, avatar_key, createdAt, updatedAt
            ) VALUES (
                :user_id, :comment, :insertedAt, :ip, :link, :mail, :nick, :pid, :rid,
                :sticky, :status, :like, :ua, :url, :avatar, :avatar_key, :createdAt, :updatedAt
            )
            """,
            row,
        )
        comment_id = int(cursor.lastrowid)
        if parent_id is None:
            connection.execute("UPDATE wl_comment SET rid = ? WHERE id = ?", (comment_id, comment_id))
        connection.commit()

        created = connection.execute("SELECT * FROM wl_comment WHERE id = ?", (comment_id,)).fetchone()
        if created is None:
            raise RuntimeError("Failed to create Waline record")
        return _row_to_record(created)


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
    avatar_key: str | None = None,
    avatar_url: str | None = None,
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
        "avatar": avatar_url,
        "avatar_key": avatar_key,
        "createdAt": _to_sql_timestamp(created_at),
        "updatedAt": _to_sql_timestamp(updated_at),
    }


def parse_comment_path(url: str) -> tuple[str, str]:
    return _build_comment_url_path(url)


def build_comment_path(content_type: str, content_slug: str) -> str:
    return _build_comment_path(content_type, content_slug)
