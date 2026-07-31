"""Integration tests for admin content CRUD endpoints.

Covers PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry through the
unified ``build_crud_router`` factory.  Each content type exercises the
full create / read / update / list / delete lifecycle plus bulk
operations, search, pagination, and authentication guards.
"""

from __future__ import annotations

import pytest

from aerisun.core.db import get_session_factory
from aerisun.domain.content.import_export_service import export_content_json, import_content_json
from aerisun.domain.crud import service as crud_service

# Base URL for all admin content endpoints.
BASE = "/api/v1/admin"

# Content types and their URL segments.
CONTENT_TYPES = ["posts", "diary", "thoughts", "excerpts"]
TAGLESS_CONTENT_TYPES = {"diary", "thoughts", "excerpts"}


def _make_payload(content_type: str, suffix: str = "") -> dict:
    """Return a minimal valid ContentCreate payload for the given type."""
    return {
        "slug": f"test-{content_type}-slug{suffix}",
        "title": f"Test {content_type.title()} Title{suffix}",
        "body": f"Test {content_type} body content{suffix}",
        "tags": ["test"],
        "visibility": "private",
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
        expected_tags = [] if content_type in TAGLESS_CONTENT_TYPES else ["test"]
        assert data["tags"] == expected_tags
        assert "status" not in data
        assert data["visibility"] == "private"
        if content_type == "posts":
            assert data["exclude_from_rss"] is False
            assert data["requires_approval"] is False
        else:
            assert "exclude_from_rss" not in data
            assert "requires_approval" not in data
        assert "id" in data
        assert "created_at" in data

    def test_create_public_persists_visibility(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-private")
        payload["visibility"] = "public"
        resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert "status" not in data
        assert data["visibility"] == "public"

    def test_diary_create_and_read_preserves_mood_and_weather(self, client, admin_headers, content_type):
        if content_type != "diary":
            pytest.skip("diary-specific presentation fields")

        payload = _make_payload(content_type, "-mood-weather")
        payload["mood"] = "calm"
        payload["weather"] = "overcast"

        create_resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)

        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["mood"] == "calm"
        assert created["weather"] == "overcast"

        read_resp = client.get(f"{BASE}/{content_type}/{created['id']}", headers=admin_headers)

        assert read_resp.status_code == 200
        read = read_resp.json()
        assert read["mood"] == "calm"
        assert read["weather"] == "overcast"

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

    def test_post_rss_exclusion_can_be_updated(self, client, admin_headers, content_type):
        if content_type != "posts":
            pytest.skip("post-specific RSS exclusion")

        payload = _make_payload(content_type, "-rss-excluded")
        created = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        assert created.status_code == 201

        response = client.put(
            f"{BASE}/{content_type}/{created.json()['id']}",
            json={"exclude_from_rss": True},
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["exclude_from_rss"] is True

    def test_post_approval_requirement_can_be_updated(self, client, admin_headers, content_type):
        if content_type != "posts":
            pytest.skip("post-specific approval requirement")

        payload = _make_payload(content_type, "-approval-required")
        created = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        assert created.status_code == 201

        response = client.put(
            f"{BASE}/{content_type}/{created.json()['id']}",
            json={"requires_approval": True},
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["requires_approval"] is True

    def test_post_json_export_and_import_preserve_post_specific_settings(self, client, admin_headers, content_type):
        if content_type != "posts":
            pytest.skip("post-specific RSS exclusion")

        payload = _make_payload(content_type, "-rss-export")
        payload["exclude_from_rss"] = True
        payload["requires_approval"] = True
        created = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        assert created.status_code == 201

        with get_session_factory()() as session:
            exported_items = export_content_json(session, "posts")
        exported_post = next(item for item in exported_items if item["slug"] == payload["slug"])
        assert exported_post["exclude_from_rss"] is True
        assert exported_post["requires_approval"] is True

        assert (
            client.put(
                f"{BASE}/{content_type}/{created.json()['id']}",
                json={"exclude_from_rss": False},
                headers=admin_headers,
            ).status_code
            == 200
        )
        with get_session_factory()() as session:
            import_result = import_content_json(
                session,
                "posts",
                [{"slug": payload["slug"], "exclude_from_rss": True, "requires_approval": True}],
            )
        assert import_result.errors == []

        restored = client.get(
            f"{BASE}/{content_type}/{created.json()['id']}",
            headers=admin_headers,
        )
        assert restored.status_code == 200
        assert restored.json()["exclude_from_rss"] is True
        assert restored.json()["requires_approval"] is True

    def test_update_does_not_change_historical_view_count(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-view-count")
        payload["view_count"] = 42
        create_resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        item_id = create_resp.json()["id"]

        resp = client.put(
            f"{BASE}/{content_type}/{item_id}",
            json={"title": "Updated without resetting views", "view_count": 0},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated without resetting views"
        assert resp.json()["view_count"] == 42

    def test_create_without_slug_generates_unique_slug(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-auto-slug")
        payload.pop("slug")

        resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)

        assert resp.status_code == 201
        generated_slug = resp.json()["slug"]
        assert generated_slug.isdigit()

    def test_create_missing_title_is_rejected(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-missing-title")
        payload.pop("title")

        resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert isinstance(detail, list)
        assert detail[0]["loc"][-1] == "title"

    def test_create_empty_title_is_rejected(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-empty-title")
        payload["title"] = ""

        resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)

        assert resp.status_code == 422
        assert resp.json()["detail"] == "标题不能为空"

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

    def test_create_public_triggers_subscription_dispatch(self, client, admin_headers, content_type, monkeypatch):
        calls: list[bool] = []
        monkeypatch.setattr(
            crud_service,
            "_dispatch_content_subscriptions_if_needed",
            lambda *args, **kwargs: calls.append(True),
        )

        payload = _make_payload(content_type, "-publish-create")
        payload["visibility"] = "public"
        resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)

        assert resp.status_code == 201
        assert calls == [True]

    def test_update_to_public_triggers_subscription_dispatch(self, client, admin_headers, content_type, monkeypatch):
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
            json={"visibility": "public"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert calls[-1:] == [True]

    def test_update_existing_public_content_does_not_dispatch_subscription(
        self, client, admin_headers, content_type, monkeypatch
    ):
        calls: list[bool] = []
        monkeypatch.setattr(
            crud_service,
            "_dispatch_content_subscriptions_if_needed",
            lambda *args, **kwargs: calls.append(True),
        )

        payload = _make_payload(content_type, "-public-edit")
        payload["visibility"] = "public"
        create_resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        item_id = create_resp.json()["id"]
        calls.clear()

        resp = client.put(
            f"{BASE}/{content_type}/{item_id}",
            json={"title": "Edited public title"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert calls == []

    def test_update_private_to_public_publishes(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-restore")
        payload["visibility"] = "private"
        create_resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        item_id = create_resp.json()["id"]

        resp = client.put(
            f"{BASE}/{content_type}/{item_id}",
            json={"visibility": "public"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["visibility"] == "public"

    def test_update_private_to_private_stays_private(self, client, admin_headers, content_type):
        payload = _make_payload(content_type, "-private-draft-restore")
        payload["visibility"] = "private"
        create_resp = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)
        item_id = create_resp.json()["id"]

        resp = client.put(
            f"{BASE}/{content_type}/{item_id}",
            json={"visibility": "private"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
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

    def test_bulk_visibility(self, client, admin_headers, content_type):
        resp = client.post(
            f"{BASE}/{content_type}/",
            json=_make_payload(content_type, "-bs"),
            headers=admin_headers,
        )
        item_id = resp.json()["id"]

        resp = client.post(
            f"{BASE}/{content_type}/bulk-visibility",
            json={"ids": [item_id], "visibility": "public"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["affected"] == 1

        resp = client.get(f"{BASE}/{content_type}/{item_id}", headers=admin_headers)
        assert "status" not in resp.json()
        assert resp.json()["visibility"] == "public"

    def test_bulk_visibility_public_triggers_subscription_dispatch(
        self, client, admin_headers, content_type, monkeypatch
    ):
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
            f"{BASE}/{content_type}/bulk-visibility",
            json={"ids": [item_id], "visibility": "public"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert calls[-1:] == [True]

    def test_bulk_visibility_public_to_public_does_not_dispatch_subscription(
        self, client, admin_headers, content_type, monkeypatch
    ):
        calls: list[bool] = []
        monkeypatch.setattr(
            crud_service,
            "_dispatch_content_subscriptions_if_needed",
            lambda *args, **kwargs: calls.append(True),
        )

        payload = _make_payload(content_type, "-bs-public-redo")
        payload["visibility"] = "public"
        resp = client.post(
            f"{BASE}/{content_type}/",
            json=payload,
            headers=admin_headers,
        )
        item_id = resp.json()["id"]
        calls.clear()

        resp = client.post(
            f"{BASE}/{content_type}/bulk-visibility",
            json={"ids": [item_id], "visibility": "public"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert calls == []

    def test_bulk_visibility_sets_private_visibility(self, client, admin_headers, content_type):
        resp = client.post(
            f"{BASE}/{content_type}/",
            json=_make_payload(content_type, "-ba"),
            headers=admin_headers,
        )
        item_id = resp.json()["id"]

        resp = client.post(
            f"{BASE}/{content_type}/bulk-visibility",
            json={"ids": [item_id], "visibility": "private"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["affected"] == 1

        resp = client.get(f"{BASE}/{content_type}/{item_id}", headers=admin_headers)
        assert "status" not in resp.json()
        assert resp.json()["visibility"] == "private"


# ── Search & pagination ───────────────────────────────────────────────


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
class TestContentSearchAndPagination:
    def test_search(self, client, admin_headers, content_type):
        # Create an entry with a unique keyword in searchable content fields
        keyword = f"UniqueKeyword{content_type}"
        payload = _make_payload(content_type, "-search")
        payload["body"] = f"Searchable {keyword} Entry"
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
