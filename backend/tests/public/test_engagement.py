from __future__ import annotations

AVATAR_PRESET_KEYS = [
    "shiro",
    "glass",
    "aurora",
    "paper",
    "dawn",
    "pebble",
    "amber",
    "mint",
    "cinder",
    "tide",
    "plum",
    "linen",
]


def _collect_avatar_keys(items: list[dict]) -> set[str]:
    collected: set[str] = set()
    for item in items:
        avatar = item.get("avatar")
        if isinstance(avatar, str) and avatar and not avatar.startswith("http"):
            collected.add(avatar)
        replies = item.get("replies")
        if isinstance(replies, list):
            collected.update(_collect_avatar_keys(replies))
    return collected


def _first_free_avatar_key(client) -> str:
    response = client.get("/api/v1/public/comments/posts/from-zero-design-system")
    assert response.status_code == 200
    used = _collect_avatar_keys(response.json()["items"])
    for key in AVATAR_PRESET_KEYS:
        if key not in used:
            return key
    raise AssertionError("No free avatar preset key available for the test")


def test_read_guestbook_returns_seeded_entries(client) -> None:
    response = client.get("/api/v1/public/guestbook")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["name"] == "Elena Torres"
    assert payload["items"][0]["status"] == "approved"
    assert payload["items"][0]["avatar_url"].startswith("https://api.dicebear.com/")


def test_create_guestbook_accepts_pending_entry(client) -> None:
    response = client.post(
        "/api/v1/public/guestbook",
        json={
            "name": "Test Guest",
            "email": "guest@example.com",
            "website": "https://guest.example.com",
            "body": "Hello from pytest.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["item"]["status"] == "pending"


def test_read_comments_returns_nested_items(client) -> None:
    response = client.get("/api/v1/public/comments/posts/from-zero-design-system")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["author_name"] == "林小北"
    assert payload["items"][0]["status"] == "approved"
    assert payload["items"][0]["avatar_url"]
    assert len(payload["items"][0]["replies"]) == 1
    assert payload["items"][0]["replies"][0]["author_name"] == "Felix"
    assert payload["items"][0]["replies"][0]["parent_id"] == payload["items"][0]["id"]
    assert payload["items"][0]["avatar_url"] != payload["items"][0]["replies"][0]["avatar_url"]


def test_create_comment_accepts_pending_item(client) -> None:
    avatar_key = _first_free_avatar_key(client)
    response = client.post(
        "/api/v1/public/comments/posts/from-zero-design-system",
        json={
            "author_name": "Pytest Reader",
            "author_email": "reader@example.com",
            "body": "很喜欢这篇。",
            "avatar_key": avatar_key,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["item"]["status"] == "pending"
    assert payload["item"]["avatar_url"].startswith("https://api.dicebear.com/")


def test_create_comment_requires_email_for_nickname_binding(client) -> None:
    avatar_key = _first_free_avatar_key(client)
    response = client.post(
        "/api/v1/public/comments/posts/from-zero-design-system",
        json={
            "author_name": "Email Required",
            "body": "没有邮箱就不该通过。",
            "avatar_key": avatar_key,
        },
    )

    assert response.status_code == 422
    assert "邮箱" in response.json()["detail"]


def test_create_comment_binds_nickname_to_email(client) -> None:
    avatar_key = _first_free_avatar_key(client)
    first = client.post(
        "/api/v1/public/comments/posts/from-zero-design-system",
        json={
            "author_name": "Bound Reader",
            "author_email": "bound@example.com",
            "body": "第一次占用昵称。",
            "avatar_key": avatar_key,
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/public/comments/posts/from-zero-design-system",
        json={
            "author_name": "Bound Reader",
            "author_email": "other@example.com",
            "body": "尝试冒用昵称。",
            "avatar_key": avatar_key,
        },
    )

    assert second.status_code == 409
    assert "昵称" in second.json()["detail"]


def test_create_comment_prevents_duplicate_avatar_for_different_names(client) -> None:
    avatar_key = _first_free_avatar_key(client)
    first = client.post(
        "/api/v1/public/comments/posts/from-zero-design-system",
        json={
            "author_name": "Avatar One",
            "author_email": "one@example.com",
            "body": "先占用一个头像。",
            "avatar_key": avatar_key,
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/public/comments/posts/from-zero-design-system",
        json={
            "author_name": "Avatar Two",
            "author_email": "two@example.com",
            "body": "换个名字继续抢同一个头像。",
            "avatar_key": avatar_key,
        },
    )

    assert second.status_code == 409
    assert "头像" in second.json()["detail"]


def test_create_comment_allows_same_name_and_email_to_reuse_avatar(client) -> None:
    avatar_key = _first_free_avatar_key(client)
    first = client.post(
        "/api/v1/public/comments/posts/from-zero-design-system",
        json={
            "author_name": "Repeat Reader",
            "author_email": "repeat@example.com",
            "body": "第一条评论。",
            "avatar_key": avatar_key,
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/public/comments/posts/from-zero-design-system",
        json={
            "author_name": "Repeat Reader",
            "author_email": "repeat@example.com",
            "body": "第二条评论。",
            "avatar_key": avatar_key,
        },
    )

    assert second.status_code == 200
    assert second.json()["item"]["avatar_url"] == first.json()["item"]["avatar_url"]


def test_create_reaction_returns_total(client) -> None:
    response = client.post(
        "/api/v1/public/reactions",
        json={
            "content_type": "posts",
            "content_slug": "from-zero-design-system",
            "reaction_type": "like",
            "client_token": "pytest-token",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reaction_type"] == "like"
    assert payload["total"] >= 3
