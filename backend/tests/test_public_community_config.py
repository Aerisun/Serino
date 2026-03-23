from __future__ import annotations

from aerisun.core.db import get_session_factory
from aerisun.core.seed import seed_reference_data
from aerisun.core.settings import get_settings
from aerisun.domain.site_config.models import CommunityConfig


def test_seed_reference_data_normalizes_community_comment_config(client) -> None:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        config = session.query(CommunityConfig).first()
        assert config is not None
        config.server_url = "http://localhost:8360/"
        config.surfaces = list(config.surfaces[:3])
        session.commit()
    finally:
        session.close()

    seed_reference_data()

    session = session_factory()
    try:
        config = session.query(CommunityConfig).first()
        assert config is not None
        assert config.server_url == get_settings().waline_server_url
        assert [item["key"] for item in config.surfaces] == ["posts", "diary", "guestbook", "thoughts", "excerpts"]
    finally:
        session.close()

    response = client.get("/api/v1/public/community-config")
    assert response.status_code == 200

    payload = response.json()
    assert payload["server_url"] == get_settings().waline_server_url
    assert [item["key"] for item in payload["surfaces"]] == ["posts", "diary", "guestbook", "thoughts", "excerpts"]
    assert payload["provider"] == "waline"
    assert payload["oauth_providers"] == ["github", "google"]
    assert payload["anonymous_enabled"] is True
    assert payload["moderation_mode"] == "all_pending"
    assert payload["default_sorting"] == "latest"
    assert payload["page_size"] == 20
    assert payload["guest_avatar_mode"] == "preset"
    assert payload["draft_enabled"] is True
    assert payload["avatar_presets"][0]["key"] == "shiro"
