from __future__ import annotations

import httpx
import pytest

from tests.support.asgi_client import SyncASGITransport
from tests.support.runtime import reset_runtime_state, teardown_runtime_state


@pytest.fixture()
def production_runtime(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from aerisun.core.db import run_database_migrations

    store_dir = tmp_path / "store"
    monkeypatch.setenv("AERISUN_ENVIRONMENT", "production")
    monkeypatch.setenv("AERISUN_STORE_DIR", str(store_dir))
    monkeypatch.setenv("AERISUN_DATA_DIR", str(store_dir))
    monkeypatch.setenv("AERISUN_MEDIA_DIR", str(store_dir / "media"))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(store_dir / "secrets"))
    monkeypatch.setenv("AERISUN_DB_PATH", str(store_dir / "aerisun.db"))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(store_dir / "waline.db"))
    monkeypatch.setenv("AERISUN_CORS_ORIGINS", '["https://example.com"]')
    monkeypatch.setenv("AERISUN_SITE_URL", "https://example.com")
    monkeypatch.setenv("AERISUN_WALINE_SERVER_URL", "https://example.com/waline")
    monkeypatch.setenv("WALINE_JWT_TOKEN", "bootstrap-admin-token")
    monkeypatch.setenv("AERISUN_BOOTSTRAP_ADMIN_USERNAME", "installer-admin")
    monkeypatch.setenv("AERISUN_BOOTSTRAP_ADMIN_PASSWORD", "installer-admin-pass")
    monkeypatch.setenv("AERISUN_FEED_CRAWL_ENABLED", "false")
    monkeypatch.setenv("AERISUN_IP_GEO_ENABLED", "false")

    reset_runtime_state()
    run_database_migrations()
    yield store_dir
    teardown_runtime_state()


def test_production_first_boot_creates_installer_admin_and_allows_login(production_runtime) -> None:
    from aerisun.core.app_factory import create_app
    from aerisun.core.bootstrap_admin import ensure_first_boot_default_admin

    created = ensure_first_boot_default_admin(is_first_boot=True)
    assert created is True

    client = httpx.Client(
        transport=SyncASGITransport(create_app()),
        base_url="http://testserver",
        follow_redirects=True,
    )
    try:
        response = client.post(
            "/api/v1/admin/auth/login",
            json={"username": "installer-admin", "password": "installer-admin-pass"},
        )
    finally:
        client.close()

    assert response.status_code == 200
    assert response.json()["token"]


def test_production_non_first_boot_does_not_backfill_default_admin(production_runtime) -> None:
    from aerisun.core.bootstrap_admin import ensure_first_boot_default_admin
    from aerisun.core.db import get_session_factory
    from aerisun.domain.iam.models import AdminUser

    created = ensure_first_boot_default_admin(is_first_boot=False)
    assert created is False

    with get_session_factory()() as session:
        assert session.query(AdminUser).count() == 0


def test_production_non_first_boot_does_not_reset_existing_admin_password(production_runtime) -> None:
    from aerisun.core.bootstrap_admin import ensure_first_boot_default_admin
    from aerisun.core.db import get_session_factory
    from aerisun.domain.exceptions import AuthenticationFailed
    from aerisun.domain.iam.bootstrap import add_admin_user
    from aerisun.domain.iam.service import authenticate_admin

    with get_session_factory()() as session:
        add_admin_user(session, username="admin", password="already-customized")
        session.commit()

    created = ensure_first_boot_default_admin(is_first_boot=False)
    assert created is False

    with get_session_factory()() as session:
        user = authenticate_admin(session, "admin", "already-customized")
        assert user.username == "admin"
        with pytest.raises(AuthenticationFailed):
            authenticate_admin(session, "admin", "admin123")


def test_production_first_boot_requires_bootstrap_admin_credentials(production_runtime, monkeypatch) -> None:
    from aerisun.core.bootstrap_admin import ensure_first_boot_default_admin

    monkeypatch.delenv("AERISUN_BOOTSTRAP_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("AERISUN_BOOTSTRAP_ADMIN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="bootstrap admin credentials"):
        ensure_first_boot_default_admin(is_first_boot=True)
