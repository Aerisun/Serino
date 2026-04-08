from __future__ import annotations

from sqlalchemy import text

from aerisun.core.data_migrations.registry import DataMigrationSpec
from aerisun.core.data_migrations.runner import (
    apply_pending_data_migrations,
    collect_migration_status,
    schedule_pending_background_data_migrations,
)
from aerisun.core.data_migrations.state import get_migration_entry
from aerisun.core.db import get_session_factory, run_database_migrations
from aerisun.core.production_baseline import PRODUCTION_BASELINE_SCHEMA_REVISION, apply_production_baseline
from aerisun.domain.ops.models import AuditLog, ConfigRevision
from aerisun.domain.site_config.models import PageCopy


def test_collect_migration_status_reports_baseline_and_pending_modes(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        run_database_migrations()
        apply_production_baseline(force=True)

        blocking_spec = DataMigrationSpec(
            migration_key="0001_fill_blocking_defaults",
            schema_revision=PRODUCTION_BASELINE_SCHEMA_REVISION,
            summary="阻塞式默认值修复",
            mode="blocking",
            apply=lambda session: None,
            resource_keys=("site.pages",),
            checksum="blocking-checksum",
            module_name="tests.blocking",
        )
        background_spec = DataMigrationSpec(
            migration_key="0001_rehash_background_assets",
            schema_revision=PRODUCTION_BASELINE_SCHEMA_REVISION,
            summary="后台资源整理",
            mode="background",
            apply=lambda session: None,
            resource_keys=(),
            checksum="background-checksum",
            module_name="tests.background",
        )
        monkeypatch.setattr(
            "aerisun.core.data_migrations.runner.get_registered_data_migrations",
            lambda: (blocking_spec, background_spec),
        )

        payload = collect_migration_status()

        assert payload["current_revision"] == PRODUCTION_BASELINE_SCHEMA_REVISION
        assert payload["baseline"]["migration_key"]
        assert payload["blocking"]["pending"] == ["0001_fill_blocking_defaults"]
        assert payload["background"]["pending"] == ["0001_rehash_background_assets"]
    finally:
        teardown_runtime_state()


def test_apply_pending_data_migrations_records_journal_revisions_and_audit(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        run_database_migrations()
        apply_production_baseline(force=True)

        def apply_fix(session) -> None:
            page = session.query(PageCopy).filter(PageCopy.page_key == "notFound").one()
            extras = dict(page.extras or {})
            extras["homeLabel"] = "回到首页"
            page.extras = extras

        spec = DataMigrationSpec(
            migration_key="0001_fix_not_found_copy",
            schema_revision=PRODUCTION_BASELINE_SCHEMA_REVISION,
            summary="修复 404 页面默认文案",
            mode="blocking",
            apply=apply_fix,
            resource_keys=("site.pages",),
            checksum="not-found-copy",
            module_name="tests.fix_not_found_copy",
        )
        monkeypatch.setattr("aerisun.core.data_migrations.runner.get_registered_data_migrations", lambda: (spec,))

        applied = apply_pending_data_migrations(mode="blocking")
        assert applied == ["0001_fix_not_found_copy"]

        session_factory = get_session_factory()
        with session_factory() as session:
            journal = get_migration_entry(session, "0001_fix_not_found_copy")
            page = session.query(PageCopy).filter(PageCopy.page_key == "notFound").one()
            revisions = session.query(ConfigRevision).filter(ConfigRevision.operation == "data_migration").all()
            audits = session.query(AuditLog).filter(AuditLog.action == "DATA MIGRATION APPLY").all()

        assert journal is not None
        assert journal.status == "applied"
        assert page.extras["homeLabel"] == "回到首页"
        assert {item.resource_key for item in revisions} == {"site.pages"}
        assert all(item.summary.startswith("版本化数据迁移：") for item in revisions)
        assert len(audits) == 1
        assert audits[0].payload["migration_key"] == "0001_fix_not_found_copy"
    finally:
        teardown_runtime_state()


def test_schedule_pending_background_data_migrations_marks_scheduled_without_applying(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        run_database_migrations()
        apply_production_baseline(force=True)

        def apply_fix(session) -> None:
            session.execute(text("SELECT 1"))

        spec = DataMigrationSpec(
            migration_key="0001_background_cleanup",
            schema_revision=PRODUCTION_BASELINE_SCHEMA_REVISION,
            summary="后台清理任务",
            mode="background",
            apply=apply_fix,
            resource_keys=(),
            checksum="background-cleanup",
            module_name="tests.background_cleanup",
        )
        monkeypatch.setattr("aerisun.core.data_migrations.runner.get_registered_data_migrations", lambda: (spec,))

        scheduled = schedule_pending_background_data_migrations()

        session_factory = get_session_factory()
        with session_factory() as session:
            journal = get_migration_entry(session, "0001_background_cleanup")

        assert scheduled == ["0001_background_cleanup"]
        assert journal is not None
        assert journal.status == "scheduled"
    finally:
        teardown_runtime_state()


def test_apply_pending_data_migrations_records_failures(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        run_database_migrations()
        apply_production_baseline(force=True)

        def explode(_session) -> None:
            raise RuntimeError("boom")

        spec = DataMigrationSpec(
            migration_key="0001_fail_blocking",
            schema_revision=PRODUCTION_BASELINE_SCHEMA_REVISION,
            summary="失败的阻塞式迁移",
            mode="blocking",
            apply=explode,
            resource_keys=(),
            checksum="fail-blocking",
            module_name="tests.fail_blocking",
        )
        monkeypatch.setattr("aerisun.core.data_migrations.runner.get_registered_data_migrations", lambda: (spec,))

        try:
            apply_pending_data_migrations(mode="blocking")
        except RuntimeError as exc:
            assert str(exc) == "boom"
        else:
            raise AssertionError("expected apply_pending_data_migrations to raise")

        session_factory = get_session_factory()
        with session_factory() as session:
            journal = get_migration_entry(session, "0001_fail_blocking")

        assert journal is not None
        assert journal.status == "failed"
        assert "boom" in (journal.last_error or "")
    finally:
        teardown_runtime_state()
