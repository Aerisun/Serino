"""Integration tests for admin social endpoints.

Covers Friend CRUD (via ``build_crud_router``), friend feed source
sub-resource operations, and authentication guards under
``/api/v1/admin/social/``.
"""

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
    """Return a minimal valid FriendCreate payload."""
    return {
        "name": f"Test Friend{suffix}",
        "url": f"https://friend{suffix}.example.com",
        "avatar_url": "https://example.com/avatar.png",
        "description": f"A test friend{suffix}",
        "status": "active",
    }


# ── Friend CRUD lifecycle ────────────────────────────────────────────


class TestFriendCRUD:
    def test_create_friend_trims_whitespace_fields(self, client, admin_headers):
        payload = {
            "name": "  Trimmed Friend  ",
            "url": "  https://trimmed.example.com/  ",
            "avatar_url": "  https://trimmed.example.com/avatar.png  ",
            "description": "  Description with spaces  ",
            "status": "active",
        }

        resp = client.post(f"{BASE}/friends/", json=payload, headers=admin_headers)
        assert resp.status_code == 201

        data = resp.json()
        assert data["name"] == "Trimmed Friend"
        assert data["url"] == "https://trimmed.example.com/"
        assert data["avatar_url"] == "https://trimmed.example.com/avatar.png"
        assert data["description"] == "Description with spaces"

    def test_create_friend(self, client, admin_headers):
        payload = _friend_payload()
        resp = client.post(f"{BASE}/friends/", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == payload["name"]
        assert data["url"] == payload["url"]
        assert data["avatar_url"] == payload["avatar_url"]
        assert data["description"] == payload["description"]
        assert data["rss_status"] == "unconfigured"
        assert "id" in data
        assert "created_at" in data

    def test_read_friend(self, client, admin_headers):
        payload = _friend_payload("-read")
        create_resp = client.post(f"{BASE}/friends/", json=payload, headers=admin_headers)
        friend_id = create_resp.json()["id"]

        resp = client.get(f"{BASE}/friends/{friend_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == friend_id
        assert resp.json()["name"] == payload["name"]

    def test_update_friend(self, client, admin_headers):
        payload = _friend_payload("-update")
        create_resp = client.post(f"{BASE}/friends/", json=payload, headers=admin_headers)
        friend_id = create_resp.json()["id"]

        resp = client.put(
            f"{BASE}/friends/{friend_id}",
            json={"name": "Updated Friend Name"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Friend Name"
        assert resp.json()["url"] == payload["url"]

    def test_list_friends(self, client, admin_headers):
        client.post(
            f"{BASE}/friends/",
            json=_friend_payload("-list"),
            headers=admin_headers,
        )

        resp = client.get(f"{BASE}/friends/", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert isinstance(data["items"], list)

    def test_delete_friend(self, client, admin_headers):
        payload = _friend_payload("-delete")
        create_resp = client.post(f"{BASE}/friends/", json=payload, headers=admin_headers)
        friend_id = create_resp.json()["id"]

        resp = client.delete(f"{BASE}/friends/{friend_id}", headers=admin_headers)
        assert resp.status_code == 204

        resp = client.get(f"{BASE}/friends/{friend_id}", headers=admin_headers)
        assert resp.status_code == 404

    def test_get_nonexistent_friend_returns_404(self, client, admin_headers):
        resp = client.get(f"{BASE}/friends/nonexistent-id", headers=admin_headers)
        assert resp.status_code == 404


# ── Friend bulk operations ────────────────────────────────────────────


class TestFriendBulkOperations:
    def test_bulk_delete_friends(self, client, admin_headers):
        ids = []
        for i in range(2):
            resp = client.post(
                f"{BASE}/friends/",
                json=_friend_payload(f"-bd{i}"),
                headers=admin_headers,
            )
            ids.append(resp.json()["id"])

        resp = client.post(
            f"{BASE}/friends/bulk-delete",
            json={"ids": ids},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["affected"] == 2

    def test_bulk_status_friends(self, client, admin_headers):
        resp = client.post(
            f"{BASE}/friends/",
            json=_friend_payload("-bstatus"),
            headers=admin_headers,
        )
        friend_id = resp.json()["id"]

        resp = client.post(
            f"{BASE}/friends/bulk-status",
            json={"ids": [friend_id], "status": "lost"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["affected"] == 1

        resp = client.get(f"{BASE}/friends/{friend_id}", headers=admin_headers)
        assert resp.json()["status"] == "lost"
        assert resp.json()["rss_status"] == "unconfigured"


# ── Friend search & pagination ────────────────────────────────────────


class TestFriendSearchAndPagination:
    def test_search_friends(self, client, admin_headers):
        keyword = "UniqueFriendName"
        payload = _friend_payload("-search")
        payload["name"] = f"Searchable {keyword} Friend"
        client.post(f"{BASE}/friends/", json=payload, headers=admin_headers)

        resp = client.get(
            f"{BASE}/friends/",
            params={"search": keyword},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_pagination_friends(self, client, admin_headers):
        for i in range(3):
            client.post(
                f"{BASE}/friends/",
                json=_friend_payload(f"-pg{i}"),
                headers=admin_headers,
            )

        resp = client.get(
            f"{BASE}/friends/",
            params={"page": 1, "page_size": 2},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["items"]) <= 2


# ── Authentication guards ─────────────────────────────────────────────


class TestFriendAuth:
    def test_list_friends_without_token(self, client):
        resp = client.get(f"{BASE}/friends/")
        assert resp.status_code in (401, 403)

    def test_create_friend_without_token(self, client):
        resp = client.post(f"{BASE}/friends/", json=_friend_payload())
        assert resp.status_code in (401, 403)


# ── Friend Feed Sources ──────────────────────────────────────────────


class TestFriendFeedSources:
    def _create_friend(self, client, admin_headers, suffix: str = "-feed") -> str:
        resp = client.post(
            f"{BASE}/friends/",
            json=_friend_payload(suffix),
            headers=admin_headers,
        )
        return resp.json()["id"]

    def test_feed_source_lifecycle(self, client, admin_headers):
        friend_id = self._create_friend(client, admin_headers)

        # CREATE feed source
        resp = client.post(
            f"{BASE}/friends/{friend_id}/feeds",
            json={
                "friend_id": friend_id,
                "feed_url": "https://example.com/feed.xml",
                "is_enabled": True,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        feed = resp.json()
        assert feed["feed_url"] == "https://example.com/feed.xml"
        assert feed["is_enabled"] is True
        assert feed["rss_status"] in {"active", "invalid"}
        feed_id = feed["id"]

        # LIST feeds for the friend
        resp = client.get(f"{BASE}/friends/{friend_id}/feeds", headers=admin_headers)
        assert resp.status_code == 200
        feeds = resp.json()
        assert any(f["id"] == feed_id for f in feeds)

        # UPDATE feed source
        resp = client.put(
            f"{BASE}/feeds/{feed_id}",
            json={"feed_url": "https://example.com/rss.xml"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["feed_url"] == "https://example.com/rss.xml"

        # DELETE feed source
        resp = client.delete(f"{BASE}/feeds/{feed_id}", headers=admin_headers)
        assert resp.status_code == 204

    def test_create_feed_trims_whitespace_url(self, client, admin_headers):
        friend_id = self._create_friend(client, admin_headers, "-feed-trim")

        resp = client.post(
            f"{BASE}/friends/{friend_id}/feeds",
            json={
                "friend_id": friend_id,
                "feed_url": "  https://example.com/feed.xml  ",
                "is_enabled": True,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["feed_url"] == "https://example.com/feed.xml"

    def test_create_feed_for_nonexistent_friend(self, client, admin_headers):
        resp = client.post(
            f"{BASE}/friends/nonexistent-id/feeds",
            json={
                "friend_id": "nonexistent-id",
                "feed_url": "https://example.com/feed.xml",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_delete_nonexistent_feed(self, client, admin_headers):
        resp = client.delete(f"{BASE}/feeds/nonexistent-id", headers=admin_headers)
        assert resp.status_code == 404

    @respx.mock
    def test_create_feed_triggers_immediate_crawl(self, client, admin_headers):
        friend_id = self._create_friend(client, admin_headers, "-feed-crawl")
        feed_url = "https://friend-feed.example.com/rss.xml"

        respx.get(feed_url).mock(return_value=httpx.Response(200, text=CREATE_FEED_RSS))

        resp = client.post(
            f"{BASE}/friends/{friend_id}/feeds",
            json={
                "friend_id": friend_id,
                "feed_url": feed_url,
                "is_enabled": True,
            },
            headers=admin_headers,
        )

        assert resp.status_code == 201
        feed = resp.json()
        assert feed["last_fetched_at"] is not None
        assert feed["last_error"] is None

        public_resp = client.get("/api/v1/site/friend-feed?limit=50")
        assert public_resp.status_code == 200
        assert any(
            item["blogName"] == "Test Friend-feed-crawl" and item["title"] == "Freshly Crawled Post"
            for item in public_resp.json()["items"]
        )

    @respx.mock
    def test_update_feed_url_clears_old_items_and_recrawls(self, client, admin_headers):
        from aerisun.core.db import get_session_factory
        from aerisun.domain.social.models import FriendFeedItem

        friend_id = self._create_friend(client, admin_headers, "-feed-update")
        initial_feed_url = "https://friend-feed.example.com/rss.xml"
        updated_feed_url = "https://friend-feed-updated.example.com/rss.xml"

        respx.get(initial_feed_url).mock(return_value=httpx.Response(200, text=CREATE_FEED_RSS))
        create_resp = client.post(
            f"{BASE}/friends/{friend_id}/feeds",
            json={
                "friend_id": friend_id,
                "feed_url": initial_feed_url,
                "is_enabled": True,
            },
            headers=admin_headers,
        )
        assert create_resp.status_code == 201
        feed_id = create_resp.json()["id"]

        respx.get(updated_feed_url).mock(return_value=httpx.Response(200, text=UPDATED_FEED_RSS))
        update_resp = client.put(
            f"{BASE}/feeds/{feed_id}",
            json={"feed_url": updated_feed_url},
            headers=admin_headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["feed_url"] == updated_feed_url
        assert update_resp.json()["last_fetched_at"] is not None

        factory = get_session_factory()
        with factory() as session:
            items = session.query(FriendFeedItem).filter(FriendFeedItem.source_id == feed_id).all()

        assert len(items) == 1
        assert items[0].title == "New Feed Post"
