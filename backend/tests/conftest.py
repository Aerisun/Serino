from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from tests.support.asgi_client import SyncASGITransport
from tests.support.runtime import (
    clone_seeded_runtime_data,
    configure_runtime_environment,
    reset_runtime_state,
    seed_runtime_data,
    teardown_runtime_state,
)


@pytest.fixture(scope="session")
def seeded_runtime_store(tmp_path_factory: pytest.TempPathFactory) -> Path:
    template_root = tmp_path_factory.mktemp("seeded-runtime")
    patch = pytest.MonkeyPatch()
    runtime_paths = configure_runtime_environment(template_root, patch)
    reset_runtime_state()
    try:
        seed_runtime_data()
    finally:
        try:
            teardown_runtime_state()
        finally:
            patch.undo()
    return runtime_paths["store_dir"]


@pytest.fixture(scope="session")
def app(seeded_runtime_store: Path):
    patch = pytest.MonkeyPatch()
    configure_runtime_environment(seeded_runtime_store.parent, patch)
    reset_runtime_state()
    try:
        from aerisun.core.app_factory import create_app

        return create_app()
    finally:
        try:
            teardown_runtime_state()
        finally:
            patch.undo()


@pytest.fixture(scope="session")
def admin_password_hash() -> str:
    import bcrypt

    return bcrypt.hashpw(b"test-password", bcrypt.gensalt()).decode()


@pytest.fixture(scope="session")
def route_admin_password_hash() -> str:
    import bcrypt

    return bcrypt.hashpw(b"route-password", bcrypt.gensalt()).decode()


@pytest.fixture()
def runtime_environment(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    seeded_runtime_store: Path,
) -> Iterator[None]:
    runtime_paths = configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    clone_seeded_runtime_data(seeded_runtime_store, runtime_paths["store_dir"])
    try:
        yield
    finally:
        teardown_runtime_state()


@pytest.fixture()
def client(runtime_environment, app) -> Iterator[httpx.Client]:
    del runtime_environment

    test_client = httpx.Client(
        transport=SyncASGITransport(app),
        base_url="http://testserver",
        follow_redirects=True,
    )
    try:
        yield test_client
    finally:
        test_client.close()


@pytest.fixture()
def admin_headers(client, admin_password_hash: str) -> dict[str, str]:
    """Create an admin user and session, return authentication headers."""
    from datetime import timedelta

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
                password_hash=admin_password_hash,
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
def seeded_session(runtime_environment):
    del runtime_environment

    from aerisun.core.db import get_session_factory

    factory = get_session_factory()
    with factory() as session:
        yield session


@pytest.fixture()
def admin_user(seeded_session, route_admin_password_hash: str):
    from aerisun.domain.iam.models import AdminUser

    user = seeded_session.query(AdminUser).filter(AdminUser.username == "route-admin").first()
    if user is None:
        user = AdminUser(
            username="route-admin",
            password_hash=route_admin_password_hash,
        )
        seeded_session.add(user)
        seeded_session.commit()
        seeded_session.refresh(user)
    return user
