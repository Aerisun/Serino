from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from aerisun.core.db import dispose_engine, run_database_migrations
from aerisun.core.settings import get_settings

CURRENT_SCHEMA_HEAD = "0003_comment_image_rate_limit"

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _configure_test_database(monkeypatch, tmp_path, db_path: Path) -> None:
    dispose_engine()
    monkeypatch.setenv("AERISUN_DB_PATH", str(db_path))
    monkeypatch.setenv("AERISUN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(tmp_path / "secrets"))
    monkeypatch.setenv("AERISUN_WALINE_DB_PATH", str(tmp_path / "waline.db"))
    get_settings.cache_clear()


def _get_tables(path: Path) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {str(row[0]) for row in rows}
    finally:
        connection.close()


def _get_alembic_revision(path: Path) -> str | None:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
        return None if row is None else str(row[0])
    finally:
        connection.close()


def test_active_alembic_history_is_reset_to_single_production_baseline_head() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)

    active_versions = sorted(path.name for path in (BACKEND_ROOT / "alembic" / "versions").glob("*.py"))

    assert tuple(script.get_heads()) == (CURRENT_SCHEMA_HEAD,)
    assert active_versions == [
        "0001_production_baseline.py",
        "0002_public_title_identity.py",
        "0003_comment_image_rate_limit.py",
    ]
    assert not (BACKEND_ROOT / "alembic" / "legacy_versions").exists()


def test_run_database_migrations_creates_baseline_schema_and_journal(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "baseline.db"

    _configure_test_database(monkeypatch, tmp_path, db_path)
    run_database_migrations()

    tables = _get_tables(db_path)

    assert "site_profile" in tables
    assert "community_config" in tables
    assert "config_revisions" in tables
    assert "_aerisun_data_migrations" in tables
    assert "page_display_options" not in tables
    assert _get_alembic_revision(db_path) == CURRENT_SCHEMA_HEAD
