from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def rate_limited_client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Client with rate limiting enabled for testing rate limit behavior."""
    store_dir = tmp_path / "store"
    monkeypatch.setenv("AERISUN_STORE_DIR", str(store_dir))
    monkeypatch.setenv("AERISUN_DATA_DIR", str(store_dir))
    monkeypatch.setenv("AERISUN_MEDIA_DIR", str(store_dir / "media"))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(store_dir / "secrets"))
    monkeypatch.setenv("AERISUN_DB_PATH", str(store_dir / "aerisun.db"))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(store_dir / "waline.db"))
    monkeypatch.setenv("AERISUN_FEED_CRAWL_ENABLED", "false")

    from aerisun.core.db import get_engine, get_session_factory
    from aerisun.core.rate_limit import limiter
    from aerisun.core.seed import seed_reference_data
    from aerisun.core.settings import get_settings

    limiter.enabled = True
    limiter.reset()

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    seed_reference_data()

    from aerisun.core.app_factory import create_app

    with TestClient(create_app()) as test_client:
        yield test_client

    limiter.enabled = False
    engine = get_engine()
    engine.dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()


def test_guestbook_rate_limited(rate_limited_client):
    """Guestbook POST should be rate limited to 5/minute."""
    for i in range(5):
        resp = rate_limited_client.post(
            "/api/v1/public/guestbook",
            json={"name": f"user{i}", "body": f"msg {i}"},
        )
        assert resp.status_code != 429, f"Request {i + 1} should not be rate limited"

    resp = rate_limited_client.post(
        "/api/v1/public/guestbook",
        json={"name": "user6", "body": "msg 6"},
    )
    assert resp.status_code == 429


def test_reactions_rate_limited(rate_limited_client):
    """Reactions POST should be rate limited to 10/minute."""
    for i in range(10):
        resp = rate_limited_client.post(
            "/api/v1/public/reactions",
            json={
                "content_type": "posts",
                "content_slug": "nonexistent",
                "reaction_type": "like",
                "client_token": f"tok-{i}",
            },
        )
        # May be 404 (nonexistent content) but should not be 429
        assert resp.status_code != 429, f"Request {i + 1} should not be rate limited"

    resp = rate_limited_client.post(
        "/api/v1/public/reactions",
        json={
            "content_type": "posts",
            "content_slug": "nonexistent",
            "reaction_type": "like",
            "client_token": "tok-11",
        },
    )
    assert resp.status_code == 429
