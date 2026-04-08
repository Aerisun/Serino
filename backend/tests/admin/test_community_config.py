from __future__ import annotations

from datetime import timedelta

import bcrypt

from aerisun.core.db import get_session_factory
from aerisun.core.time import shanghai_now
from aerisun.domain.iam.models import AdminSession, AdminUser


def _create_admin_token(username: str = "community-config-admin") -> str:
    session_factory = get_session_factory()
    token = "community-config-session-token"
    expires_at = shanghai_now() + timedelta(hours=24)

    with session_factory() as session:
        user = session.query(AdminUser).filter(AdminUser.username == username).first()
        if user is None:
            user = AdminUser(
                username=username,
                password_hash=bcrypt.hashpw(b"community-config-password", bcrypt.gensalt()).decode(),
            )
            session.add(user)
            session.flush()

        existing = session.query(AdminSession).filter(AdminSession.session_token == token).first()
        if existing is None:
            session.add(
                AdminSession(
                    admin_user_id=user.id,
                    session_token=token,
                    expires_at=expires_at,
                )
            )
        else:
            existing.expires_at = expires_at
        session.commit()

    return token


def test_admin_community_config_round_trip(client) -> None:
    token = _create_admin_token()
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/admin/site-config/community-config", headers=headers)
    assert response.status_code == 200
    current = response.json()
    assert [item["key"] for item in current["surfaces"]] == [
        "posts",
        "diary",
        "guestbook",
        "friends",
        "thoughts",
        "excerpts",
    ]
    assert current["anonymous_enabled"] is True
    assert current["moderation_mode"] == "all_pending"
    assert current["default_sorting"] == "latest"
    assert current["page_size"] == 20
    assert current["avatar_helper_copy"] == "登录后评论会绑定到当前邮箱或第三方身份，邮箱不会公开显示。"

    payload = {
        "provider": current["provider"],
        "server_url": current["server_url"],
        "surfaces": current["surfaces"],
        "meta": current["meta"],
        "required_meta": current["required_meta"],
        "emoji_presets": current["emoji_presets"],
        "image_uploader": current["image_uploader"],
        "anonymous_enabled": False,
        "moderation_mode": "no_review",
        "default_sorting": "oldest",
        "page_size": 30,
        "avatar_helper_copy": "测试留言头像库",
        "migration_state": "configured",
    }

    response = client.put("/api/v1/admin/site-config/community-config", headers=headers, json=payload)
    assert response.status_code == 200
    updated = response.json()
    for key, value in payload.items():
        assert updated[key] == value

    response = client.get("/api/v1/admin/site-config/community-config", headers=headers)
    assert response.status_code == 200
    refreshed = response.json()
    assert "enable_enjoy_search" not in refreshed
    assert refreshed["anonymous_enabled"] is False
    assert refreshed["moderation_mode"] == "no_review"
    assert refreshed["default_sorting"] == "oldest"
    assert refreshed["page_size"] == 30
    assert refreshed["avatar_helper_copy"] == "测试留言头像库"


def test_admin_community_config_normalizes_legacy_moderation_mode(client) -> None:
    token = _create_admin_token("community-config-admin-legacy")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.put(
        "/api/v1/admin/site-config/community-config",
        headers=headers,
        json={"moderation_mode": "manual"},
    )
    assert response.status_code == 200
    assert response.json()["moderation_mode"] == "all_pending"
