from __future__ import annotations

from sqlalchemy import func, select

from aerisun.core.db import get_session_factory
from aerisun.core.seed import seed_reference_data
from aerisun.core.settings import get_settings
from aerisun.domain.engagement.models import Comment, GuestbookEntry
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
    session_factory = get_session_factory()
    settings = get_settings()

    def snapshot() -> dict[str, object]:
        session = session_factory()
        try:
            root_comment = (
                session.query(Comment)
                .filter(
                    Comment.content_type == "posts",
                    Comment.content_slug == "from-zero-design-system",
                    Comment.parent_id.is_(None),
                )
                .one()
            )
            reply_comment = (
                session.query(Comment)
                .filter(
                    Comment.content_type == "posts",
                    Comment.content_slug == "from-zero-design-system",
                    Comment.parent_id == root_comment.id,
                )
                .one()
            )
            return {
                "legacy_comment_count": session.scalar(select(func.count(Comment.id))) or 0,
                "legacy_guestbook_count": session.scalar(select(func.count(GuestbookEntry.id))) or 0,
                "legacy_root_id": root_comment.id,
                "legacy_root_author": root_comment.author_name,
                "legacy_reply_author": reply_comment.author_name,
                "legacy_reply_parent_id": reply_comment.parent_id,
            }
        finally:
            session.close()

    def waline_snapshot() -> dict[str, int]:
        with connect_waline_db(settings.waline_db_path) as connection:
            total = connection.execute("SELECT COUNT(*) FROM wl_comment").fetchone()
            approved_guestbook = connection.execute(
                "SELECT COUNT(*) FROM wl_comment WHERE url = '/guestbook' AND status = 'approved'"
            ).fetchone()
            return {
                "waline_comment_count": int(total[0]) if total else 0,
                "waline_guestbook_approved_count": int(approved_guestbook[0]) if approved_guestbook else 0,
            }

    before = {**snapshot(), **waline_snapshot()}
    root_id = before["legacy_root_id"]
    assert before == {
        "legacy_comment_count": 4,
        "legacy_guestbook_count": 2,
        "legacy_root_id": root_id,
        "legacy_root_author": "林小北",
        "legacy_reply_author": "Felix",
        "legacy_reply_parent_id": root_id,
        "waline_comment_count": 6,
        "waline_guestbook_approved_count": 1,
    }

    seed_reference_data()

    after = {**snapshot(), **waline_snapshot()}
    assert after == before
