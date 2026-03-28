from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def _clear_caches():
    from aerisun.core.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _write_secret(tmp_path: Path, filename: str, value: str) -> None:
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(parents=True, exist_ok=True)
    (secret_dir / filename).write_text(value, encoding="utf-8")


def test_production_refuses_missing_waline_token(tmp_path, monkeypatch, _clear_caches):
    monkeypatch.setenv("AERISUN_ENVIRONMENT", "production")
    monkeypatch.setenv("AERISUN_CORS_ORIGINS", '["https://example.com"]')
    monkeypatch.setenv("AERISUN_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(tmp_path / "secrets"))
    monkeypatch.setenv("AERISUN_DB_PATH", str(tmp_path / "a.db"))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(tmp_path / "w.db"))

    from aerisun.core.security import check_insecure_defaults as _check_insecure_defaults
    from aerisun.core.settings import get_settings

    settings = get_settings()
    with pytest.raises(SystemExit, match="waline_jwt_token"):
        _check_insecure_defaults(settings)


def test_production_refuses_default_waline_token(tmp_path, monkeypatch, _clear_caches):
    monkeypatch.setenv("AERISUN_ENVIRONMENT", "production")
    monkeypatch.setenv("AERISUN_CORS_ORIGINS", '["https://example.com"]')
    monkeypatch.setenv("AERISUN_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(tmp_path / "secrets"))
    monkeypatch.setenv("AERISUN_DB_PATH", str(tmp_path / "a.db"))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(tmp_path / "w.db"))
    _write_secret(tmp_path, "waline_jwt_token.txt", "change-me")

    from aerisun.core.security import check_insecure_defaults as _check_insecure_defaults
    from aerisun.core.settings import get_settings

    settings = get_settings()
    with pytest.raises(SystemExit, match="waline_jwt_token"):
        _check_insecure_defaults(settings)


def test_production_warns_localhost_cors(tmp_path, monkeypatch, _clear_caches):
    monkeypatch.setenv("AERISUN_ENVIRONMENT", "production")
    monkeypatch.setenv("AERISUN_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(tmp_path / "secrets"))
    monkeypatch.setenv("AERISUN_DB_PATH", str(tmp_path / "a.db"))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(tmp_path / "w.db"))
    _write_secret(tmp_path, "waline_jwt_token.txt", "strong-random-secret")
    # cors_origins defaults to localhost — should raise in production
    monkeypatch.delenv("AERISUN_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("AERISUN_PRODUCTION_CORS_ORIGINS_OVERRIDE", raising=False)

    from aerisun.core.security import check_insecure_defaults as _check_insecure_defaults
    from aerisun.core.settings import get_settings

    settings = get_settings()
    with pytest.raises(SystemExit, match="CORS"):
        _check_insecure_defaults(settings)


def test_development_warns_but_does_not_crash(tmp_path, monkeypatch, _clear_caches):
    monkeypatch.setenv("AERISUN_ENVIRONMENT", "development")
    monkeypatch.setenv("AERISUN_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(tmp_path / "secrets"))
    monkeypatch.setenv("AERISUN_DB_PATH", str(tmp_path / "a.db"))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(tmp_path / "w.db"))
    _write_secret(tmp_path, "waline_jwt_token.txt", "change-me")

    from aerisun.core.security import check_insecure_defaults as _check_insecure_defaults
    from aerisun.core.settings import get_settings

    settings = get_settings()
    # Should not raise, only warn
    _check_insecure_defaults(settings)


def test_custom_values_pass_silently(tmp_path, monkeypatch, _clear_caches):
    monkeypatch.setenv("AERISUN_ENVIRONMENT", "production")
    monkeypatch.setenv("AERISUN_CORS_ORIGINS", '["https://example.com"]')
    monkeypatch.setenv("AERISUN_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(tmp_path / "secrets"))
    monkeypatch.setenv("AERISUN_DB_PATH", str(tmp_path / "a.db"))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(tmp_path / "w.db"))
    _write_secret(tmp_path, "waline_jwt_token.txt", "strong-random-secret")

    from aerisun.core.security import check_insecure_defaults as _check_insecure_defaults
    from aerisun.core.settings import get_settings

    settings = get_settings()
    _check_insecure_defaults(settings)  # Should not raise
