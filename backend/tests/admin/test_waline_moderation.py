from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

import bcrypt

from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.core.time import shanghai_now
from aerisun.domain.diary_access.models import DiaryAccessRequest
from aerisun.domain.iam.models import AdminSession, AdminUser
from aerisun.domain.media.models import Asset
from aerisun.domain.site_auth.models import SiteUser
from aerisun.domain.waline.service import connect_waline_db


def _create_admin_token(username: str = "waline-admin") -> str:
    session_factory = get_session_factory()
    token = "waline-admin-session-token"
    expires_at = shanghai_now() + timedelta(hours=24)

    with session_factory() as session:
        user = session.query(AdminUser).filter(AdminUser.username == username).first()
        if user is None:
            user = AdminUser(
                username=username,
                password_hash=bcrypt.hashpw(b"waline-password", bcrypt.gensalt()).decode(),
            )
            session.add(user)
            session.flush()

        existing = session.query(AdminSession).filter(AdminSession.session_token == token).first()
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


def test_waline_schema_marks_existing_records_as_read_on_upgrade(tmp_path: Path) -> None:
    legacy_db = tmp_path / "legacy-waline.db"
    with sqlite3.connect(legacy_db) as connection:
        connection.execute(
            """
            CREATE TABLE wl_comment (
                id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                user_id INTEGER DEFAULT NULL,
                comment TEXT,
                insertedAt TEXT NOT NULL,
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
            )
            """
        )
        connection.execute(
            """
            INSERT INTO wl_comment (
                comment, insertedAt, status, url, createdAt, updatedAt
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "已有评论",
                "2026-03-21 09:00:00",
                "approved",
                "/posts/legacy",
                "2026-03-21 09:00:00",
                "2026-03-21 09:00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO wl_comment (
                comment, insertedAt, status, url, createdAt, updatedAt
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "没有创建时间的已有评论",
                "2026-03-21 09:30:00",
                "approved",
                "/posts/legacy-without-created-at",
                None,
                "2026-03-21 09:30:00",
            ),
        )

    with connect_waline_db(legacy_db) as connection:
        rows = connection.execute("SELECT admin_read_at FROM wl_comment ORDER BY id").fetchall()

    assert [row["admin_read_at"] for row in rows] == [
        "2026-03-21 09:00:00",
        "2026-03-21 09:30:00",
    ]


def test_waline_schema_provisions_moderation_and_visitor_lookup_indexes(tmp_path: Path) -> None:
    with connect_waline_db(tmp_path / "waline.db") as connection:
        indexes = {str(row["name"]) for row in connection.execute("PRAGMA index_list(wl_comment)").fetchall()}

    assert "idx_wl_comment_attention" in indexes
    assert "idx_wl_comment_avatar_key" in indexes


def test_waline_connections_reuse_the_verified_schema_for_the_same_database(tmp_path: Path, monkeypatch) -> None:
    from aerisun.domain.waline import service as waline_service

    original_ensure = waline_service.ensure_waline_schema
    ensure_calls = 0

    def track_ensure(connection: sqlite3.Connection) -> None:
        nonlocal ensure_calls
        ensure_calls += 1
        original_ensure(connection)

    monkeypatch.setattr(waline_service, "ensure_waline_schema", track_ensure)
    db_path = tmp_path / "cached-schema-waline.db"

    with waline_service.connect_waline_db(db_path):
        pass
    with waline_service.connect_waline_db(db_path):
        pass

    assert ensure_calls == 1


def test_admin_moderation_tracks_shared_read_state_and_attention_counts(client) -> None:
    token = _create_admin_token("waline-read-state-admin")
    headers = {"Authorization": f"Bearer {token}"}
    settings = get_settings()

    with connect_waline_db(settings.waline_db_path) as connection:
        connection.execute("DELETE FROM wl_comment")
        comment_id = _seed_waline_comment(
            connection,
            url="/friends",
            nick="Friend applicant",
            comment="可以交换友链吗？",
            status="waiting",
            created_at="2026-03-21 11:00:00",
        )
        guestbook_id = _seed_waline_comment(
            connection,
            url="/guestbook",
            nick="Guest visitor",
            comment="来留言。",
            status="waiting",
            created_at="2026-03-21 11:05:00",
        )

    session_factory = get_session_factory()
    with session_factory() as session:
        session.query(DiaryAccessRequest).delete()
        visitor = SiteUser(
            email="attention-counts@example.com",
            display_name="Attention visitor",
            avatar_url="",
        )
        session.add(visitor)
        session.flush()
        diary_request = DiaryAccessRequest(
            site_user_id=visitor.id,
            reason="申请查看私密日记",
            status="pending",
        )
        session.add(diary_request)
        session.flush()
        diary_request_id = diary_request.id
        session.commit()

    comments = client.get("/api/v1/admin/moderation/comments", headers=headers)
    assert comments.status_code == 200
    assert comments.json()["items"][0]["is_read"] is False

    attention = client.get("/api/v1/admin/moderation/attention-counts", headers=headers)
    assert attention.status_code == 200
    assert attention.json() == {
        "comments": {"pending": 1, "unread": 1},
        "guestbook": {"pending": 1, "unread": 1},
        "diary_access": {"pending": 1},
        "pending_total": 3,
        "unread_total": 3,
    }

    comment_read = client.patch(
        "/api/v1/admin/moderation/comments/read",
        headers=headers,
        json={"ids": [str(comment_id)]},
    )
    assert comment_read.status_code == 200
    assert comment_read.json() == {"marked": 1}

    repeat_comment_read = client.patch(
        "/api/v1/admin/moderation/comments/read",
        headers=headers,
        json={"ids": [str(comment_id)]},
    )
    assert repeat_comment_read.status_code == 200
    assert repeat_comment_read.json() == {"marked": 0}

    refreshed_comments = client.get("/api/v1/admin/moderation/comments", headers=headers)
    assert refreshed_comments.status_code == 200
    assert refreshed_comments.json()["items"][0]["is_read"] is True

    guestbook_read = client.patch(
        "/api/v1/admin/moderation/guestbook/read",
        headers=headers,
        json={"ids": [str(guestbook_id)]},
    )
    assert guestbook_read.status_code == 200
    assert guestbook_read.json() == {"marked": 1}

    refreshed_attention = client.get("/api/v1/admin/moderation/attention-counts", headers=headers)
    assert refreshed_attention.status_code == 200
    assert refreshed_attention.json()["comments"]["unread"] == 1
    assert refreshed_attention.json()["guestbook"]["unread"] == 1
    assert refreshed_attention.json()["pending_total"] == 3
    assert refreshed_attention.json()["unread_total"] == 3

    diary_review = client.patch(
        f"/api/v1/admin/moderation/diary-access-requests/{diary_request_id}",
        headers=headers,
        json={"grant_access": False},
    )
    assert diary_review.status_code == 200
    assert diary_review.json()["status"] == "revoked"

    reviewed_attention = client.get("/api/v1/admin/moderation/attention-counts", headers=headers)
    assert reviewed_attention.status_code == 200
    assert reviewed_attention.json()["diary_access"] == {"pending": 0}
    assert reviewed_attention.json()["unread_total"] == 2


def test_admin_moderation_filters_friend_comments_by_their_exact_path(client) -> None:
    token = _create_admin_token("waline-friends-filter-admin")
    settings = get_settings()

    with connect_waline_db(settings.waline_db_path) as connection:
        connection.execute("DELETE FROM wl_comment")
        _seed_waline_comment(
            connection,
            url="/friends",
            nick="Friend applicant",
            comment="希望交换友链。",
            status="waiting",
            created_at="2026-03-21 11:10:00",
        )

    response = client.get(
        "/api/v1/admin/moderation/comments?surface=friends",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["content_type"] == "friends"


def test_pending_diary_access_request_counts_as_unread_until_approved(client) -> None:
    token = _create_admin_token("diary-access-approval-marks-read-admin")
    headers = {"Authorization": f"Bearer {token}"}
    settings = get_settings()

    with connect_waline_db(settings.waline_db_path) as connection:
        connection.execute("DELETE FROM wl_comment")

    session_factory = get_session_factory()
    with session_factory() as session:
        session.query(DiaryAccessRequest).delete()
        visitor = SiteUser(
            email="diary-approval-attention@example.com",
            display_name="Diary approval visitor",
            avatar_url="",
        )
        session.add(visitor)
        session.flush()
        diary_request = DiaryAccessRequest(
            site_user_id=visitor.id,
            reason="申请查看私密日记",
            status="pending",
        )
        session.add(diary_request)
        session.flush()
        diary_request_id = diary_request.id
        session.commit()

    before = client.get("/api/v1/admin/moderation/attention-counts", headers=headers)
    assert before.status_code == 200
    assert before.json()["diary_access"] == {"pending": 1}
    assert before.json()["unread_total"] == 1

    response = client.patch(
        f"/api/v1/admin/moderation/diary-access-requests/{diary_request_id}",
        headers=headers,
        json={"grant_access": True},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    after = client.get("/api/v1/admin/moderation/attention-counts", headers=headers)
    assert after.status_code == 200
    assert after.json()["diary_access"] == {"pending": 0}
    assert after.json()["unread_total"] == 0


def test_moderating_an_unread_comment_marks_it_read(client) -> None:
    token = _create_admin_token("waline-moderation-marks-read-admin")
    headers = {"Authorization": f"Bearer {token}"}
    settings = get_settings()

    with connect_waline_db(settings.waline_db_path) as connection:
        connection.execute("DELETE FROM wl_comment")
        comment_id = _seed_waline_comment(
            connection,
            url="/posts/moderation-read-state",
            nick="Pending reader",
            comment="请审核这条评论。",
            status="waiting",
            created_at="2026-03-21 11:20:00",
        )

    before = client.get("/api/v1/admin/moderation/attention-counts", headers=headers)
    assert before.status_code == 200
    assert before.json()["comments"] == {"pending": 1, "unread": 1}

    response = client.post(
        f"/api/v1/admin/moderation/comments/{comment_id}/moderate",
        headers=headers,
        json={"action": "approve"},
    )

    assert response.status_code == 200
    assert response.json()["is_read"] is True

    after = client.get("/api/v1/admin/moderation/attention-counts", headers=headers)
    assert after.status_code == 200
    assert after.json()["comments"] == {"pending": 0, "unread": 0}


def test_moderating_an_unread_guestbook_entry_marks_it_read(client) -> None:
    token = _create_admin_token("waline-guestbook-moderation-marks-read-admin")
    headers = {"Authorization": f"Bearer {token}"}
    settings = get_settings()

    with connect_waline_db(settings.waline_db_path) as connection:
        connection.execute("DELETE FROM wl_comment")
        entry_id = _seed_waline_comment(
            connection,
            url="/guestbook",
            nick="Pending guestbook reader",
            comment="请审核这条留言。",
            status="waiting",
            created_at="2026-03-21 11:25:00",
        )

    response = client.post(
        f"/api/v1/admin/moderation/guestbook/{entry_id}/moderate",
        headers=headers,
        json={"action": "reject"},
    )

    assert response.status_code == 200
    assert response.json()["is_read"] is True

    attention = client.get("/api/v1/admin/moderation/attention-counts", headers=headers)
    assert attention.status_code == 200
    assert attention.json()["guestbook"] == {"pending": 0, "unread": 0}


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

    filtered = client.get(
        "/api/v1/admin/moderation/comments?status=approved&author=Reader&email=reader@example.com&sort=created_asc",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["total"] == 1
    assert filtered_payload["items"][0]["author_name"] == "Reader One"
    assert filtered_payload["items"][0]["feedback_enabled"] is True
    assert filtered_payload["items"][0]["deletion_reason"] is None

    feedback_update = client.patch(
        f"/api/v1/admin/moderation/comments/{root_id}/feedback",
        headers={"Authorization": f"Bearer {token}"},
        json={"feedback_enabled": False},
    )
    assert feedback_update.status_code == 200
    assert feedback_update.json()["feedback_enabled"] is False

    with connect_waline_db(waline_db) as connection:
        row = connection.execute("SELECT feedback_enabled FROM wl_comment WHERE id = ?", (root_id,)).fetchone()
        assert row is not None
        assert row["feedback_enabled"] == 0

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
        rows = connection.execute("SELECT id FROM wl_comment WHERE url = '/guestbook'").fetchall()
        assert rows == []


def test_deleting_comment_removes_bound_comment_images(client) -> None:
    token = _create_admin_token("waline-image-cleanup-admin")
    settings = get_settings()
    resource_key = "internal/assets/comment/delete-bound.png"
    storage_path = settings.media_dir.expanduser().resolve() / resource_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")

    session_factory = get_session_factory()
    with session_factory() as session:
        session.add(
            Asset(
                file_name="delete-bound.png",
                resource_key=resource_key,
                visibility="internal",
                scope="user",
                category="comment",
                storage_path=str(storage_path),
                mime_type="image/png",
                byte_size=13,
                sha256="image-sha",
                storage_provider="local",
                remote_status="none",
                mirror_status="completed",
            )
        )
        session.commit()

    with connect_waline_db(settings.waline_db_path) as connection:
        connection.execute("DELETE FROM wl_comment")
        comment_id = _seed_waline_comment(
            connection,
            url="/posts/from-zero-design-system",
            nick="Reader",
            comment=f"![uploaded](/media/{resource_key})",
            status="approved",
            created_at="2026-03-21 12:00:00",
        )
        connection.commit()

    response = client.post(
        f"/api/v1/admin/moderation/comments/{comment_id}/moderate",
        headers={"Authorization": f"Bearer {token}"},
        json={"action": "delete", "reason": "cleanup image"},
    )

    assert response.status_code == 204
    assert not storage_path.exists()
    with session_factory() as session:
        assert session.query(Asset).filter_by(resource_key=resource_key).first() is None
