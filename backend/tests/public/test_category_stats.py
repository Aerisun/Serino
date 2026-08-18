from __future__ import annotations

from typing import Any

import pytest

ADMIN_BASE = "/api/v1/admin"
SITE_BASE = "/api/v1/site"


def _create_content(
    client: Any,
    admin_headers: dict[str, str],
    *,
    content_type: str,
    slug: str,
    category: str | None,
    visibility: str = "public",
    kind: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "slug": slug,
        "title": slug,
        "body": "分类统计测试内容",
        "visibility": visibility,
        "category": category,
    }
    if kind is not None:
        payload["kind"] = kind

    response = client.post(
        f"{ADMIN_BASE}/{content_type}/",
        headers=admin_headers,
        json=payload,
    )
    assert response.status_code == 201, response.text


def test_public_category_stats_are_complete_and_keep_post_kinds_separate(
    client,
    admin_headers,
) -> None:
    article_category = "分类统计文章"
    note_category = "分类统计手记"
    hidden_category = "分类统计私密"

    _create_content(
        client,
        admin_headers,
        content_type="posts",
        slug="category-stats-article-one",
        category=article_category,
        kind="manuscript",
    )
    _create_content(
        client,
        admin_headers,
        content_type="posts",
        slug="category-stats-article-two",
        category=article_category,
        kind="manuscript",
    )
    _create_content(
        client,
        admin_headers,
        content_type="posts",
        slug="category-stats-article-uncategorized",
        category=None,
        kind="manuscript",
    )
    _create_content(
        client,
        admin_headers,
        content_type="posts",
        slug="category-stats-article-private",
        category=hidden_category,
        visibility="private",
        kind="manuscript",
    )
    _create_content(
        client,
        admin_headers,
        content_type="posts",
        slug="category-stats-note",
        category=note_category,
        kind="note",
    )

    posts_response = client.get(f"{SITE_BASE}/category-stats", params={"content_type": "posts"})
    notes_response = client.get(f"{SITE_BASE}/category-stats", params={"content_type": "notes"})
    public_posts = client.get(f"{SITE_BASE}/posts", params={"limit": 1})

    assert posts_response.status_code == 200
    assert notes_response.status_code == 200
    assert public_posts.status_code == 200

    post_payload = posts_response.json()
    note_payload = notes_response.json()
    post_counts = {item["name"]: item["count"] for item in post_payload["items"]}
    note_counts = {item["name"]: item["count"] for item in note_payload["items"]}

    assert post_payload["total"] == public_posts.json()["total"]
    assert post_counts[article_category] == 2
    assert hidden_category not in post_counts
    assert note_category not in post_counts
    assert note_counts[note_category] == 1
    assert article_category not in note_counts


@pytest.mark.parametrize(
    ("content_type", "site_path", "kind"),
    [
        ("posts", "posts", "manuscript"),
        ("posts", "notes", "note"),
        ("excerpts", "excerpts", None),
    ],
)
def test_public_lists_filter_by_category(
    client,
    admin_headers,
    content_type: str,
    site_path: str,
    kind: str | None,
) -> None:
    category = f"{site_path}-筛选分类"
    other_category = f"{site_path}-其他分类"

    _create_content(
        client,
        admin_headers,
        content_type=content_type,
        slug=f"{site_path}-category-match",
        category=category,
        kind=kind,
    )
    _create_content(
        client,
        admin_headers,
        content_type=content_type,
        slug=f"{site_path}-category-other",
        category=other_category,
        kind=kind,
    )

    response = client.get(
        f"{SITE_BASE}/{site_path}",
        params={"category": category, "limit": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["slug"] for item in payload["items"]] == [f"{site_path}-category-match"]
    assert {item["category"] for item in payload["items"]} == {category}


def test_thoughts_ignore_legacy_category_filters_and_do_not_expose_category_stats(
    client,
    admin_headers,
) -> None:
    for suffix, category in (("one", "旧分类一"), ("two", "旧分类二")):
        _create_content(
            client,
            admin_headers,
            content_type="thoughts",
            slug=f"thought-no-category-{suffix}",
            category=category,
        )

    thoughts_response = client.get(
        f"{SITE_BASE}/thoughts",
        params={"category": "旧分类一"},
    )
    unfiltered_thoughts_response = client.get(f"{SITE_BASE}/thoughts")
    stats_response = client.get(
        f"{SITE_BASE}/category-stats",
        params={"content_type": "thoughts"},
    )

    assert thoughts_response.status_code == 200
    assert unfiltered_thoughts_response.status_code == 200
    assert thoughts_response.json()["total"] == unfiltered_thoughts_response.json()["total"]
    assert stats_response.status_code == 422
