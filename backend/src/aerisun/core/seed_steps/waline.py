from __future__ import annotations

import logging

from aerisun.domain.waline.service import connect_waline_db, make_waline_comment_row


def clear_waline_seed_data() -> None:
    logger = logging.getLogger("aerisun.seed")
    logger.info("Force reseed: clearing existing Waline seed data...")
    with connect_waline_db() as connection:
        connection.execute("DELETE FROM wl_comment")
        connection.execute("DELETE FROM wl_counter")
        connection.execute("DELETE FROM sqlite_sequence WHERE name IN ('wl_comment', 'wl_counter')")
        connection.commit()


def insert_waline_seed_comment(connection, item: dict[str, object], inserted_ids: dict[str, int]) -> int:  # type: ignore[no-untyped-def]
    parent_key = item.get("parent_key")
    parent_id = inserted_ids.get(str(parent_key)) if parent_key else None
    root_id = parent_id
    if parent_id is not None:
        root_row = connection.execute("SELECT rid FROM wl_comment WHERE id = ?", (parent_id,)).fetchone()
        root_id = int(root_row["rid"]) if root_row and root_row["rid"] is not None else parent_id

    row = make_waline_comment_row(
        comment=str(item["comment"]),
        nick=str(item["nick"]),
        mail=str(item["mail"]) if item.get("mail") is not None else None,
        link=str(item["link"]) if item.get("link") is not None else None,
        status=str(item["status"]),
        url=str(item["url"]),
        parent_id=parent_id,
        root_id=root_id,
        created_at=item["created_at"],  # type: ignore[arg-type]
        updated_at=item["created_at"],  # type: ignore[arg-type]
        inserted_at=item["created_at"],  # type: ignore[arg-type]
    )
    cursor = connection.execute(
        """
        INSERT INTO wl_comment (
            user_id, comment, insertedAt, ip, link, mail, nick, pid, rid,
            sticky, status, "like", ua, url, createdAt, updatedAt
        ) VALUES (
            :user_id, :comment, :insertedAt, :ip, :link, :mail, :nick, :pid, :rid,
            :sticky, :status, :like, :ua, :url, :createdAt, :updatedAt
        )
        """,
        row,
    )
    comment_id = int(cursor.lastrowid)
    if parent_id is None:
        connection.execute("UPDATE wl_comment SET rid = ? WHERE id = ?", (comment_id, comment_id))
    inserted_ids[str(item["key"])] = comment_id
    return comment_id


def seed_waline_comment_data(*, default_waline_comments: list[dict[str, object]]) -> None:
    with connect_waline_db() as connection:
        existing = connection.execute("SELECT COUNT(*) FROM wl_comment").fetchone()
        if existing and int(existing[0]) > 0:
            return

        inserted_ids: dict[str, int] = {}
        for item in default_waline_comments:
            insert_waline_seed_comment(connection, item, inserted_ids)

        connection.commit()


def seed_waline_counter_data(*, default_waline_counters: list[dict[str, object]]) -> None:
    with connect_waline_db() as connection:
        existing = connection.execute("SELECT COUNT(*) FROM wl_counter").fetchone()
        if existing and int(existing[0]) > 0:
            return

        for item in default_waline_counters:
            connection.execute(
                """
                INSERT INTO wl_counter (
                    time, reaction0, reaction1, reaction2, reaction3, reaction4,
                    reaction5, reaction6, reaction7, reaction8, url
                ) VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0, ?)
                """,
                (int(item["time"]), int(item["reaction0"]), str(item["url"])),
            )

        connection.commit()
