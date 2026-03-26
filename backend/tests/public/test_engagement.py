from __future__ import annotations

AVATAR_PICKER_COUNT = 16
AVATAR_POOL_SIZE = 1000

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


def _hash_avatar_seed(value: str) -> int:
    hash_value = 0x811C9DC5
    for character in value:
        hash_value ^= ord(character)
        hash_value = (hash_value * 0x01000193) & 0xFFFFFFFF
    return hash_value


def _next_avatar_random(state: int) -> tuple[int, float]:
    next_state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
    return next_state, next_state / 0x100000000


def _sample_avatar_indexes(email: str, count: int = AVATAR_PICKER_COUNT) -> list[int]:
    normalized = email.strip().lower().replace(" ", "") or "visitor"
    pool = list(range(AVATAR_POOL_SIZE))
    state = _hash_avatar_seed(normalized) or 1

    for index in range(len(pool) - 1, 0, -1):
        state, random_value = _next_avatar_random(state)
        target = int(random_value * (index + 1))
        pool[index], pool[target] = pool[target], pool[index]

    return pool[:count]


def _avatar_seed_for_email(email: str, index: int) -> str:
    normalized = email.strip().lower().replace(" ", "") or "visitor"
    return f"{_hash_avatar_seed(f'{normalized}:{index}'):08x}"


def _avatar_key_for_email(email: str) -> str:
    return _avatar_seed_for_email(email, _sample_avatar_indexes(email, 1)[0])


def _avatar_keys_for_email(email: str) -> list[str]:
    return [_avatar_seed_for_email(email, index) for index in _sample_avatar_indexes(email)]


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


def _update_community_config(**changes) -> None:
    from aerisun.core.db import get_session_factory
    from aerisun.domain.site_config.models import CommunityConfig

    factory = get_session_factory()
    with factory() as session:
        config = session.query(CommunityConfig).first()
        assert config is not None
        for key, value in changes.items():
            setattr(config, key, value)
        session.commit()


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


def test_create_comment_binds_avatar_to_email_seed(client) -> None:
    first_email = "binding-one@example.com"
    second_email = "binding-two@example.com"
    first_candidates = _avatar_keys_for_email(first_email)
    second_candidates = _avatar_keys_for_email(second_email)

    assert len(first_candidates) == AVATAR_PICKER_COUNT
    assert len(set(first_candidates)) == AVATAR_PICKER_COUNT
    assert len(second_candidates) == AVATAR_PICKER_COUNT
    assert len(set(second_candidates)) == AVATAR_PICKER_COUNT
    assert first_candidates != second_candidates

    first = client.post(
        "/api/v1/public/comments/posts/from-zero-design-system",
        json={
            "author_name": "Seed Reader One",
            "author_email": first_email,
            "body": "第一条绑定评论。",
            "avatar_key": first_candidates[0],
        },
    )
    assert first.status_code == 200

    first_repeat = client.post(
        "/api/v1/public/comments/posts/from-zero-design-system",
        json={
            "author_name": "Seed Reader One",
            "author_email": first_email,
            "body": "同邮箱再次评论。",
            "avatar_key": first_candidates[0],
        },
    )
    assert first_repeat.status_code == 200
    assert first_repeat.json()["item"]["avatar_url"] == first.json()["item"]["avatar_url"]

    second = client.post(
        "/api/v1/public/comments/posts/from-zero-design-system",
        json={
            "author_name": "Seed Reader Two",
            "author_email": second_email,
            "body": "第二个邮箱。",
            "avatar_key": second_candidates[0],
        },
    )
    assert second.status_code == 200
    assert second.json()["item"]["avatar_url"] != first.json()["item"]["avatar_url"]


def test_create_comment_rejects_when_anonymous_is_disabled(client) -> None:
    _update_community_config(anonymous_enabled=False)

    response = client.post(
        "/api/v1/public/comments/posts/from-zero-design-system",
        json={
            "author_name": "Visitor",
            "author_email": "visitor@example.com",
            "body": "我想留言。",
        },
    )

    assert response.status_code == 422
    assert "匿名评论" in response.json()["detail"]


def test_create_guestbook_rejects_when_anonymous_is_disabled(client) -> None:
    _update_community_config(anonymous_enabled=False)

    response = client.post(
        "/api/v1/public/guestbook",
        json={
            "name": "Visitor",
            "email": "visitor@example.com",
            "body": "我想留言。",
        },
    )

    assert response.status_code == 422
    assert "匿名留言" in response.json()["detail"]


def test_comment_image_upload_rejects_when_disabled(client) -> None:
    _update_community_config(image_uploader=False)

    response = client.post(
        "/api/v1/public/comment-image",
        files={"file": ("image.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 422
    assert "评论图片上传" in response.json()["detail"]


def test_comment_image_upload_uses_user_asset_upload(client) -> None:
    _update_community_config(image_uploader=True)

    response = client.post(
        "/api/v1/public/comment-image",
        files={"file": ("image.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    url = payload["data"]["url"]
    assert url.startswith("/media/internal/assets/comment/")

    from aerisun.core.db import get_session_factory
    from aerisun.domain.media.models import Asset
    from pathlib import Path

    resource_key = url.removeprefix("/media/")
    factory = get_session_factory()
    with factory() as session:
        asset = session.query(Asset).filter(Asset.resource_key == resource_key).one()

    assert asset.scope == "user"
    assert asset.visibility == "internal"
    assert asset.category == "comment"
    assert asset.file_name == "image.png"
    assert Path(asset.storage_path).is_file()


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
