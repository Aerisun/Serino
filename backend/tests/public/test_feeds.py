from __future__ import annotations

import pytest

from aerisun.core.settings import get_settings

ADMIN_BASE = "/api/v1/admin"


def _make_payload(content_type: str, suffix: str) -> dict:
    return {
        "slug": f"rss-{content_type}{suffix}",
        "title": f"RSS {content_type.title()}{suffix}",
        "body": f"RSS body for {content_type}{suffix}",
        "tags": ["rss"],
        "status": "draft",
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
def test_feed_only_includes_published_public_content(client, admin_headers, content_type: str, feed_path: str) -> None:
    public_payload = _make_payload(content_type, "-public")
    public_payload["status"] = "published"

    draft_payload = _make_payload(content_type, "-draft")
    draft_payload["status"] = "draft"

    private_payload = _make_payload(content_type, "-private")
    private_payload["status"] = "published"
    private_payload["visibility"] = "private"

    public_resp = client.post(f"{ADMIN_BASE}/{content_type}/", json=public_payload, headers=admin_headers)
    assert public_resp.status_code == 201

    draft_resp = client.post(f"{ADMIN_BASE}/{content_type}/", json=draft_payload, headers=admin_headers)
    assert draft_resp.status_code == 201

    private_resp = client.post(f"{ADMIN_BASE}/{content_type}/", json=private_payload, headers=admin_headers)
    assert private_resp.status_code == 201

    response = client.get(feed_path)

    assert response.status_code == 200
    assert public_payload["slug"] in response.text
    assert draft_payload["slug"] not in response.text
    assert private_payload["slug"] not in response.text
