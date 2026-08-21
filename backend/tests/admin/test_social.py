"""Focused integration contracts for admin friend and feed-source routes."""

from __future__ import annotations

import httpx
import respx

BASE = "/api/v1/admin/social"

CREATE_FEED_RSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Blog</title>
    <item>
      <title>Freshly Crawled Post</title>
      <link>https://friend-feed.example.com/posts/fresh</link>
      <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
      <description>Fresh post from the new feed</description>
    </item>
  </channel>
</rss>"""

UPDATED_FEED_RSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Updated Blog</title>
    <item>
      <title>New Feed Post</title>
      <link>https://friend-feed-updated.example.com/posts/new</link>
      <pubDate>Tue, 02 Jan 2024 12:00:00 +0000</pubDate>
      <description>Post from the updated feed</description>
    </item>
  </channel>
</rss>"""


def _friend_payload(suffix: str = "") -> dict:
    return {
        "name": f"Test Friend{suffix}",
        "url": f"https://friend{suffix}.example.com",
        "avatar_url": "https://example.com/avatar.png",
        "description": f"A test friend{suffix}",
        "status": "active",
    }


def _create_friend(client, admin_headers, suffix: str = "-feed") -> str:
    response = client.post(
        f"{BASE}/friends/",
        json=_friend_payload(suffix),
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_friend_routes_share_crud_lifecycle(client, admin_headers) -> None:
    payload = {
        "name": "  Trimmed Friend  ",
        "url": "  https://trimmed.example.com/  ",
        "avatar_url": "  https://trimmed.example.com/avatar.png  ",
        "description": "  Description with spaces  ",
        "status": "active",
    }

    created = client.post(f"{BASE}/friends/", json=payload, headers=admin_headers)

    assert created.status_code == 201
    friend = created.json()
    assert friend["name"] == "Trimmed Friend"
    assert friend["url"] == "https://trimmed.example.com/"
    assert friend["avatar_url"] == "https://trimmed.example.com/avatar.png"
    assert friend["description"] == "Description with spaces"
    assert friend["rss_status"] == "unconfigured"

    friend_id = friend["id"]
    assert client.get(f"{BASE}/friends/{friend_id}", headers=admin_headers).json()["name"] == "Trimmed Friend"

    updated = client.put(
        f"{BASE}/friends/{friend_id}",
        json={"name": "Updated Friend Name"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Friend Name"

    listed = client.get(f"{BASE}/friends/", headers=admin_headers)
    assert listed.status_code == 200
    assert any(item["id"] == friend_id for item in listed.json()["items"])

    assert client.delete(f"{BASE}/friends/{friend_id}", headers=admin_headers).status_code == 204
    assert client.get(f"{BASE}/friends/{friend_id}", headers=admin_headers).status_code == 404
    assert client.get(f"{BASE}/friends/nonexistent-id", headers=admin_headers).status_code == 404


def test_friend_bulk_search_and_pagination(client, admin_headers) -> None:
    ids = []
    for index in range(3):
        payload = _friend_payload(f"-bulk-{index}")
        payload["name"] = f"UniqueFriendName {index}"
        ids.append(client.post(f"{BASE}/friends/", json=payload, headers=admin_headers).json()["id"])

    searched = client.get(
        f"{BASE}/friends/",
        params={"search": "UniqueFriendName", "page": 1, "page_size": 2},
        headers=admin_headers,
    )
    assert searched.status_code == 200
    assert searched.json()["total"] >= 3
    assert len(searched.json()["items"]) == 2

    status = client.post(
        f"{BASE}/friends/bulk-status",
        json={"ids": ids, "status": "lost"},
        headers=admin_headers,
    )
    assert status.status_code == 200
    assert status.json()["affected"] == 3
    assert client.get(f"{BASE}/friends/{ids[0]}", headers=admin_headers).json()["status"] == "lost"

    deleted = client.post(
        f"{BASE}/friends/bulk-delete",
        json={"ids": ids},
        headers=admin_headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["affected"] == 3


def test_friend_routes_require_authentication(client) -> None:
    assert client.get(f"{BASE}/friends/").status_code in (401, 403)
    assert client.post(f"{BASE}/friends/", json=_friend_payload()).status_code in (401, 403)


def test_feed_source_rejects_missing_resources(client, admin_headers) -> None:
    missing_friend = client.post(
        f"{BASE}/friends/nonexistent-id/feeds",
        json={
            "friend_id": "nonexistent-id",
            "feed_url": "https://example.com/feed.xml",
        },
        headers=admin_headers,
    )
    assert missing_friend.status_code == 404
    assert client.delete(f"{BASE}/feeds/nonexistent-id", headers=admin_headers).status_code == 404


@respx.mock
def test_create_feed_trims_url_and_crawls_immediately(client, admin_headers) -> None:
    friend_id = _create_friend(client, admin_headers, "-feed-crawl")
    feed_url = "https://friend-feed.example.com/rss.xml"
    respx.get(feed_url).mock(return_value=httpx.Response(200, text=CREATE_FEED_RSS))

    response = client.post(
        f"{BASE}/friends/{friend_id}/feeds",
        json={
            "friend_id": friend_id,
            "feed_url": f"  {feed_url}  ",
            "is_enabled": True,
        },
        headers=admin_headers,
    )

    assert response.status_code == 201
    feed = response.json()
    assert feed["feed_url"] == feed_url
    assert feed["last_fetched_at"] is not None
    assert feed["last_error"] is None

    listed = client.get(f"{BASE}/friends/{friend_id}/feeds", headers=admin_headers)
    assert listed.status_code == 200
    assert any(item["id"] == feed["id"] for item in listed.json())

    public_response = client.get("/api/v1/site/friend-feed?limit=50")
    assert public_response.status_code == 200
    assert any(item["title"] == "Freshly Crawled Post" for item in public_response.json()["items"])


@respx.mock
def test_update_feed_url_replaces_items_and_delete_removes_source(client, admin_headers) -> None:
    from aerisun.core.db import get_session_factory
    from aerisun.domain.social.models import FriendFeedItem

    friend_id = _create_friend(client, admin_headers, "-feed-update")
    initial_url = "https://friend-feed.example.com/rss.xml"
    updated_url = "https://friend-feed-updated.example.com/rss.xml"
    respx.get(initial_url).mock(return_value=httpx.Response(200, text=CREATE_FEED_RSS))
    created = client.post(
        f"{BASE}/friends/{friend_id}/feeds",
        json={"friend_id": friend_id, "feed_url": initial_url, "is_enabled": True},
        headers=admin_headers,
    )
    assert created.status_code == 201
    feed_id = created.json()["id"]

    respx.get(updated_url).mock(return_value=httpx.Response(200, text=UPDATED_FEED_RSS))
    updated = client.put(
        f"{BASE}/feeds/{feed_id}",
        json={"feed_url": updated_url},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["feed_url"] == updated_url
    assert updated.json()["last_fetched_at"] is not None

    with get_session_factory()() as session:
        items = session.query(FriendFeedItem).filter(FriendFeedItem.source_id == feed_id).all()
    assert [item.title for item in items] == ["New Feed Post"]

    assert client.delete(f"{BASE}/feeds/{feed_id}", headers=admin_headers).status_code == 204
