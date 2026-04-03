from __future__ import annotations

import hashlib
from pathlib import Path

from aerisun.core.backfills.state import BOOTSTRAP_MIGRATION_KEY, list_applied_data_migrations
from aerisun.core.db import get_session_factory
from aerisun.core.seed import seed_bootstrap_data
from aerisun.core.seed_steps.system_assets import get_system_asset_root
from aerisun.core.settings import get_settings
from aerisun.domain.content.models import PostEntry
from aerisun.domain.media.models import Asset
from aerisun.domain.ops.models import AuditLog, ConfigRevision, TrafficDailySnapshot
from aerisun.domain.site_config.models import CommunityConfig, PageCopy, ResumeBasics, SiteProfile
from aerisun.domain.social.models import Friend
from aerisun.domain.waline.service import connect_waline_db


def _assert_force_reseed_cleans_orphan_media(seed_fn, tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        seed_fn(force=True)

        media_root = get_settings().media_dir.expanduser().resolve()
        orphan = media_root / "internal/assets/general/orphan.txt"
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_text("orphan", encoding="utf-8")

        seed_fn(force=True)

        assert not orphan.exists()
    finally:
        teardown_runtime_state()


def test_seed_bootstrap_data_only_initializes_safe_scaffold(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        seed_bootstrap_data(force=True)

        session_factory = get_session_factory()
        with session_factory() as session:
            assert session.query(PageCopy).count() > 0
            assert session.query(PostEntry).count() == 0
            assert session.query(Friend).count() == 0
            assert session.query(TrafficDailySnapshot).count() == 0
            page_widths = {
                page.page_key: page.max_width
                for page in session.query(PageCopy)
                .filter(PageCopy.page_key.in_(["posts", "diary", "excerpts", "thoughts"]))
                .all()
            }
            assert page_widths == {
                "posts": "max-w-4xl",
                "diary": "max-w-3xl",
                "excerpts": "max-w-4xl",
                "thoughts": "max-w-3xl",
            }

        settings = get_settings()
        with connect_waline_db(settings.waline_db_path) as connection:
            total = connection.execute("SELECT COUNT(*) FROM wl_comment").fetchone()
            counters = connection.execute("SELECT COUNT(*) FROM wl_counter").fetchone()

        assert int(total[0]) == 0
        assert int(counters[0]) == 0
    finally:
        teardown_runtime_state()


def test_seed_bootstrap_data_uses_updated_defaults(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        seed_bootstrap_data(force=True)

        session_factory = get_session_factory()
        with session_factory() as session:
            community = session.query(CommunityConfig).one()

        assert community.image_uploader is True
    finally:
        teardown_runtime_state()


def test_seed_bootstrap_data_uses_backend_system_asset_sources(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        seed_bootstrap_data(force=True)

        session_factory = get_session_factory()
        with session_factory() as session:
            site = session.query(SiteProfile).one()
            resume = session.query(ResumeBasics).one()
            assets = {asset.category: asset for asset in session.query(Asset).all()}

        assert site.og_image.startswith("/media/internal/assets/site-og/")
        assert site.site_icon_url.startswith("/media/internal/assets/site-icon/")
        assert site.hero_image_url.startswith("/media/internal/assets/hero-image/")
        assert site.hero_poster_url.startswith("/media/internal/assets/hero-poster/")
        assert resume.profile_image_url.startswith("/media/internal/assets/resume-avatar/")

        asset_root = get_system_asset_root()
        assert (
            asset_root
            == Path(__file__).resolve().parents[1]
            / "src"
            / "aerisun"
            / "core"
            / "seed_steps"
            / "resources"
            / "system_assets"
        )
        assert (
            assets["site-og"].sha256 == hashlib.sha256((asset_root / "share_fallback_bg.webp").read_bytes()).hexdigest()
        )
        assert (
            assets["site-icon"].sha256 == hashlib.sha256((asset_root / "browser_tab_icon.svg").read_bytes()).hexdigest()
        )
        assert (
            assets["hero-image"].sha256
            == hashlib.sha256((asset_root / "hero_flip_visual.webp").read_bytes()).hexdigest()
        )
        assert (
            assets["hero-poster"].sha256
            == hashlib.sha256((asset_root / "hero_video_poster.webp").read_bytes()).hexdigest()
        )
        assert (
            assets["resume-avatar"].sha256
            == hashlib.sha256((asset_root / "resume_avatar.webp").read_bytes()).hexdigest()
        )
    finally:
        teardown_runtime_state()


def test_seed_bootstrap_data_marks_bootstrap_and_does_not_backfill_existing_rows(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        seed_bootstrap_data(force=True)

        session_factory = get_session_factory()
        with session_factory() as session:
            community = session.query(CommunityConfig).one()
            friends_page = session.query(PageCopy).filter(PageCopy.page_key == "friends").one()
            site = session.query(SiteProfile).one()

            community.server_url = "http://localhost:8360/"
            friends_page.extras = {"circle_title": "Custom Circle"}
            site.og_image = "/images/hero_bg.jpeg"
            session.commit()

        seed_bootstrap_data()

        with session_factory() as session:
            community = session.query(CommunityConfig).one()
            friends_page = session.query(PageCopy).filter(PageCopy.page_key == "friends").one()
            site = session.query(SiteProfile).one()
            applied = list_applied_data_migrations(session, kind="bootstrap")

        assert community.server_url == "http://localhost:8360/"
        assert friends_page.extras == {"circle_title": "Custom Circle"}
        assert site.og_image == "/images/hero_bg.jpeg"
        assert BOOTSTRAP_MIGRATION_KEY in applied
    finally:
        teardown_runtime_state()


def test_seed_bootstrap_data_force_reseed_cleans_media_root(tmp_path, monkeypatch) -> None:
    _assert_force_reseed_cleans_orphan_media(seed_bootstrap_data, tmp_path, monkeypatch)


def test_seed_bootstrap_data_force_reseeds_config_history_and_system_audit(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        seed_bootstrap_data(force=True)

        session_factory = get_session_factory()
        with session_factory() as session:
            session.add(
                AuditLog(
                    actor_type="admin",
                    actor_id=None,
                    action="LEGACY AUDIT",
                    target_type="legacy",
                    target_id="legacy",
                    payload={"legacy": True},
                )
            )
            session.add(
                ConfigRevision(
                    actor_id=None,
                    resource_key="site.profile",
                    resource_label="站点资料",
                    operation="legacy",
                    resource_version="legacy",
                    summary="legacy",
                    changed_fields=["legacy"],
                    before_snapshot={"legacy": True},
                    after_snapshot={"legacy": True},
                    before_preview={"legacy": True},
                    after_preview={"legacy": True},
                    sensitive_fields=[],
                )
            )
            session.commit()

        seed_bootstrap_data(force=True)

        with session_factory() as session:
            revisions = session.query(ConfigRevision).all()
            logs = session.query(AuditLog).all()

            assert revisions
            assert logs
            assert all(item.operation == "seed" for item in revisions)
            assert all(item.summary.startswith("生产种子初始化：") for item in revisions)
            assert {item.resource_key for item in revisions} == {
                "site.profile",
                "site.community",
                "site.navigation",
                "site.social_links",
                "site.poems",
                "site.pages",
                "visitors.auth",
                "subscriptions.config",
                "network.outbound_proxy",
                "integrations.mcp_public_access",
                "automation.model_config",
                "automation.workflows",
            }
            assert all(str(item.action).startswith("CONFIG SEED ") for item in logs)
            assert all(item.payload.get("config_revision_id") for item in logs)
    finally:
        teardown_runtime_state()
