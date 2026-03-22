from __future__ import annotations

from aerisun.core.db import get_session_factory
from aerisun.domain.site_config.models import PageCopy
from aerisun.core.seed import seed_reference_data


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
        assert calendar_page.extras["weekdayLabels"] == ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    finally:
        session.close()
