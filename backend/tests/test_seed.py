from __future__ import annotations

import hashlib
from pathlib import Path

from aerisun.core.db import get_session_factory
from aerisun.core.db_preflight import compute_seed_fingerprint, run_preflight, store_seed_metadata
from aerisun.core.dev_seed import seed_development_data, seed_reference_data
from aerisun.core.seed import seed_bootstrap_data
from aerisun.core.seed_profile import resolve_seed_path
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


def test_seed_reference_data_backfills_missing_activity_page(client) -> None:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        session.query(PageCopy).filter(PageCopy.page_key == "activity").delete()
        session.commit()
    finally:
        session.close()

    seed_reference_data()

    session = session_factory()
    try:
        activity_page = session.query(PageCopy).filter(PageCopy.page_key == "activity").one()
        assert activity_page.title == "友邻与最近动态"
        assert activity_page.extras["dashboardLabel"] == "Dashboard"
    finally:
        session.close()


def test_seed_reference_data_merges_missing_page_copy_extras(client) -> None:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        friends_page = session.query(PageCopy).filter(PageCopy.page_key == "friends").one()
        friends_page.title = "Custom Friends"
        friends_page.extras = {"circle_title": "Custom Circle"}
        session.commit()
    finally:
        session.close()

    seed_reference_data()

    session = session_factory()
    try:
        friends_page = session.query(PageCopy).filter(PageCopy.page_key == "friends").one()
        assert friends_page.title == "Custom Friends"
        assert friends_page.extras["circle_title"] == "Custom Circle"
        assert friends_page.extras["refreshLabel"] == "刷新"
    finally:
        session.close()


def test_seed_reference_data_sets_default_page_sizes_for_public_lists(client) -> None:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        page_sizes = {
            page.page_key: page.page_size
            for page in session.query(PageCopy)
            .filter(PageCopy.page_key.in_(["posts", "diary", "excerpts", "thoughts"]))
            .all()
        }
        assert page_sizes == {
            "posts": 15,
            "diary": 15,
            "excerpts": 15,
            "thoughts": 15,
        }
    finally:
        session.close()


def test_seed_reference_data_updates_legacy_calendar_weekday_order(client) -> None:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        calendar_page = session.query(PageCopy).filter(PageCopy.page_key == "calendar").one()
        calendar_page.extras = {
            **(calendar_page.extras or {}),
            "weekdayLabels": ["周日", "周一", "周二", "周三", "周四", "周五", "周六"],
        }
        session.commit()
    finally:
        session.close()

    seed_reference_data()

    session = session_factory()
    try:
        calendar_page = session.query(PageCopy).filter(PageCopy.page_key == "calendar").one()
        assert calendar_page.extras["weekdayLabels"] == [
            "周一",
            "周二",
            "周三",
            "周四",
            "周五",
            "周六",
            "周日",
        ]
    finally:
        session.close()


def test_seed_reference_data_provides_comment_samples_and_is_idempotent(client) -> None:
    settings = get_settings()

    def waline_snapshot() -> dict[str, object]:
        with connect_waline_db(settings.waline_db_path) as connection:
            total = connection.execute("SELECT COUNT(*) FROM wl_comment").fetchone()
            approved_guestbook = connection.execute(
                "SELECT COUNT(*) FROM wl_comment WHERE url = '/guestbook' AND status = 'approved'"
            ).fetchone()
            root_comment = connection.execute(
                """
                SELECT nick, url
                FROM wl_comment
                WHERE url = '/posts/from-zero-design-system' AND pid IS NULL
                ORDER BY id ASC
                LIMIT 1
                """
            ).fetchone()
            reply_comment = connection.execute(
                """
                SELECT nick, pid
                FROM wl_comment
                WHERE url = '/posts/from-zero-design-system' AND pid IS NOT NULL
                ORDER BY id ASC
                LIMIT 1
                """
            ).fetchone()
            return {
                "waline_comment_count": int(total[0]) if total else 0,
                "waline_guestbook_approved_count": int(approved_guestbook[0]) if approved_guestbook else 0,
                "waline_root_author": str(root_comment["nick"]) if root_comment else "",
                "waline_root_url": str(root_comment["url"]) if root_comment else "",
                "waline_reply_author": str(reply_comment["nick"]) if reply_comment else "",
                "waline_reply_has_parent": bool(reply_comment and reply_comment["pid"]),
            }

    before = waline_snapshot()
    assert before == {
        "waline_comment_count": 6,
        "waline_guestbook_approved_count": 2,
        "waline_root_author": "林小北",
        "waline_root_url": "/posts/from-zero-design-system",
        "waline_reply_author": "Felix",
        "waline_reply_has_parent": True,
    }

    seed_reference_data()

    after = waline_snapshot()
    assert after == before


def test_seed_reference_data_provides_traffic_snapshot_samples(client) -> None:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        total = session.query(TrafficDailySnapshot).count()
        latest_home = (
            session.query(TrafficDailySnapshot)
            .filter(TrafficDailySnapshot.url == "/")
            .order_by(TrafficDailySnapshot.snapshot_date.desc())
            .first()
        )
    finally:
        session.close()

    assert total >= 14 * 6
    assert latest_home is not None
    assert latest_home.cumulative_views > 0
    assert latest_home.daily_views > 0


def test_seed_reference_data_force_reseeds_waline_rows(client) -> None:
    settings = get_settings()

    with connect_waline_db(settings.waline_db_path) as connection:
        connection.execute("DELETE FROM wl_comment")
        connection.execute("DELETE FROM wl_counter")
        connection.execute(
            "INSERT INTO wl_comment (comment, nick, status, url) VALUES (?, ?, ?, ?)",
            ("temporary comment", "Temp", "approved", "/temporary"),
        )
        connection.commit()

    seed_reference_data(force=True)

    with connect_waline_db(settings.waline_db_path) as connection:
        total = connection.execute("SELECT COUNT(*) FROM wl_comment").fetchone()
        temp = connection.execute("SELECT COUNT(*) FROM wl_comment WHERE url = '/temporary'").fetchone()

    assert int(total[0]) == 6
    assert int(temp[0]) == 0


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


def test_seed_bootstrap_data_force_reseed_cleans_media_root(tmp_path, monkeypatch) -> None:
    _assert_force_reseed_cleans_orphan_media(seed_bootstrap_data, tmp_path, monkeypatch)


def test_seed_development_data_uses_updated_defaults(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        seed_development_data(force=True)

        session_factory = get_session_factory()
        with session_factory() as session:
            community = session.query(CommunityConfig).one()

        assert community.image_uploader is True
    finally:
        teardown_runtime_state()


def test_seed_development_data_force_reseed_cleans_media_root(tmp_path, monkeypatch) -> None:
    _assert_force_reseed_cleans_orphan_media(seed_development_data, tmp_path, monkeypatch)


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


def test_seed_development_data_still_provides_full_sample_dataset(tmp_path, monkeypatch) -> None:
    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        seed_development_data(force=True)

        session_factory = get_session_factory()
        with session_factory() as session:
            assert session.query(Friend).count() > 0
            assert session.query(TrafficDailySnapshot).count() > 0
    finally:
        teardown_runtime_state()


def test_seed_profile_switch_from_dev_seed_to_seed_triggers_reseed(tmp_path, monkeypatch) -> None:
    import sqlite3
    from pathlib import Path

    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        seed_development_data(force=True)
        settings = get_settings()
        core_dir = Path("src/aerisun/core")
        known_revisions = sorted(
            line.strip().split("=")[1].strip().strip("\"'")
            for path in (Path("alembic") / "versions").glob("*.py")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith("revision") and "=" in line
        )
        with sqlite3.connect(settings.db_path) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
            connection.execute("DELETE FROM alembic_version")
            connection.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (known_revisions[-1],))
            connection.commit()
        dev_seed_path = resolve_seed_path(core_dir, seed_profile="dev-seed")
        store_seed_metadata(
            settings.db_path,
            fingerprint=compute_seed_fingerprint(dev_seed_path, seed_profile="dev-seed"),
        )

        result = run_preflight(
            db_path=settings.db_path,
            alembic_dir=Path("alembic"),
            seed_path=resolve_seed_path(core_dir, seed_profile="seed"),
            seed_profile="seed",
        )

        assert result["reseed"] is True
        assert result["reason"] == "数据库版本兼容，但种子已变化"
    finally:
        teardown_runtime_state()


def test_seed_preflight_detects_legacy_dev_seed_residue_for_seed_profile(tmp_path, monkeypatch) -> None:
    import sqlite3
    from pathlib import Path

    from tests.support.runtime import configure_runtime_environment, reset_runtime_state, teardown_runtime_state

    configure_runtime_environment(tmp_path, monkeypatch)
    reset_runtime_state()
    try:
        seed_development_data(force=True)
        settings = get_settings()
        core_dir = Path("src/aerisun/core")
        seed_path = resolve_seed_path(core_dir, seed_profile="seed")
        known_revisions = sorted(
            line.strip().split("=")[1].strip().strip("\"'")
            for path in (Path("alembic") / "versions").glob("*.py")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith("revision") and "=" in line
        )
        with sqlite3.connect(settings.db_path) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
            connection.execute("DELETE FROM alembic_version")
            connection.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (known_revisions[-1],))
            connection.commit()
        store_seed_metadata(
            settings.db_path,
            fingerprint=compute_seed_fingerprint(seed_path, seed_profile="seed"),
        )

        result = run_preflight(
            db_path=settings.db_path,
            alembic_dir=Path("alembic"),
            seed_path=seed_path,
            seed_profile="seed",
        )

        assert result["reseed"] is True
        assert result["reason"] == "数据库版本兼容，但检测到旧的开发测试种子残留"
    finally:
        teardown_runtime_state()
