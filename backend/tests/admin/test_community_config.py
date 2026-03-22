from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt

from aerisun.core.db import get_session_factory
from aerisun.domain.iam.models import AdminSession, AdminUser


def _create_admin_token(username: str = "community-config-admin") -> str:
    session_factory = get_session_factory()
    token = "community-config-session-token"
    expires_at = datetime.now(UTC) + timedelta(hours=24)

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
    assert current["oauth_providers"] == ["github", "google"]
    assert current["anonymous_enabled"] is True
    assert current["moderation_mode"] == "all_pending"
    assert current["default_sorting"] == "latest"
    assert current["page_size"] == 20
    assert current["guest_avatar_mode"] == "preset"
    assert current["draft_enabled"] is True
    assert current["avatar_presets"][0]["key"] == "shiro"

    payload = {
        "provider": current["provider"],
        "server_url": current["server_url"],
        "surfaces": current["surfaces"],
        "meta": current["meta"],
        "required_meta": current["required_meta"],
        "emoji_presets": current["emoji_presets"],
        "enable_enjoy_search": current["enable_enjoy_search"],
        "image_uploader": current["image_uploader"],
        "login_mode": "oauth",
        "oauth_url": "https://auth.example.com/community",
        "oauth_providers": ["github"],
        "anonymous_enabled": False,
        "moderation_mode": "manual",
        "default_sorting": "oldest",
        "page_size": 30,
        "avatar_presets": [
            {
                "key": "moon",
                "label": "Moon",
                "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Moon",
            }
        ],
        "guest_avatar_mode": "preset",
        "draft_enabled": False,
        "avatar_strategy": current["avatar_strategy"],
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
    assert refreshed["oauth_providers"] == ["github"]
    assert refreshed["anonymous_enabled"] is False
    assert refreshed["moderation_mode"] == "manual"
    assert refreshed["default_sorting"] == "oldest"
    assert refreshed["page_size"] == 30
    assert refreshed["avatar_presets"] == payload["avatar_presets"]
    assert refreshed["guest_avatar_mode"] == "preset"
    assert refreshed["draft_enabled"] is False
