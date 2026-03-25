from __future__ import annotations

import json

from pydantic import BaseModel
from sqlalchemy.orm import Session

from aerisun.domain.exceptions import ResourceNotFound
from aerisun.domain.site_config import repository as repo
from aerisun.domain.site_config.schemas import (
    CommunityConfigAdminRead,
    CommunityConfigRead,
    NavChildRead,
    NavItemAdminRead,
    NavItemRead,
    PageCollectionRead,
    PageCopyRead,
    PoemRead,
    ResumeExperienceRead,
    ResumeRead,
    ResumeSkillGroupRead,
    SiteConfigRead,
    SiteProfileAdminRead,
    SiteProfileRead,
    SocialLinkRead,
)


def get_site_config(session: Session) -> SiteConfigRead:
    site = repo.find_site_profile(session)
    if site is None:
        raise ResourceNotFound("site profile is missing")

    links = repo.find_social_links(session, site.id)
    poems = repo.find_poems(session, site.id)

    hero_actions = json.loads(site.hero_actions) if site.hero_actions else []

    nav_items = repo.find_enabled_nav_items(session, site.id)

    children_map: dict[str, list] = {}
    for item in nav_items:
        if item.parent_id:
            children_map.setdefault(item.parent_id, []).append(item)

    navigation = []
    for item in nav_items:
        if item.parent_id is None:
            nav_read = NavItemRead(
                label=item.label,
                trigger=item.trigger,
                href=item.href,
                children=[
                    NavChildRead(label=child.label, href=child.href or "") for child in children_map.get(item.id, [])
                ],
            )
            navigation.append(nav_read)

    return SiteConfigRead(
        site=SiteProfileRead(
            name=site.name,
            title=site.title,
            bio=site.bio,
            role=site.role,
            footer_text=site.footer_text,
            author=site.author,
            og_image=site.og_image,
            meta_description=site.meta_description,
            copyright=site.copyright,
            hero_actions=hero_actions,
            hero_video_url=site.hero_video_url,
            feature_flags=site.feature_flags if site.feature_flags else {},
        ),
        social_links=[SocialLinkRead.model_validate(link) for link in links],
        poems=[PoemRead.model_validate(poem) for poem in poems],
        navigation=navigation,
    )


def get_page_copy(session: Session) -> PageCollectionRead:
    copies = repo.find_all_page_copies(session)
    options = repo.find_all_page_display_options(session)

    items = []
    for page in copies:
        option = options.get(page.page_key)
        items.append(
            PageCopyRead(
                page_key=page.page_key,
                label=page.label,
                nav_label=page.nav_label,
                title=page.title,
                subtitle=page.subtitle,
                description=page.description,
                search_placeholder=page.search_placeholder,
                empty_message=page.empty_message,
                max_width=page.max_width,
                page_size=page.page_size,
                download_label=page.download_label,
                enabled=True if option is None else option.is_enabled,
                extras=page.extras,
            )
        )

    return PageCollectionRead(items=items)


def get_community_config(session: Session) -> CommunityConfigRead:
    config = repo.find_community_config(session)
    if config is None:
        raise ResourceNotFound("community config is missing")
    return CommunityConfigRead.model_validate(config)


def get_resume(session: Session) -> ResumeRead:
    basics = repo.find_resume_basics(session)
    if basics is None:
        raise ResourceNotFound("resume basics are missing")

    skill_groups = repo.find_resume_skill_groups(session, basics.id)
    experiences = repo.find_resume_experiences(session, basics.id)

    return ResumeRead(
        title=basics.title,
        subtitle=basics.subtitle,
        summary=basics.summary,
        download_label=basics.download_label,
        skill_groups=[
            ResumeSkillGroupRead(
                category=group.category,
                items=list(group.items),
                order_index=group.order_index,
            )
            for group in skill_groups
        ],
        experiences=[ResumeExperienceRead.model_validate(item) for item in experiences],
    )


load_site_bundle = get_site_config
load_pages_bundle = get_page_copy
load_community_bundle = get_community_config
load_resume_bundle = get_resume


# ---------------------------------------------------------------------------
# Admin helpers
# ---------------------------------------------------------------------------


def _get_site_profile_orm(session: Session):
    """Return the primary SiteProfile ORM object, raising ResourceNotFound if missing."""
    from aerisun.domain.site_config.models import SiteProfile

    profile = session.query(SiteProfile).order_by(SiteProfile.created_at.asc()).first()
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    return profile


def get_site_profile_admin(session: Session) -> SiteProfileAdminRead:
    """Return the primary SiteProfile as a DTO."""
    profile = _get_site_profile_orm(session)
    return SiteProfileAdminRead.model_validate(profile)


def update_site_profile_admin(session: Session, payload: BaseModel) -> SiteProfileAdminRead:
    """Update the primary SiteProfile fields."""
    profile = _get_site_profile_orm(session)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    session.commit()
    session.refresh(profile)
    return SiteProfileAdminRead.model_validate(profile)


def _get_community_config_orm(session: Session):
    """Return the CommunityConfig ORM object, raising ResourceNotFound if missing."""
    from aerisun.domain.site_config.models import CommunityConfig

    config = session.query(CommunityConfig).first()
    if config is None:
        raise ResourceNotFound("Community config not configured")
    return config


def get_community_config_admin(session: Session) -> CommunityConfigAdminRead:
    """Return CommunityConfig as a DTO."""
    config = _get_community_config_orm(session)
    return CommunityConfigAdminRead.model_validate(config)


def update_community_config_admin(session: Session, payload: BaseModel) -> CommunityConfigAdminRead:
    """Update CommunityConfig fields."""
    config = _get_community_config_orm(session)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(config, key, value)
    session.commit()
    session.refresh(config)
    return CommunityConfigAdminRead.model_validate(config)


def reorder_nav_items_admin(session: Session, reorder_list: list) -> list[NavItemAdminRead]:
    """Reorder nav items by updating parent_id and order_index."""
    from aerisun.domain.site_config.models import NavItem

    profile = _get_site_profile_orm(session)
    scoped = {
        item.id: item
        for item in session.query(NavItem)
        .filter(NavItem.site_profile_id == profile.id)
        .order_by(NavItem.order_index.asc())
        .all()
    }
    for reorder_item in reorder_list:
        nav_item = scoped.get(reorder_item.id)
        if nav_item is None:
            raise ResourceNotFound(f"NavItem {reorder_item.id} not found")
        nav_item.parent_id = reorder_item.parent_id
        nav_item.order_index = reorder_item.order_index
    session.commit()
    items = list(
        session.query(NavItem).filter(NavItem.site_profile_id == profile.id).order_by(NavItem.order_index.asc()).all()
    )
    return [NavItemAdminRead.model_validate(item) for item in items]


def site_profile_scoped_query(session: Session, model):
    """Return a query scoped to the primary SiteProfile."""
    profile = _get_site_profile_orm(session)
    return session.query(model).filter(model.site_profile_id == profile.id)


def attach_site_profile_id(session: Session, data: dict) -> dict:
    """Ensure data dict includes the primary site_profile_id."""
    profile = _get_site_profile_orm(session)
    if not data.get("site_profile_id"):
        data["site_profile_id"] = profile.id
    return data


def get_resume_basics_admin(session: Session):
    """Return primary ResumeBasics, raising ResourceNotFound if missing."""
    from aerisun.domain.site_config.models import ResumeBasics

    basics = session.query(ResumeBasics).order_by(ResumeBasics.created_at.asc()).first()
    if basics is None:
        raise ResourceNotFound("Resume basics not configured")
    return basics


def resume_scoped_query(session: Session, model):
    """Return a query scoped to the primary ResumeBasics."""
    basics = get_resume_basics_admin(session)
    return session.query(model).filter(model.resume_basics_id == basics.id)


def attach_resume_basics_id(session: Session, data: dict) -> dict:
    """Ensure data dict includes the primary resume_basics_id."""
    basics = get_resume_basics_admin(session)
    if not data.get("resume_basics_id"):
        data["resume_basics_id"] = basics.id
    return data
