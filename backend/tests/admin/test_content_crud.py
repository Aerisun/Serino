"""Integration tests for admin content CRUD endpoints.

Covers PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry through the
unified ``build_crud_router`` factory.  Each content type exercises the
full create / read / update / list / delete lifecycle plus bulk
operations, search, pagination, and authentication guards.
"""

from __future__ import annotations

import pytest

from aerisun.domain.crud import service as crud_service

# Base URL for all admin content endpoints.
BASE = "/api/v1/admin"

# Content types and their URL segments.
CONTENT_TYPES = ["posts", "diary", "thoughts", "excerpts"]
TAGLESS_CONTENT_TYPES = {"diary", "thoughts", "excerpts"}
AUTO_TITLE_CONTENT_TYPES = {"thoughts", "excerpts"}


def _make_payload(content_type: str, suffix: str = "") -> dict:
    """Return a minimal valid ContentCreate payload for the given type."""
    return {
        "slug": f"test-{content_type}-slug{suffix}",
        "title": f"Test {content_type.title()} Title{suffix}",
        "body": f"Test {content_type} body content{suffix}",
        "tags": ["test"],
        "status": "draft",
        "visibility": "public",
    }


def _expected_title(content_type: str, payload: dict) -> str:
    if content_type in AUTO_TITLE_CONTENT_TYPES:
        return payload.get("summary") or payload["body"]
    return payload["title"]


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
        assert data["title"] == _expected_title(content_type, payload)
        assert data["body"] == payload["body"]
        expected_tags = [] if content_type in TAGLESS_CONTENT_TYPES else ["test"]
        assert data["tags"] == expected_tags
        assert data["status"] == "draft"
        assert "id" in data
        assert "created_at" in data

    def test_create_private_persists_as_archived(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-private")
        payload["status"] = "published"
        payload["visibility"] = "private"
        resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "archived"
        assert data["visibility"] == "private"

    def test_create_private_draft_persists_as_draft(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-private-draft")
        payload["status"] = "draft"
        payload["visibility"] = "private"
        resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "draft"
        assert data["visibility"] == "private"

    def test_read(self, client, admin_headers, content_type):
        # Create first
        payload = _make_payload(content_type, "-read")
        create_resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        item_id = create_resp.json()["id"]

        resp = client.get(f"{BASE}/{content_type}/{item_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == item_id
        assert resp.json()["title"] == _expected_title(content_type, payload)

    def test_update(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-update")
        create_resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        item_id = create_resp.json()["id"]

        update_payload = {"title": "Updated Title"}
        expected_title = "Updated Title"
        if content_type in AUTO_TITLE_CONTENT_TYPES:
            update_payload = {"body": f"Updated {content_type} body"}
            expected_title = update_payload["body"]
        resp = client.put(
            f"{BASE}/{content_type}/{item_id}",
            json=update_payload,
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == expected_title
        # slug should remain unchanged
        assert resp.json()["slug"] == payload["slug"]

    def test_create_without_slug_generates_unique_slug(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-auto-slug")
        payload.pop("slug")
        if content_type in AUTO_TITLE_CONTENT_TYPES:
            payload.pop("title")

        resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)

        assert resp.status_code == 201
        generated_slug = resp.json()["slug"]
        assert generated_slug.isdigit()

    def test_posts_and_diary_still_require_title(self, client, admin_headers, content_type):
        if content_type not in {"posts", "diary"}:
            pytest.skip("Only posts and diary require a manual title")

        payload = _make_payload(content_type, "-missing-title")
        payload.pop("title")

        resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)

        assert resp.status_code == 422
        assert resp.json()["detail"] == "标题不能为空"

    def test_thoughts_and_excerpts_can_create_without_title(self, client, admin_headers, content_type):
        if content_type not in AUTO_TITLE_CONTENT_TYPES:
            pytest.skip("Only thoughts and excerpts auto-derive title")

        payload = _make_payload(content_type, "-missing-title")
        payload.pop("title")

        resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)

        assert resp.status_code == 201
        assert resp.json()["title"] == payload["body"]

    def test_duplicate_slug_is_rejected_across_content_types(self, client, admin_headers, content_type):
        shared_slug = f"shared-slug-{content_type}"
        payload = _make_payload("posts", f"-{content_type}-posts")
        payload["slug"] = shared_slug
        create_resp = client.post(f"{BASE}/posts/", json=payload, headers=admin_headers)
        assert create_resp.status_code == 201

        conflicting_type = "diary" if content_type == "posts" else content_type

        conflict_payload = _make_payload(conflicting_type, f"-{content_type}-conflict")
        conflict_payload["slug"] = shared_slug

        resp = client.post(f"{BASE}/{conflicting_type}/", json=conflict_payload, headers=admin_headers)

        assert resp.status_code == 409
        assert resp.json()["detail"] == f"slug '{shared_slug}' 已存在"

    def test_create_published_triggers_subscription_dispatch(self, client, admin_headers, content_type, monkeypatch):
        calls: list[bool] = []
        monkeypatch.setattr(
            crud_service,
            "_dispatch_content_subscriptions_if_needed",
            lambda *args, **kwargs: calls.append(True),
        )

        payload = _make_payload(content_type, "-publish-create")
        payload["status"] = "published"
        payload["visibility"] = "public"
        resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)

        assert resp.status_code == 201
        assert calls == [True]

    def test_update_to_published_triggers_subscription_dispatch(self, client, admin_headers, content_type, monkeypatch):
        calls: list[bool] = []
        monkeypatch.setattr(
            crud_service,
            "_dispatch_content_subscriptions_if_needed",
            lambda *args, **kwargs: calls.append(True),
        )

        payload = _make_payload(content_type, "-publish-update")
        create_resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        item_id = create_resp.json()["id"]

        resp = client.put(
            f"{BASE}/{content_type}/{item_id}",
            json={"status": "published", "visibility": "public"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert calls[-1:] == [True]

    def test_update_archived_private_to_public_becomes_draft(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-restore")
        payload["status"] = "published"
        payload["visibility"] = "private"
        create_resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        item_id = create_resp.json()["id"]

        resp = client.put(
            f"{BASE}/{content_type}/{item_id}",
            json={"visibility": "public"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"
        assert resp.json()["visibility"] == "public"

    def test_update_archived_private_to_private_draft_stays_draft(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-private-draft-restore")
        payload["status"] = "published"
        payload["visibility"] = "private"
        create_resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        item_id = create_resp.json()["id"]

        resp = client.put(
            f"{BASE}/{content_type}/{item_id}",
            json={"status": "draft"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"
        assert resp.json()["visibility"] == "private"

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

        resp = client.get(f"{BASE}/{content_type}/{item_id}", headers=admin_headers)
        assert resp.json()["status"] == "published"
        assert resp.json()["visibility"] == "public"

    def test_bulk_status_publish_triggers_subscription_dispatch(self, client, admin_headers, content_type, monkeypatch):
        calls: list[bool] = []
        monkeypatch.setattr(
            crud_service,
            "_dispatch_content_subscriptions_if_needed",
            lambda *args, **kwargs: calls.append(True),
        )

        resp = client.post(
            f"{BASE}/{content_type}/",
            json=_make_payload(content_type, "-bs-dispatch"),
            headers=admin_headers,
        )
        item_id = resp.json()["id"]

        resp = client.post(
            f"{BASE}/{content_type}/bulk-status",
            json={"ids": [item_id], "status": "published"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert calls[-1:] == [True]

    def test_bulk_archive_sets_private_visibility(self, client, admin_headers, content_type):
        resp = client.post(
            f"{BASE}/{content_type}/",
            json=_make_payload(content_type, "-ba"),
            headers=admin_headers,
        )
        item_id = resp.json()["id"]

        resp = client.post(
            f"{BASE}/{content_type}/bulk-status",
            json={"ids": [item_id], "status": "archived"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["affected"] == 1

        resp = client.get(f"{BASE}/{content_type}/{item_id}", headers=admin_headers)
        assert resp.json()["status"] == "archived"
        assert resp.json()["visibility"] == "private"


# ── Search & pagination ───────────────────────────────────────────────


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
class TestContentSearchAndPagination:
    def test_search(self, client, admin_headers, content_type):
        # Create an entry with a unique keyword in searchable content fields
        keyword = f"UniqueKeyword{content_type}"
        payload = _make_payload(content_type, "-search")
        payload["body"] = f"Searchable {keyword} Entry"
        if content_type not in AUTO_TITLE_CONTENT_TYPES:
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
        assert any(keyword in (item["title"] + item["body"]) for item in data["items"])

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
