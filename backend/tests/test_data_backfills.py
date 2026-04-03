from __future__ import annotations

from sqlalchemy import text

from aerisun.core.backfills.runner import run_pending_backfills
from aerisun.core.backfills.state import list_applied_data_migrations
from aerisun.core.db import get_session_factory
from aerisun.core.seed import seed_bootstrap_data
from aerisun.core.settings import get_settings
from aerisun.domain.automation.settings import AGENT_MODEL_CONFIG_FLAG_KEY
from aerisun.domain.ops.models import AuditLog, ConfigRevision
from aerisun.domain.site_auth.models import SiteAuthConfig
from aerisun.domain.site_config.models import CommunityConfig, PageCopy, ResumeBasics, SiteProfile
from aerisun.domain.subscription.models import ContentSubscriptionConfig


def test_run_pending_backfills_marks_bootstrap_baseline_without_replaying_history(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        seed_bootstrap_data(force=True)

        applied = run_pending_backfills()

        session_factory = get_session_factory()
        with session_factory() as session:
            recorded = list_applied_data_migrations(session, kind="backfill")

        assert applied == []
        assert recorded == {
            "20260403_page_copy_defaults",
            "20260403_community_config_defaults",
            "20260403_system_asset_references",
            "20260403_runtime_config_defaults",
        }
    finally:
        teardown_runtime_state()


def test_run_pending_backfills_applies_registered_repairs_once(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        seed_bootstrap_data(force=True)

        session_factory = get_session_factory()
        with session_factory() as session:
            session.execute(text("DELETE FROM _aerisun_data_migrations"))
            friends_page = session.query(PageCopy).filter(PageCopy.page_key == "friends").one()
            community = session.query(CommunityConfig).one()
            site = session.query(SiteProfile).one()
            resume = session.query(ResumeBasics).one()
            auth = session.query(SiteAuthConfig).one()
            subscription = session.query(ContentSubscriptionConfig).one()

            friends_page.title = "Custom Friends"
            friends_page.extras = {"circle_title": "Custom Circle"}
            community.server_url = "http://localhost:8360/"
            community.surfaces = list((community.surfaces or [])[:3])
            site.og_image = "/images/hero_bg.jpeg"
            resume.profile_image_url = "/images/avatar.webp"
            flags = dict(site.feature_flags or {})
            flags.pop(AGENT_MODEL_CONFIG_FLAG_KEY, None)
            site.feature_flags = flags
            auth.admin_auth_methods = None
            auth.admin_console_auth_methods = None
            subscription.allowed_content_types = []
            subscription.mail_subject_template = ""
            subscription.mail_body_template = ""
            session.commit()

        applied = run_pending_backfills()
        assert applied == [
            "20260403_page_copy_defaults",
            "20260403_community_config_defaults",
            "20260403_system_asset_references",
            "20260403_runtime_config_defaults",
        ]
        assert run_pending_backfills() == []

        with session_factory() as session:
            friends_page = session.query(PageCopy).filter(PageCopy.page_key == "friends").one()
            community = session.query(CommunityConfig).one()
            site = session.query(SiteProfile).one()
            resume = session.query(ResumeBasics).one()
            auth = session.query(SiteAuthConfig).one()
            subscription = session.query(ContentSubscriptionConfig).one()

            assert friends_page.title == "Custom Friends"
            assert friends_page.extras["circle_title"] == "Custom Circle"
            assert friends_page.extras["refreshLabel"] == "刷新"
            assert community.server_url == get_settings().waline_server_url
            assert [item["key"] for item in community.surfaces] == ["posts", "diary", "guestbook", "thoughts", "excerpts"]
            assert site.og_image.startswith("/media/internal/assets/site-og/")
            assert resume.profile_image_url.startswith("/media/internal/assets/resume-avatar/")
            assert AGENT_MODEL_CONFIG_FLAG_KEY in dict(site.feature_flags or {})
            assert auth.admin_auth_methods == []
            assert auth.admin_console_auth_methods == []
            assert subscription.allowed_content_types == ["posts", "diary", "thoughts", "excerpts"]
            assert subscription.mail_subject_template == "[{site_name}] {content_title}"
            assert subscription.mail_body_template
    finally:
        teardown_runtime_state()


def test_run_pending_backfills_records_config_revisions_and_audit(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        seed_bootstrap_data(force=True)

        session_factory = get_session_factory()
        with session_factory() as session:
            session.execute(text("DELETE FROM _aerisun_data_migrations"))
            not_found_page = session.query(PageCopy).filter(PageCopy.page_key == "notFound").one()
            community = session.query(CommunityConfig).one()
            site = session.query(SiteProfile).one()
            auth = session.query(SiteAuthConfig).one()
            subscription = session.query(ContentSubscriptionConfig).one()

            extras = dict(not_found_page.extras or {})
            extras["badgeLabel"] = "Shell mismatch"
            not_found_page.extras = extras
            community.server_url = "http://localhost:8360/"
            site.og_image = "/images/hero_bg.jpeg"
            auth.admin_console_auth_methods = None
            auth.admin_auth_methods = None
            subscription.allowed_content_types = []
            flags = dict(site.feature_flags or {})
            flags.pop(AGENT_MODEL_CONFIG_FLAG_KEY, None)
            site.feature_flags = flags
            session.commit()

        run_pending_backfills()

        with session_factory() as session:
            revisions = session.query(ConfigRevision).filter(ConfigRevision.operation == "backfill").all()
            audits = session.query(AuditLog).filter(AuditLog.action == "DATA BACKFILL APPLY").all()

        assert {item.resource_key for item in revisions} >= {
            "site.pages",
            "site.community",
            "subscriptions.config",
            "site.profile",
        }
        assert all(item.summary.startswith("升级数据回填：") for item in revisions)
        assert len(audits) == 4
        assert {item.payload["migration_key"] for item in audits} == {
            "20260403_page_copy_defaults",
            "20260403_community_config_defaults",
            "20260403_system_asset_references",
            "20260403_runtime_config_defaults",
        }
    finally:
        teardown_runtime_state()
