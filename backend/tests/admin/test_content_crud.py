"""Integration tests for admin content CRUD endpoints.

Covers PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry through the
unified ``build_crud_router`` factory.  Each content type exercises the
full create / read / update / list / delete lifecycle plus bulk
operations, search, pagination, and authentication guards.
"""

from __future__ import annotations

import pytest

# Base URL for all admin content endpoints.
BASE = "/api/v1/admin"

# Content types and their URL segments.
CONTENT_TYPES = ["posts", "diary", "thoughts", "excerpts"]


def _make_payload(content_type: str, suffix: str = "") -> dict:
    """Return a minimal valid ContentCreate payload for the given type."""
    return {
        "slug": f"test-{content_type}-slug{suffix}",
        "title": f"Test {content_type.title()} Title{suffix}",
        "body": f"Test {content_type} body content{suffix}",
        "tags": ["test"],
        "status": "draft",
    }


# ── Full CRUD lifecycle per content type ──────────────────────────────


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
class TestContentCRUDLifecycle:
    """CREATE → READ → UPDATE → LIST → DELETE → 404 for each type."""

    def test_create(self, client, admin_headers, content_type):
        payload = _make_payload(content_type)
        resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == payload["slug"]
        assert data["title"] == payload["title"]
        assert data["body"] == payload["body"]
        assert data["tags"] == ["test"]
        assert data["status"] == "draft"
        assert "id" in data
        assert "created_at" in data

    def test_read(self, client, admin_headers, content_type):
        # Create first
        payload = _make_payload(content_type, "-read")
        create_resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        item_id = create_resp.json()["id"]

        resp = client.get(f"{BASE}/{content_type}/{item_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == item_id
        assert resp.json()["title"] == payload["title"]

    def test_update(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-update")
        create_resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        item_id = create_resp.json()["id"]

        update_payload = {"title": "Updated Title"}
        resp = client.put(
            f"{BASE}/{content_type}/{item_id}",
            json=update_payload,
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"
        # slug should remain unchanged
        assert resp.json()["slug"] == payload["slug"]

    def test_list(self, client, admin_headers, content_type):
        # Ensure at least one item exists
        client.post(
            f"{BASE}/{content_type}/",
            json=_make_payload(content_type, "-list"),
            headers=admin_headers,
        )

        resp = client.get(f"{BASE}/{content_type}/", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert isinstance(data["items"], list)
        assert "page" in data
        assert "page_size" in data

    def test_delete(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-delete")
        create_resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        item_id = create_resp.json()["id"]

        resp = client.delete(f"{BASE}/{content_type}/{item_id}", headers=admin_headers)
        assert resp.status_code == 204

        # Confirm gone
        resp = client.get(f"{BASE}/{content_type}/{item_id}", headers=admin_headers)
        assert resp.status_code == 404

    def test_get_nonexistent_returns_404(self, client, admin_headers, content_type):
        resp = client.get(
            f"{BASE}/{content_type}/nonexistent-id-12345",
            headers=admin_headers,
        )
        assert resp.status_code == 404


# ── Authentication guard ──────────────────────────────────────────────


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
class TestContentAuth:
    """Requests without a valid token must be rejected."""

    def test_list_without_token_is_rejected(self, client, content_type):
        resp = client.get(f"{BASE}/{content_type}/")
        assert resp.status_code in (401, 403)

    def test_create_without_token_is_rejected(self, client, content_type):
        resp = client.post(f"{BASE}/{content_type}/", json=_make_payload(content_type))
        assert resp.status_code in (401, 403)


# ── Bulk operations ───────────────────────────────────────────────────


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
class TestContentBulkOperations:
    def test_bulk_delete(self, client, admin_headers, content_type):
        ids = []
        for i in range(2):
            resp = client.post(
                f"{BASE}/{content_type}/",
                json=_make_payload(content_type, f"-bd{i}"),
                headers=admin_headers,
            )
            ids.append(resp.json()["id"])

        resp = client.post(
            f"{BASE}/{content_type}/bulk-delete",
            json={"ids": ids},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["affected"] == 2

        # Verify they are gone
        for item_id in ids:
            assert client.get(f"{BASE}/{content_type}/{item_id}", headers=admin_headers).status_code == 404

    def test_bulk_status(self, client, admin_headers, content_type):
        resp = client.post(
            f"{BASE}/{content_type}/",
            json=_make_payload(content_type, "-bs"),
            headers=admin_headers,
        )
        item_id = resp.json()["id"]

        resp = client.post(
            f"{BASE}/{content_type}/bulk-status",
            json={"ids": [item_id], "status": "published"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["affected"] == 1

        # Verify status changed
        resp = client.get(f"{BASE}/{content_type}/{item_id}", headers=admin_headers)
        assert resp.json()["status"] == "published"


# ── Search & pagination ───────────────────────────────────────────────


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
class TestContentSearchAndPagination:
    def test_search(self, client, admin_headers, content_type):
        # Create an entry with a unique keyword in the title
        keyword = f"UniqueKeyword{content_type}"
        payload = _make_payload(content_type, "-search")
        payload["title"] = f"Searchable {keyword} Entry"
        client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)

        resp = client.get(
            f"{BASE}/{content_type}/",
            params={"search": keyword},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(keyword in item["title"] for item in data["items"])

    def test_pagination(self, client, admin_headers, content_type):
        # Create enough items to paginate
        for i in range(3):
            client.post(
                f"{BASE}/{content_type}/",
                json=_make_payload(content_type, f"-pg{i}"),
                headers=admin_headers,
            )

        resp = client.get(
            f"{BASE}/{content_type}/",
            params={"page": 1, "page_size": 2},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["items"]) <= 2
        assert data["total"] >= 3
