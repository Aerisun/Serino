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
    ("path", "channel_section", "slug", "item_path"),
    [
        ("/feeds/articles.xml", "Articles", "from-zero-design-system", "/posts/from-zero-design-system"),
        ("/feeds/diary.xml", "Diary", "spring-equinox-and-warm-light", "/diary/spring-equinox-and-warm-light"),
        ("/feeds/thoughts.xml", "Thoughts", "spacing-rhythm-note", "/thoughts#spacing-rhythm-note"),
        ("/feeds/excerpts.xml", "Excerpts", "good-design-note", "/excerpts#good-design-note"),
    ],
)
def test_public_content_feeds_return_rss_xml(
    client, path: str, channel_section: str, slug: str, item_path: str
) -> None:
    if path == "/feeds/diary.xml":
        _set_diary_private_enabled(False)
    site_url = (get_settings().site_url or "https://example.com").rstrip("/")
    with get_session_factory()() as session:
        site_name = session.query(SiteProfile).one().name

    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/rss+xml")
    assert f"<title>{site_name} {channel_section}</title>" in response.text
    assert slug in response.text
    assert f"{site_url}{item_path}" in response.text


@pytest.mark.parametrize("alias_path", ["/rss.xml", "/feed.xml", "/feeds.xml"])
def test_articles_feed_aliases_redirect_to_canonical_feed(client, alias_path: str) -> None:
    alias_response = client.get(alias_path, follow_redirects=False)

    assert alias_response.status_code == 308
    assert alias_response.headers["location"] == "/feeds/articles.xml"


def test_legacy_posts_feed_is_not_available(client) -> None:
    assert client.get("/feeds/posts.xml").status_code == 404


@pytest.mark.parametrize(
    ("content_type", "feed_path"),
    [
        ("posts", "/feeds/articles.xml"),
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

    response = client.get("/feeds/articles.xml")

    assert visible_payload["slug"] in response.text
    assert hidden_payload["slug"] not in response.text


def test_posts_feed_includes_notes_at_their_public_url_unless_excluded(client, admin_headers) -> None:
    visible_note = _make_payload("posts", "-visible-note-in-rss")
    visible_note["kind"] = "note"
    hidden_note = _make_payload("posts", "-hidden-note-from-rss")
    hidden_note["kind"] = "note"
    hidden_note["exclude_from_rss"] = True

    assert client.post(f"{ADMIN_BASE}/posts/", json=visible_note, headers=admin_headers).status_code == 201
    assert client.post(f"{ADMIN_BASE}/posts/", json=hidden_note, headers=admin_headers).status_code == 201

    response = client.get("/feeds/articles.xml")

    assert response.status_code == 200
    assert visible_note["slug"] in response.text
    assert f"/notes/{visible_note['slug']}" in response.text
    assert hidden_note["slug"] not in response.text


def test_posts_feed_excludes_posts_that_require_access_approval(client, admin_headers) -> None:
    protected_payload = _make_payload("posts", "-approval-only")
    protected_payload["requires_approval"] = True

    created = client.post(f"{ADMIN_BASE}/posts/", json=protected_payload, headers=admin_headers)
    assert created.status_code == 201

    response = client.get("/feeds/articles.xml")

    assert response.status_code == 200
    assert protected_payload["slug"] not in response.text


def test_feed_identity_uses_the_configured_public_site_name(client) -> None:
    with get_session_factory()() as session:
        profile = session.query(SiteProfile).one()
        profile.name = "Custom Public Name"
        session.commit()

    response = client.get("/feeds/articles.xml")

    assert response.status_code == 200
    assert "<title>Custom Public Name Articles</title>" in response.text
    assert "<description>Latest published manuscripts and notes from Custom Public Name</description>" in response.text
    assert "<generator>Serino</generator>" in response.text


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


def test_posts_rss_limits_generated_summary_to_thirty_characters_without_changing_post_list(
    client,
    admin_headers,
) -> None:
    body = "abcdefghijklmnopqrstuvwxyz0123456789"
    payload = _make_payload("posts", "-short-rss-summary")
    payload["body"] = body

    created = client.post(f"{ADMIN_BASE}/posts/", json=payload, headers=admin_headers)
    assert created.status_code == 201

    feed_response = client.get("/feeds/articles.xml")
    list_response = client.get("/api/v1/site/posts")

    assert feed_response.status_code == 200
    assert "abcdefghijklmnopqrstuvwxyz012…" in feed_response.text
    assert body not in feed_response.text

    assert list_response.status_code == 200
    entry = next(item for item in list_response.json()["items"] if item["slug"] == payload["slug"])
    assert entry["summary"] == body
