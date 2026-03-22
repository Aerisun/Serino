from __future__ import annotations

import sqlite3

from aerisun.db import run_database_migrations
from aerisun.settings import get_settings


def _get_columns(path: str, table: str) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(row[1]) for row in rows}
    finally:
        connection.close()


def test_run_database_migrations_upgrades_legacy_schema(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "legacy.db"

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE site_profile (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                title TEXT NOT NULL,
                bio TEXT NOT NULL,
                role TEXT NOT NULL,
                footer_text TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                og_image TEXT NOT NULL DEFAULT '/images/hero_bg.jpeg',
                meta_description TEXT NOT NULL DEFAULT '',
                copyright TEXT NOT NULL DEFAULT 'All rights reserved',
                hero_actions TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE page_copy (
                id TEXT PRIMARY KEY,
                page_key TEXT NOT NULL UNIQUE,
                label TEXT,
                title TEXT NOT NULL,
                subtitle TEXT NOT NULL,
                description TEXT,
                search_placeholder TEXT,
                empty_message TEXT,
                max_width TEXT,
                page_size INTEGER,
                download_label TEXT,
                extras JSON NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE posts (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                summary TEXT,
                body TEXT NOT NULL,
                tags JSON NOT NULL,
                status TEXT NOT NULL,
                visibility TEXT NOT NULL,
                published_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE diary_entries (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                summary TEXT,
                body TEXT NOT NULL,
                tags JSON NOT NULL,
                status TEXT NOT NULL,
                visibility TEXT NOT NULL,
                published_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE thoughts (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                summary TEXT,
                body TEXT NOT NULL,
                tags JSON NOT NULL,
                status TEXT NOT NULL,
                visibility TEXT NOT NULL,
                published_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE excerpts (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                summary TEXT,
                body TEXT NOT NULL,
                tags JSON NOT NULL,
                status TEXT NOT NULL,
                visibility TEXT NOT NULL,
                published_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.execute("INSERT INTO alembic_version (version_num) VALUES ('0002_add_site_meta_fields')")
        connection.commit()
    finally:
        connection.close()

    monkeypatch.setenv("AERISUN_DB_PATH", str(db_path))
    monkeypatch.setenv("AERISUN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(tmp_path / "secrets"))

    get_settings.cache_clear()

    run_database_migrations()

    site_profile_columns = _get_columns(str(db_path), "site_profile")
    posts_columns = _get_columns(str(db_path), "posts")
    diary_columns = _get_columns(str(db_path), "diary_entries")
    thoughts_columns = _get_columns(str(db_path), "thoughts")
    excerpts_columns = _get_columns(str(db_path), "excerpts")
    nav_item_columns = _get_columns(str(db_path), "nav_items")

    assert "hero_video_url" in site_profile_columns
    assert {"category", "view_count"} <= posts_columns
    assert {"mood", "weather", "poem", "view_count"} <= diary_columns
    assert {"mood", "view_count"} <= thoughts_columns
    assert {"author_name", "source", "view_count"} <= excerpts_columns
    assert {"label", "href", "trigger", "parent_id", "site_profile_id"} <= nav_item_columns
