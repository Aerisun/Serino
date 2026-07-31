from __future__ import annotations

from datetime import timedelta

from aerisun.core.db import get_session_factory
from aerisun.core.time import shanghai_now
from aerisun.domain.site_config.models import SiteProfile

ADMIN_BASE = "/api/v1/admin"


def _login_site_user(client, *, email: str = "post-reader@example.com", display_name: str = "Post Reader") -> None:
    response = client.post(
        "/api/v1/site-auth/email",
        json={
            "email": email,
            "display_name": display_name,
            "avatar_url": f"/api/v1/avatars/10.x/notionists/svg?seed={display_name}",
        },
    )
    assert response.status_code == 200
    assert response.json()["authenticated"] is True


def _create_protected_post(client, admin_headers, *, slug: str) -> dict:
    response = client.post(
        f"{ADMIN_BASE}/posts/",
        json={
            "slug": slug,
            "title": f"Protected {slug}",
            "body": "Only approved visitors can read this article.",
            "visibility": "public",
            "requires_approval": True,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    return response.json()


def _set_post_approval_enabled(enabled: bool) -> None:
    with get_session_factory()() as session:
        profile = session.query(SiteProfile).order_by(SiteProfile.created_at.asc()).first()
        assert profile is not None
        profile.feature_flags = {
            **dict(profile.feature_flags or {}),
            "post_access_approval_enabled": enabled,
        }
        session.commit()


def test_post_access_is_scoped_to_one_article_and_can_be_revoked(client, admin_headers) -> None:
    first_post = _create_protected_post(client, admin_headers, slug="approved-first-post")
    second_post = _create_protected_post(client, admin_headers, slug="separate-second-post")

    anonymous_detail = client.get(f"/api/v1/site/posts/{first_post['slug']}")
    assert anonymous_detail.status_code == 401
    assert anonymous_detail.json()["detail"] == "请先登录。"

    _login_site_user(client)

    forbidden_detail = client.get(f"/api/v1/site/posts/{first_post['slug']}")
    assert forbidden_detail.status_code == 403

    state = client.get(f"/api/v1/site/post-access/{first_post['slug']}/me")
    assert state.status_code == 200
    assert state.json()["authenticated"] is True
    assert state.json()["has_access"] is False
    assert state.json()["post_title"] == first_post["title"]

    request_response = client.post(
        f"/api/v1/site/post-access/{first_post['slug']}/requests",
        json={"reason": "想阅读完整文章。"},
    )
    assert request_response.status_code == 201

    updated_request = client.post(
        f"/api/v1/site/post-access/{first_post['slug']}/requests",
        json={"reason": "补充理由：我会尊重内容。"},
    )
    assert updated_request.status_code == 201
    assert updated_request.json()["id"] == request_response.json()["id"]
    assert updated_request.json()["reason"] == "补充理由：我会尊重内容。"

    list_response = client.get(f"{ADMIN_BASE}/moderation/post-access-requests", headers=admin_headers)
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["post_id"] == first_post["id"]
    assert item["post_title"] == first_post["title"]
    assert item["visitor_email"] == "post-reader@example.com"

    expires_at = (shanghai_now() + timedelta(days=7)).isoformat()
    approve_response = client.patch(
        f"{ADMIN_BASE}/moderation/post-access-requests/{item['id']}",
        json={"grant_access": True, "expires_at": expires_at},
        headers=admin_headers,
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["has_access"] is True

    approved_detail = client.get(f"/api/v1/site/posts/{first_post['slug']}")
    assert approved_detail.status_code == 200
    assert approved_detail.headers["cache-control"] == "private, no-store"
    assert approved_detail.headers["vary"] == "Cookie"

    granted_posts = client.get("/api/v1/site/post-access/me")
    assert granted_posts.status_code == 200
    granted_items = granted_posts.json()["items"]
    assert len(granted_items) == 1
    assert granted_items[0]["slug"] == first_post["slug"]
    assert granted_items[0]["title"] == first_post["title"]
    assert granted_items[0]["access_expires_at"] == approve_response.json()["access_expires_at"]
    assert granted_items[0]["remaining_seconds"] > 0

    second_post_detail = client.get(f"/api/v1/site/posts/{second_post['slug']}")
    assert second_post_detail.status_code == 403

    revoke_response = client.patch(
        f"{ADMIN_BASE}/moderation/post-access-requests/{item['id']}",
        json={"revoke_access": True},
        headers=admin_headers,
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["has_access"] is False

    granted_posts_after_revoke = client.get("/api/v1/site/post-access/me")
    assert granted_posts_after_revoke.status_code == 200
    assert granted_posts_after_revoke.json()["items"] == []

    revoked_detail = client.get(f"/api/v1/site/posts/{first_post['slug']}")
    assert revoked_detail.status_code == 403


def test_disabling_post_approval_restores_public_detail_access(client, admin_headers) -> None:
    post = _create_protected_post(client, admin_headers, slug="feature-disabled-post")
    _set_post_approval_enabled(False)

    response = client.get(f"/api/v1/site/posts/{post['slug']}")

    assert response.status_code == 200
