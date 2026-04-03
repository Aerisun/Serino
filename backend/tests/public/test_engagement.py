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
    response = client.get("/api/v1/site-interactions/comments/posts/from-zero-design-system")
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


def _login_site_user(client, *, email: str, display_name: str) -> None:
    _login_site_user_with_options(client, email=email, display_name=display_name)


def _login_site_user_with_options(
    client,
    *,
    email: str,
    display_name: str,
    admin_password: str | None = None,
) -> None:
    response = client.post(
        "/api/v1/site-auth/email",
        json={
            "email": email,
            "display_name": display_name,
            "avatar_url": f"https://api.dicebear.com/9.x/notionists/svg?seed={display_name}",
            **({"admin_password": admin_password} if admin_password is not None else {}),
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["requires_profile"] is False


def _bind_admin_identity_by_email(*, email: str) -> None:
    import bcrypt

    from aerisun.core.db import get_session_factory
    from aerisun.domain.iam.models import AdminUser
    from aerisun.domain.site_auth.admin_binding import bind_site_admin_identity_by_email
    from aerisun.domain.site_auth.models import SiteAuthConfig
    from aerisun.domain.site_auth.schemas import SiteAdminEmailIdentityBindRequest

    factory = get_session_factory()
    with factory() as session:
        admin_user = session.query(AdminUser).filter(AdminUser.username == "comment-admin").first()
        if admin_user is None:
            admin_user = AdminUser(
                username="comment-admin",
                password_hash=bcrypt.hashpw(b"comment-password", bcrypt.gensalt()).decode(),
            )
            session.add(admin_user)
            session.flush()

        config = session.query(SiteAuthConfig).first()
        assert config is not None
        config.admin_email_enabled = True
        config.admin_email_password_hash = bcrypt.hashpw(
            b"comment-password",
            bcrypt.gensalt(),
        ).decode()
        session.commit()

        bind_site_admin_identity_by_email(
            session,
            SiteAdminEmailIdentityBindRequest(email=email),
            admin_user_id=admin_user.id,
        )


def _seed_public_comment(
    *,
    nick: str,
    mail: str | None,
    body: str,
    avatar_key: str | None = None,
    avatar_url: str | None = None,
) -> None:
    from aerisun.domain.waline.service import build_comment_path, create_waline_record

    create_waline_record(
        comment=body,
        nick=nick,
        mail=mail,
        link=None,
        status="approved",
        url=build_comment_path("posts", "from-zero-design-system"),
        avatar_key=avatar_key or f"{nick}-avatar",
        avatar_url=avatar_url or f"https://api.dicebear.com/9.x/notionists/svg?seed={nick}",
    )


def _flatten_comments(items: list[dict]) -> list[dict]:
    flattened: list[dict] = []
    for item in items:
        flattened.append(item)
        replies = item.get("replies")
        if isinstance(replies, list):
            flattened.extend(_flatten_comments(replies))
    return flattened


def test_read_guestbook_returns_seeded_entries(client) -> None:
    response = client.get("/api/v1/site-interactions/guestbook")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 2
    assert payload["total"] == 2
    assert payload["page"] == 1
    assert payload["page_size"] == 20
    assert payload["has_more"] is False
    assert {item["name"] for item in payload["items"]} == {"Elena Torres", "纸鹤"}
    assert all(item["status"] == "approved" for item in payload["items"])
    assert all(item["avatar_url"].startswith("https://api.dicebear.com/") for item in payload["items"])


def test_create_guestbook_accepts_pending_entry(client) -> None:
    _login_site_user(client, email="guest@example.com", display_name="Test Guest")

    response = client.post(
        "/api/v1/site-interactions/guestbook",
        json={
            "name": "Ignored Name",
            "email": "ignored@example.com",
            "website": "https://guest.example.com",
            "body": "Hello from pytest.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["item"]["status"] == "pending"
    assert payload["item"]["name"] == "Test Guest"
    assert payload["item"]["website"] == "https://guest.example.com"


def test_create_guestbook_requires_login(client) -> None:
    response = client.post(
        "/api/v1/site-interactions/guestbook",
        json={
            "name": "Visitor",
            "email": "visitor@example.com",
            "body": "我想留言。",
        },
    )

    assert response.status_code == 422
    assert "登录后才能留言" in response.json()["detail"]


def test_read_comments_returns_nested_items(client) -> None:
    response = client.get("/api/v1/site-interactions/comments/posts/from-zero-design-system")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["total"] == 1
    assert payload["page"] == 1
    assert payload["page_size"] == 20
    assert payload["has_more"] is False
    assert payload["items"][0]["author_name"] == "林小北"
    assert payload["items"][0]["status"] == "approved"
    assert payload["items"][0]["avatar_url"]
    assert len(payload["items"][0]["replies"]) == 1
    assert payload["items"][0]["replies"][0]["author_name"] == "Felix"
    assert payload["items"][0]["replies"][0]["parent_id"] == payload["items"][0]["id"]
    assert payload["items"][0]["replies"][0]["is_author"] is False
    assert payload["items"][0]["avatar_url"] != payload["items"][0]["replies"][0]["avatar_url"]


def test_read_comments_supports_pagination(client) -> None:
    _seed_public_comment(nick="Page One", mail="page-one@example.com", body="第一页测试评论")
    _seed_public_comment(nick="Page Two", mail="page-two@example.com", body="第二页测试评论")

    first = client.get(
        "/api/v1/site-interactions/comments/posts/from-zero-design-system",
        params={"page": 1, "page_size": 2},
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["page"] == 1
    assert first_payload["page_size"] == 2
    assert first_payload["total"] >= 3
    assert len(first_payload["items"]) == 2
    assert first_payload["has_more"] is True

    second = client.get(
        "/api/v1/site-interactions/comments/posts/from-zero-design-system",
        params={"page": 2, "page_size": 2},
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["page"] == 2
    assert second_payload["page_size"] == 2
    assert second_payload["total"] == first_payload["total"]
    assert len(second_payload["items"]) >= 1
    assert {item["id"] for item in first_payload["items"]}.isdisjoint({item["id"] for item in second_payload["items"]})


def test_create_comment_accepts_pending_item(client) -> None:
    _login_site_user(client, email="reader@example.com", display_name="Pytest Reader")

    response = client.post(
        "/api/v1/site-interactions/comments/posts/from-zero-design-system",
        json={
            "author_name": "Ignored Name",
            "author_email": "ignored@example.com",
            "body": "很喜欢这篇。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["item"]["status"] == "pending"
    assert payload["item"]["author_name"] == "Pytest Reader"
    assert payload["item"]["avatar_url"].startswith("https://api.dicebear.com/")


def test_read_comments_marks_email_bound_admin_identity(client) -> None:
    _bind_admin_identity_by_email(email="owner@example.com")
    _seed_public_comment(
        nick="并不是站点标题",
        mail="owner@example.com",
        body="邮箱绑定管理员评论",
    )

    response = client.get("/api/v1/site-interactions/comments/posts/from-zero-design-system")

    assert response.status_code == 200
    payload = response.json()
    comment = next(item for item in _flatten_comments(payload["items"]) if item["body"] == "邮箱绑定管理员评论")
    assert comment["author_name"] == "Felix"
    assert comment["is_author"] is True
    assert "/media/internal/assets/hero-image/" in comment["avatar_url"]


def test_create_comment_marks_bound_admin_user_as_author(client) -> None:
    _bind_admin_identity_by_email(email="admin-comment@example.com")
    _login_site_user_with_options(
        client,
        email="admin-comment@example.com",
        display_name="Comment Admin",
        admin_password="comment-password",
    )

    response = client.post(
        "/api/v1/site-interactions/comments/posts/from-zero-design-system",
        json={
            "author_name": "Ignored Name",
            "author_email": "ignored@example.com",
            "body": "管理员实际发出的评论。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["item"]["author_name"] == "Felix"
    assert payload["item"]["is_author"] is True
    assert payload["item"]["avatar"] == "site-admin"
    assert "/media/internal/assets/hero-image/" in payload["item"]["avatar_url"]


def test_read_guestbook_marks_email_bound_admin_identity(client) -> None:
    from aerisun.domain.waline.service import build_comment_path, create_waline_record

    _bind_admin_identity_by_email(email="guestbook-owner@example.com")
    create_waline_record(
        comment="管理员留言",
        nick="并不是站点标题",
        mail="guestbook-owner@example.com",
        link=None,
        status="approved",
        url=build_comment_path("guestbook", "guestbook"),
        avatar_key="guestbook-owner-avatar",
        avatar_url="https://api.dicebear.com/9.x/notionists/svg?seed=guestbook-owner",
    )

    response = client.get("/api/v1/site-interactions/guestbook")

    assert response.status_code == 200
    payload = response.json()
    entry = next(item for item in payload["items"] if item["body"] == "管理员留言")
    assert entry["name"] == "Felix"
    assert entry["is_author"] is True
    assert "/media/internal/assets/hero-image/" in entry["avatar_url"]


def test_create_guestbook_marks_bound_admin_user_as_author(client) -> None:
    _bind_admin_identity_by_email(email="admin-guestbook@example.com")
    _login_site_user_with_options(
        client,
        email="admin-guestbook@example.com",
        display_name="Guestbook Admin",
        admin_password="comment-password",
    )

    response = client.post(
        "/api/v1/site-interactions/guestbook",
        json={
            "name": "Ignored Name",
            "email": "ignored@example.com",
            "body": "管理员实际发出的留言。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["item"]["name"] == "Felix"
    assert payload["item"]["is_author"] is True
    assert payload["item"]["avatar"] == "site-admin"
    assert "/media/internal/assets/hero-image/" in payload["item"]["avatar_url"]


def test_create_comment_requires_login(client) -> None:
    response = client.post(
        "/api/v1/site-interactions/comments/posts/from-zero-design-system",
        json={
            "author_name": "Visitor",
            "author_email": "visitor@example.com",
            "body": "没有登录就不该通过。",
        },
    )

    assert response.status_code == 422
    assert "登录后才能发表评论" in response.json()["detail"]


def test_create_comment_rejects_email_login_when_disabled_for_comments(client) -> None:
    _login_site_user(client, email="email-reader@example.com", display_name="Email Reader")
    _update_community_config(anonymous_enabled=False)

    response = client.post(
        "/api/v1/site-interactions/comments/posts/from-zero-design-system",
        json={
            "author_name": "Ignored Name",
            "author_email": "ignored@example.com",
            "body": "邮箱登录不该继续评论。",
        },
    )
    assert response.status_code == 422
    assert "邮箱登录评论" in response.json()["detail"]


def test_create_guestbook_rejects_email_login_when_disabled_for_comments(client) -> None:
    _login_site_user(client, email="guest-reader@example.com", display_name="Guest Reader")
    _update_community_config(anonymous_enabled=False)

    response = client.post(
        "/api/v1/site-interactions/guestbook",
        json={
            "name": "Ignored Name",
            "email": "ignored@example.com",
            "body": "邮箱登录不该继续留言。",
        },
    )

    assert response.status_code == 422
    assert "邮箱登录留言" in response.json()["detail"]


def test_comment_image_upload_rejects_when_disabled(client) -> None:
    _update_community_config(image_uploader=False)

    response = client.post(
        "/api/v1/site-interactions/comment-image",
        files={"file": ("image.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 422
    assert "评论图片上传" in response.json()["detail"]


def test_comment_image_upload_rejects_when_exceeding_configured_size_limit(client) -> None:
    _update_community_config(image_uploader=True, image_max_bytes=1024)

    response = client.post(
        "/api/v1/site-interactions/comment-image",
        files={"file": ("image.png", b"x" * 2048, "image/png")},
    )

    assert response.status_code == 413
    assert "图片过大" in response.json()["detail"]


def test_comment_image_upload_uses_user_asset_upload(client) -> None:
    _update_community_config(image_uploader=True)

    response = client.post(
        "/api/v1/site-interactions/comment-image",
        files={"file": ("image.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    url = payload["data"]["url"]
    assert url.startswith("/media/internal/assets/comment/")

    from pathlib import Path

    from aerisun.core.db import get_session_factory
    from aerisun.domain.media.models import Asset

    resource_key = url.removeprefix("/media/")
    factory = get_session_factory()
    with factory() as session:
        asset = session.query(Asset).filter(Asset.resource_key == resource_key).one()

    assert asset.scope == "user"
    assert asset.visibility == "internal"
    assert asset.category == "comment"
    assert asset.file_name == "image.png"
    assert Path(asset.storage_path).is_file()


def test_comment_image_upload_with_oss_queues_async_mirror(monkeypatch, client) -> None:
    _update_community_config(image_uploader=True)

    from pathlib import Path

    from aerisun.core.base import utcnow
    from aerisun.core.db import get_session_factory
    from aerisun.domain.media import object_storage as media_object_storage
    from aerisun.domain.media import service as media_service
    from aerisun.domain.media.models import Asset, AssetMirrorQueueItem

    class _Provider:
        def upload_bytes(self, *, object_key: str, data: bytes, content_type: str | None):
            return media_object_storage.ObjectHead(
                content_length=len(data),
                content_type=content_type,
                etag="etag-comment-upload",
                last_modified=utcnow(),
            )

    monkeypatch.setattr(media_service, "build_object_storage_provider", lambda session: _Provider())
    monkeypatch.setattr(media_object_storage, "build_object_storage_provider", lambda session: _Provider())

    response = client.post(
        "/api/v1/site-interactions/comment-image",
        files={"file": ("image.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 200
    url = response.json()["data"]["url"]
    resource_key = url.removeprefix("/media/")

    with get_session_factory()() as session:
        asset = session.query(Asset).filter(Asset.resource_key == resource_key).one()
        mirrors = session.query(AssetMirrorQueueItem).filter_by(asset_id=asset.id).all()

    assert asset.scope == "user"
    assert asset.visibility == "internal"
    assert asset.category == "comment"
    assert asset.file_name == "image.png"
    assert asset.remote_status == "available"
    assert asset.mirror_status == "queued"
    assert len(mirrors) == 1
    assert mirrors[0].status == "queued"
    assert mirrors[0].object_key == resource_key
    assert not Path(asset.storage_path).exists()


def test_create_reaction_returns_total(client) -> None:
    response = client.post(
        "/api/v1/site-interactions/reactions",
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
