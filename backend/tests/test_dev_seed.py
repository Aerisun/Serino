from __future__ import annotations

from aerisun.core.db import get_session_factory
from aerisun.core.db_preflight import compute_seed_fingerprint, run_preflight, store_seed_metadata
from aerisun.core.dev_seed import seed_development_data
from aerisun.core.seed_profile import resolve_seed_path
from aerisun.core.settings import get_settings
from aerisun.domain.site_config.models import CommunityConfig
from aerisun.domain.social.models import Friend
from aerisun.domain.ops.models import TrafficDailySnapshot
from aerisun.domain.waline.service import connect_waline_db


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


def test_seed_development_data_provides_comment_samples_and_is_idempotent(client) -> None:
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

    seed_development_data()

    after = waline_snapshot()
    assert after == before


def test_seed_development_data_provides_traffic_snapshot_samples(client) -> None:
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


def test_seed_development_data_force_reseeds_waline_rows(client) -> None:
    settings = get_settings()

    with connect_waline_db(settings.waline_db_path) as connection:
        connection.execute("DELETE FROM wl_comment")
        connection.execute("DELETE FROM wl_counter")
        connection.execute(
            "INSERT INTO wl_comment (comment, nick, status, url) VALUES (?, ?, ?, ?)",
            ("temporary comment", "Temp", "approved", "/temporary"),
        )
        connection.commit()

    seed_development_data(force=True)

    with connect_waline_db(settings.waline_db_path) as connection:
        total = connection.execute("SELECT COUNT(*) FROM wl_comment").fetchone()
        temp = connection.execute("SELECT COUNT(*) FROM wl_comment WHERE url = '/temporary'").fetchone()

    assert int(total[0]) == 6
    assert int(temp[0]) == 0


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
