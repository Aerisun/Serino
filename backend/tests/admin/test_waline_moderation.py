from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3

import bcrypt

from aerisun.db import get_session_factory
from aerisun.models import AdminSession, AdminUser
from aerisun.settings import get_settings
from aerisun.waline import connect_waline_db


def _create_admin_token(username: str = "waline-admin") -> str:
    session_factory = get_session_factory()
    token = "waline-admin-session-token"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    with session_factory() as session:
        user = session.query(AdminUser).filter(AdminUser.username == username).first()
        if user is None:
            user = AdminUser(
                username=username,
                password_hash=bcrypt.hashpw(b"waline-password", bcrypt.gensalt()).decode(),
            )
            session.add(user)
            session.flush()

        existing = (
            session.query(AdminSession)
            .filter(AdminSession.session_token == token)
            .first()
        )
        if existing is None:
            session.add(
                AdminSession(
                    admin_user_id=user.id,
                    session_token=token,
                    expires_at=expires_at,
                )
            )
        else:
            existing.expires_at = expires_at
        session.commit()

    return token


def _seed_waline_comment(
    connection: sqlite3.Connection,
    *,
    url: str,
    nick: str,
    comment: str,
    status: str,
    created_at: str,
    mail: str | None = None,
    link: str | None = None,
    pid: int | None = None,
    rid: int | None = None,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO wl_comment (
            user_id, comment, insertedAt, ip, link, mail, nick, pid, rid,
            sticky, status, "like", ua, url, createdAt, updatedAt
        ) VALUES (
            NULL, ?, ?, '', ?, ?, ?, ?, ?,
            NULL, ?, 0, '', ?, ?, ?
        )
        """,
        (
            comment,
            created_at,
            link,
            mail,
            nick,
            pid,
            rid,
            status,
            url,
            created_at,
            created_at,
        ),
    )
    return int(cursor.lastrowid)


def test_admin_moderation_uses_waline_storage(client) -> None:
    token = _create_admin_token()
    settings = get_settings()
    waline_db = settings.waline_db_path

    with connect_waline_db(waline_db) as connection:
        connection.execute("DELETE FROM wl_comment")
        root_id = _seed_waline_comment(
            connection,
            url="/posts/from-zero-design-system",
            nick="Reader One",
            comment="Great article.",
            status="approved",
            created_at="2026-03-21 10:00:00",
            mail="reader@example.com",
        )
        reply_id = _seed_waline_comment(
            connection,
            url="/posts/from-zero-design-system",
            nick="Author",
            comment="Thanks for reading.",
            status="approved",
            created_at="2026-03-21 10:05:00",
            pid=root_id,
            rid=root_id,
        )
        guestbook_id = _seed_waline_comment(
            connection,
            url="/guestbook",
            nick="Visitor",
            comment="Hello from the guestbook.",
            status="waiting",
            created_at="2026-03-21 11:00:00",
            link="https://visitor.example.com",
        )
        connection.commit()

    response = client.get(
        "/api/v1/admin/moderation/comments?status=approved",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert any(item["content_type"] == "posts" and item["parent_id"] is None for item in payload["items"])
    assert any(item["content_type"] == "posts" and item["parent_id"] == str(root_id) for item in payload["items"])

    response = client.post(
        f"/api/v1/admin/moderation/comments/{reply_id}/moderate",
        headers={"Authorization": f"Bearer {token}"},
        json={"action": "reject", "reason": "spam"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    with connect_waline_db(waline_db) as connection:
        row = connection.execute("SELECT status FROM wl_comment WHERE id = ?", (reply_id,)).fetchone()
        assert row is not None
        assert row["status"] == "spam"

    response = client.get(
        "/api/v1/admin/moderation/guestbook?status=pending",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == str(guestbook_id)
    assert payload["items"][0]["website"] == "https://visitor.example.com"

    response = client.post(
        f"/api/v1/admin/moderation/guestbook/{guestbook_id}/moderate",
        headers={"Authorization": f"Bearer {token}"},
        json={"action": "delete", "reason": "cleanup"},
    )
    assert response.status_code == 204

    with connect_waline_db(waline_db) as connection:
        rows = connection.execute(
            "SELECT id FROM wl_comment WHERE url = '/guestbook'"
        ).fetchall()
        assert rows == []
