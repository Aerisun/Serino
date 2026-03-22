from __future__ import annotations

import pytest


@pytest.fixture()
def _clear_caches():
    from aerisun.core.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_production_refuses_default_waline_token(tmp_path, monkeypatch, _clear_caches):
    monkeypatch.setenv("AERISUN_ENVIRONMENT", "production")
    monkeypatch.setenv("WALINE_JWT_TOKEN", "change-me")
    monkeypatch.setenv("AERISUN_CORS_ORIGINS", '["https://example.com"]')
    monkeypatch.setenv("AERISUN_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_DB_PATH", str(tmp_path / "a.db"))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(tmp_path / "w.db"))

    from aerisun.core.settings import get_settings
    from aerisun.main import _check_insecure_defaults

    settings = get_settings()
    with pytest.raises(SystemExit, match="WALINE_JWT_TOKEN"):
        _check_insecure_defaults(settings)


def test_production_warns_localhost_cors(tmp_path, monkeypatch, _clear_caches):
    monkeypatch.setenv("AERISUN_ENVIRONMENT", "production")
    monkeypatch.setenv("WALINE_JWT_TOKEN", "strong-random-secret")
    monkeypatch.setenv("AERISUN_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_DB_PATH", str(tmp_path / "a.db"))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(tmp_path / "w.db"))
    # cors_origins defaults to localhost — should raise in production
    monkeypatch.delenv("AERISUN_CORS_ORIGINS", raising=False)

    from aerisun.core.settings import get_settings
    from aerisun.main import _check_insecure_defaults

    settings = get_settings()
    with pytest.raises(SystemExit, match="CORS"):
        _check_insecure_defaults(settings)


def test_development_warns_but_does_not_crash(tmp_path, monkeypatch, _clear_caches):
    monkeypatch.setenv("AERISUN_ENVIRONMENT", "development")
    monkeypatch.setenv("WALINE_JWT_TOKEN", "change-me")
    monkeypatch.setenv("AERISUN_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_DB_PATH", str(tmp_path / "a.db"))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(tmp_path / "w.db"))

    from aerisun.core.settings import get_settings
    from aerisun.main import _check_insecure_defaults

    settings = get_settings()
    # Should not raise, only warn
    _check_insecure_defaults(settings)


def test_custom_values_pass_silently(tmp_path, monkeypatch, _clear_caches):
    monkeypatch.setenv("AERISUN_ENVIRONMENT", "production")
    monkeypatch.setenv("WALINE_JWT_TOKEN", "strong-random-secret")
    monkeypatch.setenv("AERISUN_CORS_ORIGINS", '["https://example.com"]')
    monkeypatch.setenv("AERISUN_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_DB_PATH", str(tmp_path / "a.db"))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(tmp_path / "w.db"))

    from aerisun.core.settings import get_settings
    from aerisun.main import _check_insecure_defaults

    settings = get_settings()
    _check_insecure_defaults(settings)  # Should not raise
