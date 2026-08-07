from __future__ import annotations

import importlib
from datetime import timedelta

import pytest
from sqlalchemy import text

from aerisun.core.data_migrations.registry import DataMigrationSpec
from aerisun.core.data_migrations.runner import (
    apply_pending_data_migrations,
    cleanup_applied_data_migrations,
    collect_migration_status,
    schedule_pending_background_data_migrations,
)
from aerisun.core.data_migrations.state import get_migration_entry, mark_data_migration_running
from aerisun.core.db import get_session_factory, run_database_migrations
from aerisun.core.production_baseline import PRODUCTION_BASELINE_SCHEMA_REVISION, apply_production_baseline
from aerisun.core.time import shanghai_now
from aerisun.domain.content.models import PostEntry
from aerisun.domain.ops.models import AuditLog, ConfigRevision, VisitRecord
from aerisun.domain.site_config.models import PageCopy
from aerisun.domain.waline.service import set_counter_value


def test_content_view_count_backfill_preserves_the_highest_existing_total(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        run_database_migrations()
        apply_production_baseline(force=True)

        path = "/posts/historical-view-count"
        session_factory = get_session_factory()
        with session_factory() as session:
            post = PostEntry(
                slug="historical-view-count",
                title="Historical view count",
                body="Historical body",
                visibility="public",
                view_count=5,
            )
            session.add(post)
            session.add_all(
                [
                    VisitRecord(
                        visited_at=shanghai_now(),
                        path=path,
                        ip_address=f"203.0.113.{index}",
                        status_code=200,
                        is_bot=False,
                    )
                    for index in range(1, 13)
                ]
            )
            session.commit()
            post.updated_at = shanghai_now() - timedelta(days=1)
            session.commit()
            edited_at = post.updated_at

        set_counter_value(url=path, pageview_count=10)
        module = importlib.import_module(
            "aerisun.core.data_migrations.versions.0014_persist_content_view_counts_backfill"
        )

        with session_factory() as session:
            module.apply(session)
            session.commit()
            post = session.query(PostEntry).filter(PostEntry.slug == "historical-view-count").one()

        assert post.view_count == 12
        assert post.updated_at.replace(tzinfo=None) == edited_at.replace(tzinfo=None)
    finally:
        teardown_runtime_state()


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

        assert payload["current_revision"] == payload["head_revisions"][0]
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


def test_apply_pending_data_migrations_reports_progress_callback_in_order(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        run_database_migrations()
        apply_production_baseline(force=True)

        applied_order: list[str] = []

        first_spec = DataMigrationSpec(
            migration_key="0001_fill_defaults",
            schema_revision=PRODUCTION_BASELINE_SCHEMA_REVISION,
            summary="修复默认值",
            mode="blocking",
            apply=lambda session: None,
            resource_keys=(),
            checksum="fill-defaults",
            module_name="tests.fill_defaults",
        )
        second_spec = DataMigrationSpec(
            migration_key="0001_sync_assets",
            schema_revision=PRODUCTION_BASELINE_SCHEMA_REVISION,
            summary="同步资源引用",
            mode="blocking",
            apply=lambda session: None,
            resource_keys=(),
            checksum="sync-assets",
            module_name="tests.sync_assets",
        )
        monkeypatch.setattr(
            "aerisun.core.data_migrations.runner.get_registered_data_migrations",
            lambda: (first_spec, second_spec),
        )

        applied = apply_pending_data_migrations(
            mode="blocking",
            on_applied=lambda spec: applied_order.append(spec.migration_key),
        )

        assert applied == ["0001_fill_defaults", "0001_sync_assets"]
        assert applied_order == applied
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


def test_blocking_data_migration_finalizer_runs_after_durable_prepare_and_can_resume(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        run_database_migrations()
        apply_production_baseline(force=True)

        events: list[str] = []
        fail_finalize = True

        def prepare(session) -> None:
            page = session.query(PageCopy).filter(PageCopy.page_key == "notFound").one()
            extras = dict(page.extras or {})
            extras["migrationPhase"] = "prepared"
            page.extras = extras
            events.append("prepare")

        def finalize(session) -> None:
            nonlocal fail_finalize
            page = session.query(PageCopy).filter(PageCopy.page_key == "notFound").one()
            journal = get_migration_entry(session, "0001_two_phase_cleanup")
            assert page.extras["migrationPhase"] == "prepared"
            assert journal is not None
            assert journal.status == "running"
            events.append("finalize")
            if fail_finalize:
                fail_finalize = False
                raise RuntimeError("cleanup failed")

        spec = DataMigrationSpec(
            migration_key="0001_two_phase_cleanup",
            schema_revision=PRODUCTION_BASELINE_SCHEMA_REVISION,
            summary="两阶段资源清理",
            mode="blocking",
            apply=prepare,
            finalize=finalize,
            resource_keys=(),
            checksum="two-phase-cleanup",
            module_name="tests.two_phase_cleanup",
        )
        monkeypatch.setattr("aerisun.core.data_migrations.runner.get_registered_data_migrations", lambda: (spec,))

        with pytest.raises(RuntimeError, match="cleanup failed"):
            apply_pending_data_migrations(mode="blocking")

        session_factory = get_session_factory()
        with session_factory() as session:
            journal = get_migration_entry(session, "0001_two_phase_cleanup")
            page = session.query(PageCopy).filter(PageCopy.page_key == "notFound").one()
        assert journal is not None
        assert journal.status == "failed"
        assert page.extras["migrationPhase"] == "prepared"

        assert apply_pending_data_migrations(mode="blocking") == ["0001_two_phase_cleanup"]
        assert events == ["prepare", "finalize", "prepare", "finalize"]
        with session_factory() as session:
            journal = get_migration_entry(session, "0001_two_phase_cleanup")
        assert journal is not None
        assert journal.status == "applied"
    finally:
        teardown_runtime_state()


def test_running_two_phase_migration_resumes_at_finalizer_without_repeating_prepare(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        run_database_migrations()
        apply_production_baseline(force=True)
        events: list[str] = []
        spec = DataMigrationSpec(
            migration_key="0001_resume_finalizer",
            schema_revision=PRODUCTION_BASELINE_SCHEMA_REVISION,
            summary="恢复中断后的清理",
            mode="blocking",
            apply=lambda session: events.append("prepare"),
            finalize=lambda session: events.append("finalize"),
            checksum="resume-finalizer",
            module_name="tests.resume_finalizer",
        )
        monkeypatch.setattr("aerisun.core.data_migrations.runner.get_registered_data_migrations", lambda: (spec,))

        with get_session_factory()() as session:
            mark_data_migration_running(
                session,
                migration_key=spec.migration_key,
                schema_revision=spec.schema_revision,
                mode=spec.mode,
                checksum=spec.checksum,
            )
            session.commit()

        assert apply_pending_data_migrations(mode="blocking") == [spec.migration_key]
        assert events == ["finalize"]
        with get_session_factory()() as session:
            journal = get_migration_entry(session, spec.migration_key)
        assert journal is not None
        assert journal.status == "applied"
    finally:
        teardown_runtime_state()


def test_post_commit_cleanup_failure_keeps_applied_journal_and_retries_cleanup_only(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        run_database_migrations()
        apply_production_baseline(force=True)
        events: list[str] = []
        fail_cleanup = True

        def cleanup(session) -> None:
            nonlocal fail_cleanup
            journal = get_migration_entry(session, "0001_post_commit_cleanup")
            assert journal is not None
            assert journal.status == "applied"
            events.append("cleanup")
            if fail_cleanup:
                fail_cleanup = False
                raise RuntimeError("post-commit cleanup failed")

        spec = DataMigrationSpec(
            migration_key="0001_post_commit_cleanup",
            schema_revision=PRODUCTION_BASELINE_SCHEMA_REVISION,
            summary="提交后清理",
            mode="blocking",
            apply=lambda _session: events.append("apply"),
            finalize=lambda _session: events.append("finalize"),
            cleanup=cleanup,
            resource_keys=(),
            checksum="post-commit-cleanup",
            module_name="tests.post_commit_cleanup",
        )
        monkeypatch.setattr("aerisun.core.data_migrations.runner.get_registered_data_migrations", lambda: (spec,))

        with pytest.raises(RuntimeError, match="post-commit cleanup failed"):
            apply_pending_data_migrations(mode="blocking")

        with get_session_factory()() as session:
            journal = get_migration_entry(session, spec.migration_key)
        assert journal is not None
        assert journal.status == "applied"

        assert apply_pending_data_migrations(mode="blocking") == []
        assert events == ["apply", "finalize", "cleanup", "cleanup"]
    finally:
        teardown_runtime_state()


def test_deferred_cleanup_runs_only_when_explicitly_requested(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        run_database_migrations()
        apply_production_baseline(force=True)
        events: list[str] = []
        spec = DataMigrationSpec(
            migration_key="0001_deferred_cleanup",
            schema_revision=PRODUCTION_BASELINE_SCHEMA_REVISION,
            summary="延后清理",
            mode="blocking",
            apply=lambda _session: events.append("apply"),
            finalize=lambda _session: events.append("finalize"),
            cleanup=lambda _session: events.append("cleanup"),
            resource_keys=(),
            checksum="deferred-cleanup",
            module_name="tests.deferred_cleanup",
        )
        monkeypatch.setattr("aerisun.core.data_migrations.runner.get_registered_data_migrations", lambda: (spec,))

        assert apply_pending_data_migrations(mode="blocking", defer_cleanup=True) == [spec.migration_key]
        assert events == ["apply", "finalize"]
        assert cleanup_applied_data_migrations(mode="blocking") == [spec.migration_key]
        assert events == ["apply", "finalize", "cleanup"]
    finally:
        teardown_runtime_state()
