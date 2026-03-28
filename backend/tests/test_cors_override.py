from __future__ import annotations

from pathlib import Path


def _write_secret(tmp_path: Path, filename: str, value: str) -> None:
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(parents=True, exist_ok=True)
    (secret_dir / filename).write_text(value, encoding="utf-8")


def test_production_cors_override_prevents_localhost_crash(tmp_path, monkeypatch):
    from aerisun.core.settings import get_settings

    get_settings.cache_clear()

    monkeypatch.setenv("AERISUN_ENVIRONMENT", "production")
    monkeypatch.setenv("AERISUN_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(tmp_path / "secrets"))
    monkeypatch.setenv("AERISUN_DB_PATH", str(tmp_path / "a.db"))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(tmp_path / "w.db"))

    _write_secret(tmp_path, "waline_jwt_token.txt", "strong-random-secret")

    # leave cors_origins default (localhost) but provide emergency override
    monkeypatch.delenv("AERISUN_CORS_ORIGINS", raising=False)
    monkeypatch.setenv("AERISUN_PRODUCTION_CORS_ORIGINS_OVERRIDE", '["https://example.com"]')

    from aerisun.core.security import check_insecure_defaults

    settings = get_settings()
    # Should not raise for CORS now (may still raise for missing runtime public_site_url if session provided)
    check_insecure_defaults(settings)


def test_resolve_allowed_origins_prefers_override(monkeypatch, seeded_session):
    from aerisun.core.db import get_engine, get_session_factory
    from aerisun.core.middleware import _resolve_allowed_origins
    from aerisun.core.settings import get_settings

    monkeypatch.setenv("AERISUN_ENVIRONMENT", "production")
    monkeypatch.setenv("AERISUN_CORS_ORIGINS", '["https://fallback.example.com"]')
    monkeypatch.setenv("AERISUN_PRODUCTION_CORS_ORIGINS_OVERRIDE", '["https://override.example.com"]')

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    settings = get_settings()
    factory = get_session_factory()
    with factory() as session:
        assert _resolve_allowed_origins(settings, session) == ["https://override.example.com"]
