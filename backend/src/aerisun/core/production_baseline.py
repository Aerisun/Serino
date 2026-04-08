from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import select

from aerisun.core.data_migrations.state import (
    ensure_migration_journal,
    get_migration_entry,
    mark_baseline_applied,
)
from aerisun.core.db import get_session_factory
from aerisun.core.seed import (
    DEFAULT_PAGE_COPIES,
    DEFAULT_POEMS,
    DEFAULT_RESUME,
    DEFAULT_SITE_PROFILE,
    DEFAULT_SOCIAL_LINKS,
    PRODUCTION_CONFIG_HISTORY_RESOURCES,
    _clear_seed_data,
    _seed_agent_model_config,
    _seed_community_config,
    _seed_config_history_and_audit,
    _seed_nav_items,
    _seed_site_auth_config,
    _seed_subscription_config_from_settings,
)
from aerisun.core.seed_steps.assets import purge_managed_media_root
from aerisun.core.seed_steps.common import is_empty
from aerisun.core.seed_steps.content import insert_missing_page_copies
from aerisun.core.seed_steps.system_assets import seed_core_system_asset_urls
from aerisun.core.seed_steps.waline import clear_waline_seed_data
from aerisun.core.settings import get_settings
from aerisun.domain.site_config.models import Poem, ResumeBasics, SiteProfile, SocialLink
from aerisun.domain.waline.service import connect_waline_db

PRODUCTION_BASELINE_ID = "2026_04_production_baseline_v1"
PRODUCTION_BASELINE_SCHEMA_REVISION = "0001_production_baseline"


def baseline_checksum() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def has_production_baseline(session) -> bool:
    entry = get_migration_entry(session, PRODUCTION_BASELINE_ID)
    return entry is not None and entry.status == "applied"


def _ensure_waline_schema() -> None:
    with connect_waline_db(get_settings().waline_db_path):
        return


def _apply_reference_baseline(session, *, force: bool = False) -> None:
    seeded_assets = seed_core_system_asset_urls(session)

    if is_empty(session, SiteProfile):
        site = SiteProfile(
            **{
                **DEFAULT_SITE_PROFILE,
                "og_image": seeded_assets["og_image"],
                "site_icon_url": seeded_assets["site_icon_url"],
                "hero_image_url": seeded_assets["hero_image_url"],
                "hero_poster_url": seeded_assets["hero_poster_url"],
            }
        )
        session.add(site)
        session.flush()

        session.add_all([SocialLink(site_profile_id=site.id, **item) for item in DEFAULT_SOCIAL_LINKS])
        session.add_all(
            [Poem(site_profile_id=site.id, order_index=index, content=text) for index, text in enumerate(DEFAULT_POEMS)]
        )
        insert_missing_page_copies(session, DEFAULT_PAGE_COPIES)

        resume = ResumeBasics(**{**DEFAULT_RESUME, "profile_image_url": seeded_assets["profile_image_url"]})
        session.add(resume)
        session.flush()

    current_site = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
    if current_site is not None:
        _seed_nav_items(session, site_id=current_site.id)

    _seed_community_config(session, force=force)
    _seed_site_auth_config(session, force=force)
    _seed_subscription_config_from_settings(session, force=force)
    _seed_agent_model_config(session, force=force)
    _seed_config_history_and_audit(
        session,
        resources=PRODUCTION_CONFIG_HISTORY_RESOURCES,
        operation="baseline",
        summary_prefix="生产 baseline 初始化",
    )


def apply_production_baseline(*, force: bool = False) -> bool:
    settings = get_settings()
    settings.ensure_directories()

    session_factory = get_session_factory()
    with session_factory() as session:
        ensure_migration_journal(session)
        if has_production_baseline(session) and not force:
            return False

        if force:
            _clear_seed_data(session)
            clear_waline_seed_data()
            session.commit()
            purge_managed_media_root()

        _ensure_waline_schema()
        _apply_reference_baseline(session, force=force)
        mark_baseline_applied(
            session,
            migration_key=PRODUCTION_BASELINE_ID,
            schema_revision=PRODUCTION_BASELINE_SCHEMA_REVISION,
            checksum=baseline_checksum(),
        )
        session.commit()
    return True
