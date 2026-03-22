from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from aerisun.models import (
    CommunityConfig,
    NavItem,
    PageCopy,
    PageDisplayOption,
    Poem,
    ResumeBasics,
    ResumeExperience,
    ResumeSkillGroup,
    SiteProfile,
    SocialLink,
)
from aerisun.schemas import (
    CommunityConfigRead,
    NavChildRead,
    NavItemRead,
    PageCollectionRead,
    PageCopyRead,
    ResumeExperienceRead,
    ResumeRead,
    ResumeSkillGroupRead,
    SiteConfigRead,
    SiteProfileRead,
    PoemRead,
    SocialLinkRead,
)


def get_site_config(session: Session) -> SiteConfigRead:
    site = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
    if site is None:
        raise LookupError("site profile is missing")

    links = session.scalars(
        select(SocialLink).where(SocialLink.site_profile_id == site.id).order_by(SocialLink.order_index.asc())
    ).all()
    poems = session.scalars(
        select(Poem).where(Poem.site_profile_id == site.id).order_by(Poem.order_index.asc())
    ).all()

    hero_actions = json.loads(site.hero_actions) if site.hero_actions else []

    nav_items = session.scalars(
        select(NavItem)
        .where(NavItem.site_profile_id == site.id, NavItem.is_enabled == True)
        .order_by(NavItem.order_index.asc())
    ).all()

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
                    NavChildRead(label=child.label, href=child.href or "")
                    for child in children_map.get(item.id, [])
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
        ),
        social_links=[SocialLinkRead.model_validate(link) for link in links],
        poems=[PoemRead.model_validate(poem) for poem in poems],
        navigation=navigation,
    )


def get_page_copy(session: Session) -> PageCollectionRead:
    copies = session.scalars(select(PageCopy).order_by(PageCopy.page_key.asc())).all()
    options = {option.page_key: option for option in session.scalars(select(PageDisplayOption)).all()}

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
    config = session.scalars(select(CommunityConfig).order_by(CommunityConfig.created_at.asc())).first()
    if config is None:
        raise LookupError("community config is missing")
    return CommunityConfigRead.model_validate(config)


def get_resume(session: Session) -> ResumeRead:
    basics = session.scalars(select(ResumeBasics).order_by(ResumeBasics.created_at.asc())).first()
    if basics is None:
        raise LookupError("resume basics are missing")

    skill_groups = session.scalars(
        select(ResumeSkillGroup)
        .where(ResumeSkillGroup.resume_basics_id == basics.id)
        .order_by(ResumeSkillGroup.order_index.asc())
    ).all()
    experiences = session.scalars(
        select(ResumeExperience)
        .where(ResumeExperience.resume_basics_id == basics.id)
        .order_by(ResumeExperience.order_index.asc())
    ).all()

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
