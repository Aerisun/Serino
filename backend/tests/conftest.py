from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest

from tests.support.asgi_client import SyncASGITransport
from tests.support.runtime import (
    configure_runtime_environment,
    reset_runtime_state,
    seed_runtime_data,
    teardown_runtime_state,
)


@pytest.fixture()
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[httpx.Client]:
    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    seed_runtime_data()

    from aerisun.core.app_factory import create_app

    test_client = httpx.Client(
        transport=SyncASGITransport(create_app()),
        base_url="http://testserver",
        follow_redirects=True,
    )
    try:
        yield test_client
    finally:
        test_client.close()

    teardown_runtime_state()


@pytest.fixture()
def admin_headers(client) -> dict[str, str]:
    """Create an admin user and session, return authentication headers."""
    from datetime import timedelta

    import bcrypt

    from aerisun.core.db import get_session_factory
    from aerisun.core.time import shanghai_now
    from aerisun.domain.iam.models import AdminSession, AdminUser

    factory = get_session_factory()
    token = "test-admin-session-token"
    with factory() as session:
        user = session.query(AdminUser).filter(AdminUser.username == "test-admin").first()
        if user is None:
            user = AdminUser(
                username="test-admin",
                password_hash=bcrypt.hashpw(b"test-password", bcrypt.gensalt()).decode(),
            )
            session.add(user)
            session.flush()
        existing = session.query(AdminSession).filter(AdminSession.session_token == token).first()
        if existing is None:
            session.add(
                AdminSession(
                    admin_user_id=user.id,
                    session_token=token,
                    expires_at=shanghai_now() + timedelta(hours=24),
                )
            )
        else:
            existing.expires_at = shanghai_now() + timedelta(hours=24)
        session.commit()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def seeded_session(tmp_path, monkeypatch: pytest.MonkeyPatch):
    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    seed_runtime_data()

    from aerisun.core.db import get_session_factory

    factory = get_session_factory()
    with factory() as session:
        yield session

    teardown_runtime_state()


@pytest.fixture()
def admin_user(seeded_session):
    import bcrypt

    from aerisun.domain.iam.models import AdminUser

    user = seeded_session.query(AdminUser).filter(AdminUser.username == "route-admin").first()
    if user is None:
        user = AdminUser(
            username="route-admin",
            password_hash=bcrypt.hashpw(b"route-password", bcrypt.gensalt()).decode(),
        )
        seeded_session.add(user)
        seeded_session.commit()
        seeded_session.refresh(user)
    return user
