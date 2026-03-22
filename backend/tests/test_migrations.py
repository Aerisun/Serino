from __future__ import annotations

import json
import sqlite3

from aerisun.core.db import run_database_migrations
from aerisun.core.settings import get_settings


def _get_columns(path: str, table: str) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(row[1]) for row in rows}
    finally:
        connection.close()


def _get_row(path: str, table: str) -> sqlite3.Row | None:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(f"SELECT * FROM {table} LIMIT 1").fetchone()
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
        connection.execute(
            """
            CREATE TABLE community_config (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL DEFAULT 'waline',
                server_url TEXT NOT NULL DEFAULT '',
                surfaces JSON NOT NULL,
                meta JSON NOT NULL,
                required_meta JSON NOT NULL,
                emoji_presets JSON NOT NULL,
                enable_enjoy_search BOOLEAN NOT NULL DEFAULT 1,
                image_uploader BOOLEAN NOT NULL DEFAULT 0,
                login_mode TEXT NOT NULL DEFAULT 'disable',
                oauth_url TEXT,
                avatar_strategy TEXT NOT NULL DEFAULT 'identicon',
                avatar_helper_copy TEXT NOT NULL DEFAULT '',
                migration_state TEXT NOT NULL DEFAULT 'not_started',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO community_config (
                id, provider, server_url, surfaces, meta, required_meta, emoji_presets,
                enable_enjoy_search, image_uploader, login_mode, oauth_url, avatar_strategy,
                avatar_helper_copy, migration_state, created_at, updated_at
            ) VALUES (
                'community-config',
                'waline',
                '',
                ?,
                ?,
                ?,
                ?,
                1,
                0,
                'disable',
                NULL,
                'identicon',
                '',
                'not_started',
                '2026-03-21 00:00:00',
                '2026-03-21 00:00:00'
            )
            """,
            (
                json.dumps(
                    [
                        {
                            "key": "posts",
                            "label": "文章评论",
                            "path": "/posts/{slug}",
                            "enabled": True,
                        },
                        {
                            "key": "guestbook",
                            "label": "留言板",
                            "path": "/guestbook",
                            "enabled": True,
                        },
                    ],
                    ensure_ascii=False,
                ),
                json.dumps(["nick", "mail"], ensure_ascii=False),
                json.dumps(["nick"], ensure_ascii=False),
                json.dumps(["twemoji", "qq", "bilibili"], ensure_ascii=False),
            ),
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
    community_config_columns = _get_columns(str(db_path), "community_config")

    assert "hero_video_url" in site_profile_columns
    assert {"category", "view_count"} <= posts_columns
    assert {"mood", "weather", "poem", "view_count"} <= diary_columns
    assert {"mood", "view_count"} <= thoughts_columns
    assert {"author_name", "source", "view_count"} <= excerpts_columns
    assert {
        "label",
        "href",
        "trigger",
        "parent_id",
        "site_profile_id",
    } <= nav_item_columns
    assert {
        "oauth_providers",
        "anonymous_enabled",
        "moderation_mode",
        "default_sorting",
        "page_size",
        "avatar_presets",
        "guest_avatar_mode",
        "draft_enabled",
    } <= community_config_columns

    row = _get_row(str(db_path), "community_config")
    assert row is not None
    assert json.loads(row["oauth_providers"]) == ["github", "google"]
    assert row["anonymous_enabled"] in (1, True)
    assert row["moderation_mode"] == "all_pending"
    assert row["default_sorting"] == "latest"
    assert row["page_size"] == 20
    assert json.loads(row["avatar_presets"])[0]["key"] == "shiro"
    assert row["guest_avatar_mode"] == "preset"
    assert row["draft_enabled"] in (1, True)
