"""Integration tests for admin social endpoints.

Covers Friend CRUD (via ``build_crud_router``), friend feed source
sub-resource operations, and authentication guards under
``/api/v1/admin/social/``.
"""

from __future__ import annotations

BASE = "/api/v1/admin/social"


def _friend_payload(suffix: str = "") -> dict:
    """Return a minimal valid FriendCreate payload."""
    return {
        "name": f"Test Friend{suffix}",
        "url": f"https://friend{suffix}.example.com",
        "avatar_url": "https://example.com/avatar.png",
        "description": f"A test friend{suffix}",
        "status": "active",
        "order_index": 0,
    }


# ── Friend CRUD lifecycle ────────────────────────────────────────────


class TestFriendCRUD:

    def test_create_friend(self, client, admin_headers):
        payload = _friend_payload()
        resp = client.post(
            f"{BASE}/friends/", json=payload, headers=admin_headers
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == payload["name"]
        assert data["url"] == payload["url"]
        assert data["avatar_url"] == payload["avatar_url"]
        assert data["description"] == payload["description"]
        assert "id" in data
        assert "created_at" in data

    def test_read_friend(self, client, admin_headers):
        payload = _friend_payload("-read")
        create_resp = client.post(
            f"{BASE}/friends/", json=payload, headers=admin_headers
        )
        friend_id = create_resp.json()["id"]

        resp = client.get(
            f"{BASE}/friends/{friend_id}", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == friend_id
        assert resp.json()["name"] == payload["name"]

    def test_update_friend(self, client, admin_headers):
        payload = _friend_payload("-update")
        create_resp = client.post(
            f"{BASE}/friends/", json=payload, headers=admin_headers
        )
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
        create_resp = client.post(
            f"{BASE}/friends/", json=payload, headers=admin_headers
        )
        friend_id = create_resp.json()["id"]

        resp = client.delete(
            f"{BASE}/friends/{friend_id}", headers=admin_headers
        )
        assert resp.status_code == 204

        resp = client.get(
            f"{BASE}/friends/{friend_id}", headers=admin_headers
        )
        assert resp.status_code == 404

    def test_get_nonexistent_friend_returns_404(self, client, admin_headers):
        resp = client.get(
            f"{BASE}/friends/nonexistent-id", headers=admin_headers
        )
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
            json={"ids": [friend_id], "status": "inactive"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["affected"] == 1

        resp = client.get(
            f"{BASE}/friends/{friend_id}", headers=admin_headers
        )
        assert resp.json()["status"] == "inactive"


# ── Friend search & pagination ────────────────────────────────────────


class TestFriendSearchAndPagination:

    def test_search_friends(self, client, admin_headers):
        keyword = "UniqueFriendName"
        payload = _friend_payload("-search")
        payload["name"] = f"Searchable {keyword} Friend"
        client.post(
            f"{BASE}/friends/", json=payload, headers=admin_headers
        )

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
        resp = client.post(
            f"{BASE}/friends/", json=_friend_payload()
        )
        assert resp.status_code in (401, 403)


# ── Friend Feed Sources ──────────────────────────────────────────────


class TestFriendFeedSources:

    def _create_friend(self, client, admin_headers) -> str:
        resp = client.post(
            f"{BASE}/friends/",
            json=_friend_payload("-feed"),
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
        feed_id = feed["id"]

        # LIST feeds for the friend
        resp = client.get(
            f"{BASE}/friends/{friend_id}/feeds", headers=admin_headers
        )
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
        resp = client.delete(
            f"{BASE}/feeds/{feed_id}", headers=admin_headers
        )
        assert resp.status_code == 204

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
        resp = client.delete(
            f"{BASE}/feeds/nonexistent-id", headers=admin_headers
        )
        assert resp.status_code == 404
