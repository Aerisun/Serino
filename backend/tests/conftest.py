from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    store_dir = tmp_path / "store"
    data_dir = store_dir
    media_dir = store_dir / "media"
    secrets_dir = store_dir / "secrets"
    db_path = store_dir / "aerisun.db"
    waline_db_path = store_dir / "waline.db"

    monkeypatch.setenv("AERISUN_STORE_DIR", str(store_dir))
    monkeypatch.setenv("AERISUN_DATA_DIR", str(data_dir))
    monkeypatch.setenv("AERISUN_MEDIA_DIR", str(media_dir))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(secrets_dir))
    monkeypatch.setenv("AERISUN_DB_PATH", str(db_path))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(waline_db_path))
    monkeypatch.setenv("AERISUN_SEED_REFERENCE_DATA", "true")

    from aerisun.core.db import get_engine, get_session_factory
    from aerisun.core.rate_limit import limiter
    from aerisun.core.settings import get_settings

    limiter.enabled = False

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    from aerisun.main import app

    with TestClient(app) as test_client:
        yield test_client

    engine = get_engine()
    engine.dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()


@pytest.fixture()
def admin_headers(client) -> dict[str, str]:
    """Create an admin user and session, return authentication headers."""
    from datetime import datetime, timedelta, timezone

    import bcrypt

    from aerisun.core.db import get_session_factory
    from aerisun.domain.iam.models import AdminSession, AdminUser

    factory = get_session_factory()
    token = "test-admin-session-token"
    with factory() as session:
        user = (
            session.query(AdminUser)
            .filter(AdminUser.username == "test-admin")
            .first()
        )
        if user is None:
            user = AdminUser(
                username="test-admin",
                password_hash=bcrypt.hashpw(
                    b"test-password", bcrypt.gensalt()
                ).decode(),
            )
            session.add(user)
            session.flush()
        existing = (
            session.query(AdminSession)
            .filter(AdminSession.session_token == token)
            .first()
        )
        if existing is None:
            session.add(
                AdminSession(
                    admin_user_id=user.id,
                    session_token=token,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                )
            )
        else:
            existing.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        session.commit()
    return {"Authorization": f"Bearer {token}"}
