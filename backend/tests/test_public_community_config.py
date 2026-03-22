from __future__ import annotations

from aerisun.core.db import get_session_factory
from aerisun.domain.site_config.models import CommunityConfig
from aerisun.core.seed import seed_reference_data
from aerisun.core.settings import get_settings


def test_seed_reference_data_backfills_blank_community_server_url(client) -> None:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        config = session.query(CommunityConfig).first()
        assert config is not None
        config.server_url = ""
        session.commit()
    finally:
        session.close()

    seed_reference_data()

    session = session_factory()
    try:
        config = session.query(CommunityConfig).first()
        assert config is not None
        assert config.server_url == get_settings().waline_server_url
    finally:
        session.close()

    response = client.get("/api/v1/public/community-config")
    assert response.status_code == 200

    payload = response.json()
    assert payload["server_url"] == get_settings().waline_server_url
    assert payload["provider"] == "waline"
