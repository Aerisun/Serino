from __future__ import annotations

from typing import Any

ADMIN_BASE = "/api/v1/admin"


def _create_post(
    client: Any,
    admin_headers: dict[str, str],
    *,
    slug: str,
    kind: str,
    category: str,
) -> dict[str, Any]:
    response = client.post(
        f"{ADMIN_BASE}/posts/",
        headers=admin_headers,
        json={
            "slug": slug,
            "title": slug,
            "body": "分类隔离测试正文",
            "visibility": "private",
            "kind": kind,
            "category": category,
        },
    )
    assert response.status_code == 201
    return response.json()


def _categories(client: Any, admin_headers: dict[str, str], content_type: str) -> list[dict[str, Any]]:
    response = client.get(
        f"{ADMIN_BASE}/content/category-options",
        headers=admin_headers,
        params={"content_type": content_type},
    )
    assert response.status_code == 200
    return response.json()


def test_post_categories_are_scoped_to_manuscripts_or_notes(client, admin_headers) -> None:
    manuscript_category = "文稿专属分类"
    note_category = "手记专属分类"

    _create_post(
        client,
        admin_headers,
        slug="manuscript-category-scope",
        kind="manuscript",
        category=manuscript_category,
    )
    _create_post(
        client,
        admin_headers,
        slug="note-category-scope",
        kind="note",
        category=note_category,
    )

    manuscript_categories = {item["name"]: item["usage_count"] for item in _categories(client, admin_headers, "posts")}
    note_categories = {item["name"]: item["usage_count"] for item in _categories(client, admin_headers, "notes")}

    assert manuscript_categories[manuscript_category] == 1
    assert note_category not in manuscript_categories
    assert note_categories[note_category] == 1
    assert manuscript_category not in note_categories


def test_switching_a_note_to_manuscript_clears_its_category(client, admin_headers) -> None:
    category = "待清空手记分类"
    note = _create_post(
        client,
        admin_headers,
        slug="clear-note-category-on-kind-switch",
        kind="note",
        category=category,
    )

    updated = client.put(
        f"{ADMIN_BASE}/posts/{note['id']}",
        headers=admin_headers,
        json={"kind": "manuscript"},
    )

    assert updated.status_code == 200
    assert updated.json()["kind"] == "manuscript"
    assert updated.json()["category"] is None
    notes = {item["name"]: item["usage_count"] for item in _categories(client, admin_headers, "notes")}
    assert notes[category] == 0


def test_thoughts_always_clear_categories_from_legacy_clients(client, admin_headers) -> None:
    created = client.post(
        f"{ADMIN_BASE}/thoughts/",
        headers=admin_headers,
        json={
            "slug": "thought-category-scope",
            "title": "碎碎念分类隔离",
            "body": "分类隔离测试正文",
            "visibility": "private",
            "category": "碎碎念专属分类",
        },
    )
    assert created.status_code == 201
    assert created.json()["category"] is None

    updated = client.put(
        f"{ADMIN_BASE}/thoughts/{created.json()['id']}",
        headers=admin_headers,
        json={"category": "旧草稿分类"},
    )

    assert updated.status_code == 200
    assert updated.json()["category"] is None

    categories = client.get(
        f"{ADMIN_BASE}/content/category-options",
        headers=admin_headers,
        params={"content_type": "thoughts"},
    )
    assert categories.status_code == 422
