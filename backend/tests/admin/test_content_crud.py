"""Focused integration contracts for the shared admin content CRUD router."""

from __future__ import annotations

import pytest

from aerisun.core.db import get_session_factory
from aerisun.domain.content.import_export_service import export_content_json, import_content_json
from aerisun.domain.crud import service as crud_service

BASE = "/api/v1/admin"
CONTENT_TYPES = ("posts", "diary", "thoughts", "excerpts")
TAGLESS_CONTENT_TYPES = {"diary", "thoughts", "excerpts"}


def _make_payload(content_type: str, suffix: str = "") -> dict:
    return {
        "slug": f"test-{content_type}-slug{suffix}",
        "title": f"Test {content_type.title()} Title{suffix}",
        "body": f"Test {content_type} body content{suffix}",
        "tags": ["test"],
        "visibility": "private",
    }


@pytest.mark.parametrize("content_type", CONTENT_TYPES)
def test_content_routes_share_crud_lifecycle(client, admin_headers, content_type: str) -> None:
    payload = _make_payload(content_type)

    created_response = client.post(f"{BASE}/{content_type}/", json=payload, headers=admin_headers)

    assert created_response.status_code == 201
    created = created_response.json()
    assert created["slug"] == payload["slug"]
    assert created["title"] == payload["title"]
    assert created["body"] == payload["body"]
    assert created["tags"] == ([] if content_type in TAGLESS_CONTENT_TYPES else ["test"])
    assert created["visibility"] == "private"
    assert "status" not in created
    if content_type == "posts":
        assert created["exclude_from_rss"] is False
        assert created["requires_approval"] is False
        assert created["kind"] == "manuscript"
    else:
        assert "exclude_from_rss" not in created
        assert "requires_approval" not in created

    item_id = created["id"]
    read_response = client.get(f"{BASE}/{content_type}/{item_id}", headers=admin_headers)
    assert read_response.status_code == 200
    assert read_response.json()["title"] == payload["title"]

    updated_response = client.put(
        f"{BASE}/{content_type}/{item_id}",
        json={"title": "Updated Title", "visibility": "public"},
        headers=admin_headers,
    )
    assert updated_response.status_code == 200
    assert updated_response.json()["title"] == "Updated Title"
    assert updated_response.json()["slug"] == payload["slug"]
    assert updated_response.json()["visibility"] == "public"

    list_response = client.get(f"{BASE}/{content_type}/", headers=admin_headers)
    assert list_response.status_code == 200
    assert any(item["id"] == item_id for item in list_response.json()["items"])

    assert client.delete(f"{BASE}/{content_type}/{item_id}", headers=admin_headers).status_code == 204
    assert client.get(f"{BASE}/{content_type}/{item_id}", headers=admin_headers).status_code == 404


def test_diary_preserves_presentation_fields(client, admin_headers) -> None:
    payload = {**_make_payload("diary", "-mood-weather"), "mood": "calm", "weather": "overcast"}

    created = client.post(f"{BASE}/diary/", json=payload, headers=admin_headers)

    assert created.status_code == 201
    read = client.get(f"{BASE}/diary/{created.json()['id']}", headers=admin_headers)
    assert read.status_code == 200
    assert read.json()["mood"] == "calm"
    assert read.json()["weather"] == "overcast"


def test_post_specific_settings_validate_and_update(client, admin_headers) -> None:
    payload = {
        **_make_payload("posts", "-settings"),
        "exclude_from_rss": True,
        "requires_approval": True,
        "kind": "note",
    }

    created = client.post(f"{BASE}/posts/", json=payload, headers=admin_headers)

    assert created.status_code == 201
    assert created.json()["exclude_from_rss"] is True
    assert created.json()["requires_approval"] is True
    assert created.json()["kind"] == "note"

    updated = client.put(
        f"{BASE}/posts/{created.json()['id']}",
        json={"exclude_from_rss": False, "requires_approval": False, "kind": "manuscript"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["exclude_from_rss"] is False
    assert updated.json()["requires_approval"] is False
    assert updated.json()["kind"] == "manuscript"

    invalid_payload = {**_make_payload("posts", "-invalid-kind"), "kind": "invalid"}
    assert client.post(f"{BASE}/posts/", json=invalid_payload, headers=admin_headers).status_code == 422


def test_post_json_roundtrip_preserves_specific_settings(client, admin_headers) -> None:
    payload = {
        **_make_payload("posts", "-json-roundtrip"),
        "exclude_from_rss": True,
        "requires_approval": True,
        "kind": "note",
    }
    created = client.post(f"{BASE}/posts/", json=payload, headers=admin_headers)
    assert created.status_code == 201

    with get_session_factory()() as session:
        exported = next(item for item in export_content_json(session, "posts") if item["slug"] == payload["slug"])
    assert exported["exclude_from_rss"] is True
    assert exported["requires_approval"] is True
    assert exported["kind"] == "note"

    assert (
        client.put(
            f"{BASE}/posts/{created.json()['id']}",
            json={"exclude_from_rss": False, "requires_approval": False, "kind": "manuscript"},
            headers=admin_headers,
        ).status_code
        == 200
    )
    with get_session_factory()() as session:
        result = import_content_json(
            session,
            "posts",
            [
                {
                    "slug": payload["slug"],
                    "exclude_from_rss": True,
                    "requires_approval": True,
                    "kind": "note",
                }
            ],
        )
    assert result.errors == []

    restored = client.get(f"{BASE}/posts/{created.json()['id']}", headers=admin_headers)
    assert restored.json()["exclude_from_rss"] is True
    assert restored.json()["requires_approval"] is True
    assert restored.json()["kind"] == "note"


def test_content_creation_validates_titles_and_generates_slugs(client, admin_headers) -> None:
    automatic_slug = _make_payload("posts", "-automatic-slug")
    automatic_slug.pop("slug")
    created = client.post(f"{BASE}/posts/", json=automatic_slug, headers=admin_headers)
    assert created.status_code == 201
    assert created.json()["slug"].isdigit()

    missing_title = _make_payload("posts", "-missing-title")
    missing_title.pop("title")
    missing = client.post(f"{BASE}/posts/", json=missing_title, headers=admin_headers)
    assert missing.status_code == 422
    assert missing.json()["detail"][0]["loc"][-1] == "title"

    empty_title = {**_make_payload("posts", "-empty-title"), "title": ""}
    empty = client.post(f"{BASE}/posts/", json=empty_title, headers=admin_headers)
    assert empty.status_code == 422
    assert empty.json()["detail"] == "标题不能为空"


def test_content_slug_is_unique_across_types(client, admin_headers) -> None:
    shared_slug = "shared-content-slug"
    post_payload = {**_make_payload("posts", "-shared"), "slug": shared_slug}
    diary_payload = {**_make_payload("diary", "-shared"), "slug": shared_slug}

    assert client.post(f"{BASE}/posts/", json=post_payload, headers=admin_headers).status_code == 201
    conflict = client.post(f"{BASE}/diary/", json=diary_payload, headers=admin_headers)

    assert conflict.status_code == 409
    assert conflict.json()["detail"] == f"slug '{shared_slug}' 已存在"


def test_content_update_ignores_client_view_count(client, admin_headers) -> None:
    payload = {**_make_payload("posts", "-view-count"), "view_count": 42}
    created = client.post(f"{BASE}/posts/", json=payload, headers=admin_headers)

    updated = client.put(
        f"{BASE}/posts/{created.json()['id']}",
        json={"title": "Updated without resetting views", "view_count": 0},
        headers=admin_headers,
    )

    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated without resetting views"
    assert updated.json()["view_count"] == 42


def test_publish_transitions_dispatch_subscriptions_once(client, admin_headers, monkeypatch) -> None:
    calls: list[bool] = []
    monkeypatch.setattr(
        crud_service,
        "_dispatch_content_subscriptions_if_needed",
        lambda *args, **kwargs: calls.append(True),
    )

    public_payload = {**_make_payload("posts", "-public-create"), "visibility": "public"}
    public_item = client.post(f"{BASE}/posts/", json=public_payload, headers=admin_headers)
    assert public_item.status_code == 201
    assert calls == [True]

    calls.clear()
    assert (
        client.put(
            f"{BASE}/posts/{public_item.json()['id']}",
            json={"title": "Edited public title"},
            headers=admin_headers,
        ).status_code
        == 200
    )
    assert calls == []

    private_item = client.post(
        f"{BASE}/posts/",
        json=_make_payload("posts", "-private-publish"),
        headers=admin_headers,
    )
    calls.clear()
    assert (
        client.put(
            f"{BASE}/posts/{private_item.json()['id']}",
            json={"visibility": "public"},
            headers=admin_headers,
        ).status_code
        == 200
    )
    assert calls == [True]


def test_content_bulk_operations(client, admin_headers, monkeypatch) -> None:
    calls: list[bool] = []
    monkeypatch.setattr(
        crud_service,
        "_dispatch_content_subscriptions_if_needed",
        lambda *args, **kwargs: calls.append(True),
    )
    ids = [
        client.post(
            f"{BASE}/posts/",
            json=_make_payload("posts", f"-bulk-{index}"),
            headers=admin_headers,
        ).json()["id"]
        for index in range(2)
    ]

    visibility = client.post(
        f"{BASE}/posts/bulk-visibility",
        json={"ids": ids, "visibility": "public"},
        headers=admin_headers,
    )
    assert visibility.status_code == 200
    assert visibility.json()["affected"] == 2
    assert calls == [True]
    assert client.get(f"{BASE}/posts/{ids[0]}", headers=admin_headers).json()["visibility"] == "public"

    calls.clear()
    unchanged = client.post(
        f"{BASE}/posts/bulk-visibility",
        json={"ids": ids, "visibility": "public"},
        headers=admin_headers,
    )
    assert unchanged.status_code == 200
    assert calls == []

    private = client.post(
        f"{BASE}/posts/bulk-visibility",
        json={"ids": ids, "visibility": "private"},
        headers=admin_headers,
    )
    assert private.status_code == 200
    assert private.json()["affected"] == 2
    assert calls == []
    assert client.get(f"{BASE}/posts/{ids[0]}", headers=admin_headers).json()["visibility"] == "private"

    deleted = client.post(
        f"{BASE}/posts/bulk-delete",
        json={"ids": ids},
        headers=admin_headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["affected"] == 2
    assert client.get(f"{BASE}/posts/{ids[0]}", headers=admin_headers).status_code == 404


def test_content_router_rejects_unauthenticated_requests(client) -> None:
    assert client.get(f"{BASE}/posts/").status_code in (401, 403)
    assert client.post(f"{BASE}/posts/", json=_make_payload("posts")).status_code in (401, 403)


def test_content_list_search_and_pagination(client, admin_headers) -> None:
    keyword = "UniqueContentKeyword"
    for index in range(3):
        payload = _make_payload("posts", f"-search-{index}")
        payload["title"] = f"{keyword} {index}"
        client.post(f"{BASE}/posts/", json=payload, headers=admin_headers)

    response = client.get(
        f"{BASE}/posts/",
        params={"search": keyword, "page": 1, "page_size": 2},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["page"] == 1
    assert response.json()["page_size"] == 2
    assert response.json()["total"] == 3
    assert len(response.json()["items"]) == 2
