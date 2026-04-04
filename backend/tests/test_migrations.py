from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from aerisun.core.db import dispose_engine, run_database_migrations
from aerisun.core.settings import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]


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


def _get_tables(path: str) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {str(row[0]) for row in rows}
    finally:
        connection.close()


def _configure_test_database(monkeypatch, tmp_path, db_path) -> None:
    dispose_engine()
    monkeypatch.setenv("AERISUN_DB_PATH", str(db_path))
    monkeypatch.setenv("AERISUN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_STORE_DIR", str(tmp_path))
    monkeypatch.setenv("AERISUN_MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("AERISUN_SECRETS_DIR", str(tmp_path / "secrets"))
    get_settings.cache_clear()


def _upgrade_to_revision(revision: str) -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(config, revision)


def _assert_head_schema(db_path, *, expect_data_updates: bool) -> None:
    tables = _get_tables(str(db_path))
    site_profile_columns = _get_columns(str(db_path), "site_profile")
    page_copy_columns = _get_columns(str(db_path), "page_copy")
    posts_columns = _get_columns(str(db_path), "posts")
    diary_columns = _get_columns(str(db_path), "diary_entries")
    thoughts_columns = _get_columns(str(db_path), "thoughts")
    excerpts_columns = _get_columns(str(db_path), "excerpts")
    nav_item_columns = _get_columns(str(db_path), "nav_items")
    community_config_columns = _get_columns(str(db_path), "community_config")
    assets_columns = _get_columns(str(db_path), "assets")
    traffic_snapshot_columns = _get_columns(str(db_path), "traffic_daily_snapshots")
    agent_run_columns = _get_columns(str(db_path), "agent_runs")
    agent_run_step_columns = _get_columns(str(db_path), "agent_run_steps")
    agent_run_approval_columns = _get_columns(str(db_path), "agent_run_approvals")
    webhook_subscription_columns = _get_columns(str(db_path), "webhook_subscriptions")
    webhook_delivery_columns = _get_columns(str(db_path), "webhook_deliveries")
    webhook_dead_letter_columns = _get_columns(str(db_path), "webhook_dead_letters")
    workflow_gate_state_columns = _get_columns(str(db_path), "workflow_gate_states")
    workflow_gate_buffer_columns = _get_columns(str(db_path), "workflow_gate_buffer_items")
    workflow_build_task_columns = _get_columns(str(db_path), "workflow_build_tasks")
    workflow_build_task_step_columns = _get_columns(str(db_path), "workflow_build_task_steps")
    sync_run_columns = _get_columns(str(db_path), "sync_runs")
    backup_target_config_columns = _get_columns(str(db_path), "backup_target_configs")
    backup_queue_item_columns = _get_columns(str(db_path), "backup_queue_items")
    backup_commit_columns = _get_columns(str(db_path), "backup_commits")
    backup_recovery_key_columns = _get_columns(str(db_path), "backup_recovery_keys")
    api_key_columns = _get_columns(str(db_path), "api_keys")
    asset_remote_delete_queue_columns = _get_columns(str(db_path), "asset_remote_delete_queue_items")
    asset_remote_upload_queue_columns = _get_columns(str(db_path), "asset_remote_upload_queue_items")

    assert "config_revisions" in tables
    assert "page_display_options" not in tables
    assert "hero_video_url" in site_profile_columns
    assert "site_icon_url" in site_profile_columns
    assert "filing_info" in site_profile_columns
    assert {"label", "nav_label", "description", "download_label"} & page_copy_columns == set()
    assert {"footer_text", "author", "meta_description", "copyright"} & site_profile_columns == set()
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
        "anonymous_enabled",
        "moderation_mode",
        "default_sorting",
        "page_size",
        "avatar_helper_copy",
    } <= community_config_columns
    assert {
        "login_mode",
        "oauth_url",
        "oauth_providers",
        "avatar_presets",
        "guest_avatar_mode",
        "draft_enabled",
        "avatar_strategy",
    } & community_config_columns == set()
    assert {"resource_key", "visibility", "category", "note", "scope"} <= assets_columns
    assert {
        "snapshot_date",
        "url",
        "cumulative_views",
        "daily_views",
        "cumulative_reactions",
        "created_at",
        "updated_at",
    } <= traffic_snapshot_columns

    assert {"workflow_key", "status", "thread_id", "created_at"} <= agent_run_columns
    assert {"run_id", "sequence_no", "node_key", "narrative"} <= agent_run_step_columns
    assert {"run_id", "interrupt_id", "approval_type", "status"} <= agent_run_approval_columns
    assert {"name", "status", "target_url", "event_types"} <= webhook_subscription_columns
    assert {"subscription_id", "event_type", "event_id", "status", "attempt_count"} <= webhook_delivery_columns
    assert {"delivery_id", "reason", "event_type", "dead_lettered_at"} <= webhook_dead_letter_columns
    assert {"workflow_key", "node_id", "status", "in_flight_run_id"} <= workflow_gate_state_columns
    assert {"workflow_key", "node_id", "run_id", "status"} <= workflow_gate_buffer_columns
    assert {"workflow_key", "task_type", "status", "summary"} <= workflow_build_task_columns
    assert {"task_id", "name", "status", "detail"} <= workflow_build_task_step_columns
    assert {"key_suffix", "mcp_config", "enabled"} <= api_key_columns
    assert {
        "job_name",
        "status",
        "transport",
        "trigger_kind",
        "queue_item_id",
        "commit_id",
        "stats_json",
    } <= sync_run_columns
    assert {
        "enabled",
        "paused",
        "interval_minutes",
        "transport_mode",
        "site_slug",
        "credential_ref",
        "encrypt_runtime_data",
    } <= backup_target_config_columns
    assert "receiver_base_url" not in backup_target_config_columns
    assert "age_public_key_fingerprint" not in backup_target_config_columns
    assert {
        "transport",
        "trigger_kind",
        "status",
        "dataset_versions",
        "verified_chunks",
        "retry_count",
    } <= backup_queue_item_columns
    assert {
        "object_key",
        "status",
        "retry_count",
        "next_retry_at",
        "last_error",
        "started_at",
        "finished_at",
    } <= asset_remote_delete_queue_columns
    assert {
        "asset_id",
        "object_key",
        "status",
        "retry_count",
        "next_retry_at",
        "last_error",
        "started_at",
        "finished_at",
    } <= asset_remote_upload_queue_columns
    assert {
        "transport",
        "trigger_kind",
        "site_slug",
        "remote_commit_id",
        "manifest_digest",
        "datasets",
    } <= backup_commit_columns
    assert {
        "credential_ref",
        "site_slug",
        "status",
        "secrets_fingerprint",
        "encrypted_private_payload",
        "acknowledged_at",
    } <= backup_recovery_key_columns
    assert "backup_snapshots" not in tables
    assert "restore_points" not in tables

    if expect_data_updates:
        community_config_row = _get_row(str(db_path), "community_config")
        asset_row = _get_row(str(db_path), "assets")

        assert community_config_row is not None
        assert community_config_row["anonymous_enabled"] in (1, True)
        assert community_config_row["moderation_mode"] == "all_pending"
        assert community_config_row["default_sorting"] == "latest"
        assert community_config_row["page_size"] == 20
        assert (
            community_config_row["avatar_helper_copy"] == "登录后评论会绑定到当前邮箱或第三方身份，邮箱不会公开显示。"
        )

        assert asset_row is not None
        assert asset_row["resource_key"] == "internal/assets/general/asset1.png"
        assert asset_row["visibility"] == "internal"
        assert asset_row["category"] == "general"
        assert asset_row["scope"] == "user"
        assert asset_row["note"] is None


def test_0001_initial_is_static_historical_schema(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "initial.db"

    _configure_test_database(monkeypatch, tmp_path, db_path)
    _upgrade_to_revision("0001_initial")

    tables = _get_tables(str(db_path))
    site_profile_columns = _get_columns(str(db_path), "site_profile")
    posts_columns = _get_columns(str(db_path), "posts")
    assets_columns = _get_columns(str(db_path), "assets")
    community_config_columns = _get_columns(str(db_path), "community_config")

    assert {
        "site_profile",
        "social_links",
        "poems",
        "page_copy",
        "page_display_options",
        "community_config",
        "resume_basics",
        "resume_skills",
        "resume_experiences",
        "posts",
        "diary_entries",
        "thoughts",
        "excerpts",
        "guestbook_entries",
        "comments",
        "reactions",
        "friends",
        "friend_feed_sources",
        "friend_feed_items",
        "assets",
        "admin_users",
        "admin_sessions",
        "api_keys",
        "audit_logs",
        "moderation_records",
        "backup_snapshots",
        "restore_points",
        "sync_runs",
    } <= tables

    assert {"nav_items", "content_categories", "traffic_daily_snapshots", "visit_records"} & tables == set()
    assert {"site_users", "site_auth_config", "site_admin_identities"} & tables == set()
    assert {"agent_runs", "agent_run_steps", "agent_run_approvals"} & tables == set()
    assert {"webhook_subscriptions", "webhook_deliveries", "webhook_dead_letters"} & tables == set()

    assert site_profile_columns == {
        "id",
        "name",
        "title",
        "bio",
        "role",
        "footer_text",
        "created_at",
        "updated_at",
    }
    assert {"category", "view_count", "is_pinned", "pin_order"} & posts_columns == set()
    assert {"resource_key", "visibility", "category", "note", "scope"} & assets_columns == set()
    assert {
        "anonymous_enabled",
        "moderation_mode",
        "default_sorting",
        "page_size",
        "avatar_helper_copy",
        "image_max_bytes",
    } & community_config_columns == set()


def test_run_database_migrations_upgrades_empty_database(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "fresh.db"

    _configure_test_database(monkeypatch, tmp_path, db_path)
    run_database_migrations()
    _assert_head_schema(db_path, expect_data_updates=False)


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
                filing_info TEXT NOT NULL DEFAULT '',
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
        connection.execute(
            """
            CREATE TABLE api_keys (
                id TEXT PRIMARY KEY,
                key_name TEXT NOT NULL,
                key_prefix TEXT NOT NULL UNIQUE,
                hashed_secret TEXT NOT NULL,
                scopes JSON NOT NULL,
                last_used_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE assets (
                id TEXT PRIMARY KEY,
                file_name TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                mime_type TEXT,
                byte_size INTEGER,
                sha256 TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO assets (
                id, file_name, storage_path,
                mime_type, byte_size, sha256, created_at, updated_at
            ) VALUES (
                'asset-1',
                'image.png',
                '/tmp/image.png',
                NULL,
                NULL,
                NULL,
                '2026-03-21 00:00:00',
                '2026-03-21 00:00:00'
            )
            """
        )
        connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.execute("INSERT INTO alembic_version (version_num) VALUES ('0001_initial')")
        connection.commit()
    finally:
        connection.close()

    _configure_test_database(monkeypatch, tmp_path, db_path)
    run_database_migrations()
    _assert_head_schema(db_path, expect_data_updates=True)
