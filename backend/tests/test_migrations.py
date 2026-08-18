from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from aerisun.core.db import dispose_engine, run_database_migrations
from aerisun.core.settings import get_settings

CURRENT_SCHEMA_HEAD = "0027_remove_thought_categories"

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


def _get_columns(path: Path, table: str) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(row[1]) for row in rows}
    finally:
        connection.close()


def _get_indexes(path: Path, table: str) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(f"PRAGMA index_list({table})").fetchall()
        return {str(row[1]) for row in rows}
    finally:
        connection.close()


def _get_index_column_sort_order(path: Path, index: str) -> dict[str, int]:
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(f"PRAGMA index_xinfo({index})").fetchall()
        return {str(row[2]): int(row[3]) for row in rows if int(row[5]) == 1}
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
        "0004_drop_admin_email_password_hash.py",
        "0005_remove_content_status.py",
        "0006_visit_record_user_agent_fields.py",
        "0007_comment_feedback_config.py",
        "0008_visit_record_order_index.py",
        "0009_backup_bootstrap_claims.py",
        "0010_diary_access_requests.py",
        "0011_content_notification_failed_attempts.py",
        "0012_backup_retention_days.py",
        "0013_asset_public_slug.py",
        "0014_persist_content_view_counts.py",
        "0015_diary_access_latest_request_index.py",
        "0016_post_rss_exclusion.py",
        "0017_post_requires_approval.py",
        "0018_post_access_requests.py",
        "0019_asset_storage_layout.py",
        "0020_agent_run_coordination.py",
        "0021_system_diagnostics.py",
        "0022_webhook_network_policy.py",
        "0023_agent_run_principal.py",
        "0024_agent_message_projection.py",
        "0025_post_manuscript_note_kind.py",
        "0026_manuscript_note_page_config.py",
        "0027_remove_thought_categories.py",
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
    assert "backup_bootstrap_claims" in tables
    assert "diary_access_requests" in tables
    assert "_aerisun_data_migrations" in tables
    assert "asset_local_delete_queue_items" in tables
    assert "failed_attempts" in _get_columns(db_path, "content_notifications")
    assert "ix_diary_access_requests_site_user_created_id" in _get_indexes(
        db_path,
        "diary_access_requests",
    )
    assert _get_index_column_sort_order(db_path, "ix_diary_access_requests_site_user_created_id") == {
        "site_user_id": 0,
        "created_at": 1,
        "id": 1,
    }
    assert "retention_days" in _get_columns(db_path, "backup_target_configs")
    assert "public_slug" in _get_columns(db_path, "assets")
    assert "ix_assets_scope_category_created_at" in _get_indexes(db_path, "assets")
    assert "ix_assets_remote_object_key" in _get_indexes(db_path, "assets")
    assert "exclude_from_rss" in _get_columns(db_path, "posts")
    assert "requires_approval" in _get_columns(db_path, "posts")
    assert "kind" in _get_columns(db_path, "posts")
    assert "post_access_requests" in tables
    assert "exclude_from_rss" not in _get_columns(db_path, "diary_entries")
    assert "page_display_options" not in tables
    assert "admin_email_password_hash" not in _get_columns(db_path, "site_auth_config")
    assert "status" not in _get_columns(db_path, "posts")
    assert "first_archived_at" not in _get_columns(db_path, "posts")
    assert {
        "execution_mode",
        "workflow_snapshot",
        "workflow_fingerprint",
        "idempotency_key",
        "available_at",
        "attempt_count",
        "max_attempts",
        "lease_owner",
        "lease_expires_at",
        "heartbeat_at",
        "cancel_requested_at",
        "retry_of_run_id",
        "requested_by_type",
        "requested_by_id",
        "authorization_scopes",
    } <= _get_columns(db_path, "agent_runs")
    assert {
        "ix_agent_runs_claimable",
        "ix_agent_runs_lease_expires_at",
        "uq_agent_runs_workflow_idempotency",
    } <= _get_indexes(db_path, "agent_runs")
    assert "uq_agent_run_steps_run_sequence" in _get_indexes(db_path, "agent_run_steps")
    assert "system_diagnostic_state" in tables
    assert {
        "run_id",
        "execution_status",
        "overall_status",
        "trigger_kind",
        "healthy_count",
        "warning_count",
        "failed_count",
        "skipped_count",
        "results_json",
        "started_at",
        "completed_at",
        "last_error",
    } <= _get_columns(db_path, "system_diagnostic_state")
    assert "ix_system_diagnostic_state_execution_status" in _get_indexes(
        db_path,
        "system_diagnostic_state",
    )
    assert "allow_private_network" in _get_columns(db_path, "webhook_subscriptions")
    assert _get_alembic_revision(db_path) == CURRENT_SCHEMA_HEAD


def test_remove_thought_categories_migration_clears_legacy_data(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "legacy-thought-categories.db"

    _configure_test_database(monkeypatch, tmp_path, db_path)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(config, "0026_manuscript_note_page_config")

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            INSERT INTO thoughts (
                id, slug, title, summary, body, category, tags, visibility, published_at,
                public_title, first_published_at, is_pinned, pin_order, mood, view_count,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-thought",
                "legacy-thought",
                "旧碎碎念",
                None,
                "旧内容",
                "旧分类",
                "[]",
                "private",
                None,
                None,
                None,
                0,
                0,
                None,
                0,
                "2026-08-18 12:00:00",
                "2026-08-18 12:00:00",
            ),
        )
        connection.executemany(
            """
            INSERT INTO content_categories (id, content_type, name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("legacy-thought-category", "thoughts", "旧分类", "2026-08-18 12:00:00", "2026-08-18 12:00:00"),
                ("post-category", "posts", "文稿分类", "2026-08-18 12:00:00", "2026-08-18 12:00:00"),
            ],
        )
        connection.commit()
    finally:
        connection.close()

    run_database_migrations()

    connection = sqlite3.connect(db_path)
    try:
        category = connection.execute("SELECT category FROM thoughts WHERE id = 'legacy-thought'").fetchone()
        thought_categories = connection.execute(
            "SELECT COUNT(*) FROM content_categories WHERE content_type = 'thoughts'"
        ).fetchone()
        retained_categories = connection.execute(
            "SELECT COUNT(*) FROM content_categories WHERE content_type = 'posts' AND name = '文稿分类'"
        ).fetchone()
    finally:
        connection.close()

    assert category == (None,)
    assert thought_categories == (0,)
    assert retained_categories == (1,)


def test_agent_run_coordination_migration_upgrades_legacy_schema_and_rows(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "legacy-agent-runs.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
            INSERT INTO alembic_version (version_num) VALUES ('0019_asset_storage_layout');
            CREATE TABLE agent_runs (
                id VARCHAR(36) PRIMARY KEY NOT NULL,
                workflow_key VARCHAR(120) NOT NULL,
                status VARCHAR(32) NOT NULL,
                trigger_kind VARCHAR(40) NOT NULL,
                trigger_event VARCHAR(120),
                target_type VARCHAR(80),
                target_id VARCHAR(64),
                thread_id VARCHAR(64) NOT NULL UNIQUE,
                latest_checkpoint_id VARCHAR(120),
                checkpoint_ns VARCHAR(120),
                input_payload JSON NOT NULL,
                context_payload JSON NOT NULL,
                result_payload JSON NOT NULL,
                error_code VARCHAR(80),
                error_message TEXT,
                started_at DATETIME,
                finished_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            CREATE TABLE agent_run_steps (
                id VARCHAR(36) PRIMARY KEY NOT NULL,
                run_id VARCHAR(36) NOT NULL,
                sequence_no INTEGER NOT NULL,
                node_key VARCHAR(120) NOT NULL,
                step_kind VARCHAR(40) NOT NULL,
                status VARCHAR(32) NOT NULL,
                narrative TEXT NOT NULL,
                input_payload JSON NOT NULL,
                output_payload JSON NOT NULL,
                error_payload JSON NOT NULL,
                started_at DATETIME,
                finished_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            INSERT INTO agent_runs (
                id, workflow_key, status, trigger_kind, thread_id,
                input_payload, context_payload, result_payload, created_at, updated_at
            ) VALUES (
                'legacy-run', 'legacy-workflow', 'completed', 'manual', 'legacy-thread',
                '{}', '{}', '{}', '2026-08-01 00:00:00', '2026-08-01 00:00:00'
            );
            INSERT INTO agent_run_steps (
                id, run_id, sequence_no, node_key, step_kind, status, narrative,
                input_payload, output_payload, error_payload, created_at, updated_at
            ) VALUES
                (
                    'legacy-step-a', 'legacy-run', 1, 'first', 'node_completed', 'completed', 'first',
                    '{}', '{}', '{}', '2026-08-01 00:00:01', '2026-08-01 00:00:01'
                ),
                (
                    'legacy-step-b', 'legacy-run', 1, 'second', 'node_completed', 'completed', 'second',
                    '{}', '{}', '{}', '2026-08-01 00:00:02', '2026-08-01 00:00:02'
                );
            """
        )
        connection.commit()
    finally:
        connection.close()

    _configure_test_database(monkeypatch, tmp_path, db_path)
    run_database_migrations()

    assert _get_alembic_revision(db_path) == CURRENT_SCHEMA_HEAD
    assert {
        "execution_mode",
        "workflow_snapshot",
        "workflow_fingerprint",
        "idempotency_key",
        "available_at",
        "attempt_count",
        "max_attempts",
        "lease_owner",
        "lease_expires_at",
        "heartbeat_at",
        "cancel_requested_at",
        "retry_of_run_id",
    } <= _get_columns(db_path, "agent_runs")
    assert {
        "ix_agent_runs_claimable",
        "ix_agent_runs_lease_expires_at",
        "uq_agent_runs_workflow_idempotency",
    } <= _get_indexes(db_path, "agent_runs")
    assert "uq_agent_run_steps_run_sequence" in _get_indexes(db_path, "agent_run_steps")

    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            """
            SELECT execution_mode, workflow_snapshot, attempt_count, max_attempts,
                   requested_by_type, requested_by_id, authorization_scopes
            FROM agent_runs WHERE id = 'legacy-run'
            """
        ).fetchone()
        step_sequences = connection.execute(
            "SELECT sequence_no FROM agent_run_steps WHERE run_id = 'legacy-run' ORDER BY sequence_no"
        ).fetchall()
    finally:
        connection.close()
    assert row == ("live", "{}", 0, 3, "system", None, '["*"]')
    assert step_sequences == [(1,), (2,)]
