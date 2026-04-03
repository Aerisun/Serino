from __future__ import annotations

import httpx
import respx

from aerisun.core.base import utcnow
from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.domain.social.models import Friend, FriendFeedSource
from aerisun.domain.social.monitor import (
    check_single_friend_site,
    run_due_rss_health_checks,
)


@respx.mock
def test_check_single_friend_site_marks_friend_lost(seeded_session) -> None:
    friend = seeded_session.query(Friend).filter(Friend.name == "Arthals' ink").first()
    assert friend is not None

    respx.get(friend.url).mock(return_value=httpx.Response(503))

    result = check_single_friend_site(seeded_session, friend.id, get_settings())
    seeded_session.refresh(friend)

    assert result["status"] == "lost"
    assert friend.status == "lost"
    assert friend.last_checked_at is not None
    assert friend.last_error == "HTTP 503"


@respx.mock
def test_check_single_friend_site_trims_whitespace_url(seeded_session) -> None:
    friend = seeded_session.query(Friend).filter(Friend.name == "Arthals' ink").first()
    assert friend is not None

    friend.url = "  https://arthals.ink/  "
    seeded_session.commit()

    respx.get("https://arthals.ink/").mock(return_value=httpx.Response(200))

    result = check_single_friend_site(seeded_session, friend.id, get_settings())
    seeded_session.refresh(friend)

    assert result["status"] == "active"
    assert friend.status == "active"
    assert friend.url == "https://arthals.ink/"
    assert friend.last_error is None


@respx.mock
def test_run_due_rss_health_checks_marks_source_invalid(seeded_session) -> None:
    all_sources = seeded_session.query(FriendFeedSource).all()
    for item in all_sources:
        item.last_fetched_at = utcnow()
    seeded_session.flush()

    source = (
        seeded_session.query(FriendFeedSource)
        .join(Friend, FriendFeedSource.friend_id == Friend.id)
        .filter(Friend.name == "Arthals' ink")
        .first()
    )
    assert source is not None

    source.last_fetched_at = None
    source.last_error = None
    seeded_session.commit()

    respx.get(source.feed_url).mock(return_value=httpx.Response(500))
    respx.route().mock(return_value=httpx.Response(404))

    summary = run_due_rss_health_checks(get_settings())

    factory = get_session_factory()
    with factory() as session:
        refreshed_source = session.get(FriendFeedSource, source.id)
        refreshed_friend = session.get(Friend, source.friend_id)
        assert refreshed_source is not None
        assert refreshed_friend is not None
        rss_status = refreshed_friend.rss_status

    assert summary["status"] == "completed"
    assert refreshed_source.last_error == "HTTP 500"
    assert rss_status == "invalid"
