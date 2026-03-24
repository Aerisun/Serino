from __future__ import annotations

from aerisun.core.db import get_session_factory
from aerisun.core.seed import seed_reference_data
from aerisun.core.settings import get_settings
from aerisun.domain.site_config.models import PageCopy
from aerisun.domain.waline.service import connect_waline_db


def test_seed_reference_data_backfills_missing_activity_page(client) -> None:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        session.query(PageCopy).filter(PageCopy.page_key == "activity").delete()
        session.commit()
    finally:
        session.close()

    seed_reference_data()

    session = session_factory()
    try:
        activity_page = session.query(PageCopy).filter(PageCopy.page_key == "activity").one()
        assert activity_page.title == "友邻与最近动态"
        assert activity_page.extras["dashboardLabel"] == "Dashboard"
    finally:
        session.close()


def test_seed_reference_data_merges_missing_page_copy_extras(client) -> None:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        friends_page = session.query(PageCopy).filter(PageCopy.page_key == "friends").one()
        friends_page.title = "Custom Friends"
        friends_page.extras = {"circle_title": "Custom Circle"}
        session.commit()
    finally:
        session.close()

    seed_reference_data()

    session = session_factory()
    try:
        friends_page = session.query(PageCopy).filter(PageCopy.page_key == "friends").one()
        assert friends_page.title == "Custom Friends"
        assert friends_page.extras["circle_title"] == "Custom Circle"
        assert friends_page.extras["statusLabel"] == "状态"
    finally:
        session.close()


def test_seed_reference_data_updates_legacy_calendar_weekday_order(client) -> None:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        calendar_page = session.query(PageCopy).filter(PageCopy.page_key == "calendar").one()
        calendar_page.extras = {
            **(calendar_page.extras or {}),
            "weekdayLabels": ["周日", "周一", "周二", "周三", "周四", "周五", "周六"],
        }
        session.commit()
    finally:
        session.close()

    seed_reference_data()

    session = session_factory()
    try:
        calendar_page = session.query(PageCopy).filter(PageCopy.page_key == "calendar").one()
        assert calendar_page.extras["weekdayLabels"] == [
            "周一",
            "周二",
            "周三",
            "周四",
            "周五",
            "周六",
            "周日",
        ]
    finally:
        session.close()


def test_seed_reference_data_provides_comment_samples_and_is_idempotent(client) -> None:
    settings = get_settings()

    def waline_snapshot() -> dict[str, object]:
        with connect_waline_db(settings.waline_db_path) as connection:
            total = connection.execute("SELECT COUNT(*) FROM wl_comment").fetchone()
            approved_guestbook = connection.execute(
                "SELECT COUNT(*) FROM wl_comment WHERE url = '/guestbook' AND status = 'approved'"
            ).fetchone()
            root_comment = connection.execute(
                """
                SELECT nick, url
                FROM wl_comment
                WHERE url = '/posts/from-zero-design-system' AND pid IS NULL
                ORDER BY id ASC
                LIMIT 1
                """
            ).fetchone()
            reply_comment = connection.execute(
                """
                SELECT nick, pid
                FROM wl_comment
                WHERE url = '/posts/from-zero-design-system' AND pid IS NOT NULL
                ORDER BY id ASC
                LIMIT 1
                """
            ).fetchone()
            return {
                "waline_comment_count": int(total[0]) if total else 0,
                "waline_guestbook_approved_count": int(approved_guestbook[0]) if approved_guestbook else 0,
                "waline_root_author": str(root_comment["nick"]) if root_comment else "",
                "waline_root_url": str(root_comment["url"]) if root_comment else "",
                "waline_reply_author": str(reply_comment["nick"]) if reply_comment else "",
                "waline_reply_has_parent": bool(reply_comment and reply_comment["pid"]),
            }

    before = waline_snapshot()
    assert before == {
        "waline_comment_count": 6,
        "waline_guestbook_approved_count": 1,
        "waline_root_author": "林小北",
        "waline_root_url": "/posts/from-zero-design-system",
        "waline_reply_author": "Felix",
        "waline_reply_has_parent": True,
    }

    seed_reference_data()

    after = waline_snapshot()
    assert after == before


def test_seed_reference_data_force_reseeds_waline_rows(client) -> None:
    settings = get_settings()

    with connect_waline_db(settings.waline_db_path) as connection:
        connection.execute("DELETE FROM wl_comment")
        connection.execute("DELETE FROM wl_counter")
        connection.execute(
            "INSERT INTO wl_comment (comment, nick, status, url) VALUES (?, ?, ?, ?)",
            ("temporary comment", "Temp", "approved", "/temporary"),
        )
        connection.commit()

    seed_reference_data(force=True)

    with connect_waline_db(settings.waline_db_path) as connection:
        total = connection.execute("SELECT COUNT(*) FROM wl_comment").fetchone()
        temp = connection.execute("SELECT COUNT(*) FROM wl_comment WHERE url = '/temporary'").fetchone()

    assert int(total[0]) == 6
    assert int(temp[0]) == 0
