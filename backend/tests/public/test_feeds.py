from __future__ import annotations

import pytest

from aerisun.core.db import get_session_factory
from aerisun.core.settings import get_settings
from aerisun.domain.content.feed_service import build_posts_rss_xml
from aerisun.domain.diary_access.service import DIARY_PRIVATE_FEATURE_FLAG
from aerisun.domain.site_config.models import SiteProfile

ADMIN_BASE = "/api/v1/admin"


def _set_diary_private_enabled(enabled: bool) -> None:
    with get_session_factory()() as session:
        profile = session.query(SiteProfile).one()
        flags = dict(profile.feature_flags or {})
        flags[DIARY_PRIVATE_FEATURE_FLAG] = enabled
        profile.feature_flags = flags
        session.commit()


def _make_payload(content_type: str, suffix: str) -> dict:
    return {
        "slug": f"rss-{content_type}{suffix}",
        "title": f"RSS {content_type.title()}{suffix}",
        "body": f"RSS body for {content_type}{suffix}",
        "tags": ["rss"],
        "visibility": "public",
    }


@pytest.mark.parametrize(
    ("path", "channel_title", "slug", "item_path"),
    [
        ("/feeds/posts.xml", "Aerisun Posts", "from-zero-design-system", "/posts/from-zero-design-system"),
        ("/feeds/diary.xml", "Aerisun Diary", "spring-equinox-and-warm-light", "/diary/spring-equinox-and-warm-light"),
        ("/feeds/thoughts.xml", "Aerisun Thoughts", "spacing-rhythm-note", "/thoughts#spacing-rhythm-note"),
        ("/feeds/excerpts.xml", "Aerisun Excerpts", "good-design-note", "/excerpts#good-design-note"),
    ],
)
def test_public_content_feeds_return_rss_xml(client, path: str, channel_title: str, slug: str, item_path: str) -> None:
    if path == "/feeds/diary.xml":
        _set_diary_private_enabled(False)
    site_url = (get_settings().site_url or "https://example.com").rstrip("/")

    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/rss+xml")
    assert f"<title>{channel_title}</title>" in response.text
    assert slug in response.text
    assert f"{site_url}{item_path}" in response.text


@pytest.mark.parametrize("alias_path", ["/rss.xml", "/feed.xml", "/feeds.xml"])
def test_posts_feed_aliases_return_same_xml_as_posts_feed(client, alias_path: str) -> None:
    posts_response = client.get("/feeds/posts.xml")
    alias_response = client.get(alias_path)

    assert posts_response.status_code == 200
    assert alias_response.status_code == 200
    assert alias_response.headers["content-type"].startswith("application/rss+xml")
    assert alias_response.text == posts_response.text


@pytest.mark.parametrize(
    ("content_type", "feed_path"),
    [
        ("posts", "/feeds/posts.xml"),
        ("diary", "/feeds/diary.xml"),
        ("thoughts", "/feeds/thoughts.xml"),
        ("excerpts", "/feeds/excerpts.xml"),
    ],
)
def test_feed_only_includes_public_content(client, admin_headers, content_type: str, feed_path: str) -> None:
    if content_type == "diary":
        _set_diary_private_enabled(False)
    public_payload = _make_payload(content_type, "-public")

    private_payload = _make_payload(content_type, "-private")
    private_payload["visibility"] = "private"

    public_resp = client.post(f"{ADMIN_BASE}/{content_type}/", json=public_payload, headers=admin_headers)
    assert public_resp.status_code == 201

    private_resp = client.post(f"{ADMIN_BASE}/{content_type}/", json=private_payload, headers=admin_headers)
    assert private_resp.status_code == 201

    response = client.get(feed_path)

    assert response.status_code == 200
    assert public_payload["slug"] in response.text
    assert private_payload["slug"] not in response.text


def test_posts_feed_excludes_public_posts_marked_for_rss_exclusion(client, admin_headers) -> None:
    hidden_payload = _make_payload("posts", "-hidden-from-rss")
    hidden_payload["exclude_from_rss"] = True
    visible_payload = _make_payload("posts", "-visible-in-rss")

    hidden_response = client.post(f"{ADMIN_BASE}/posts/", json=hidden_payload, headers=admin_headers)
    visible_response = client.post(f"{ADMIN_BASE}/posts/", json=visible_payload, headers=admin_headers)

    assert hidden_response.status_code == 201
    assert visible_response.status_code == 201

    response = client.get("/feeds/posts.xml")

    assert visible_payload["slug"] in response.text
    assert hidden_payload["slug"] not in response.text


def test_posts_feed_backfills_limit_after_excluding_newer_posts(client, admin_headers) -> None:
    visible_payload = _make_payload("posts", "-older-visible")
    visible_payload["published_at"] = "2099-01-01T00:00:00+08:00"
    hidden_payload = _make_payload("posts", "-newer-hidden")
    hidden_payload["published_at"] = "2099-01-02T00:00:00+08:00"
    hidden_payload["exclude_from_rss"] = True

    assert client.post(f"{ADMIN_BASE}/posts/", json=visible_payload, headers=admin_headers).status_code == 201
    assert client.post(f"{ADMIN_BASE}/posts/", json=hidden_payload, headers=admin_headers).status_code == 201

    with get_session_factory()() as session:
        response = build_posts_rss_xml(session, "https://example.com", limit=1)

    assert visible_payload["slug"] in response
    assert hidden_payload["slug"] not in response
