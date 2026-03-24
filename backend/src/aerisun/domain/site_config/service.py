from __future__ import annotations

import json

from sqlalchemy.orm import Session

from aerisun.domain.site_config import repository as repo
from aerisun.domain.site_config.schemas import (
    CommunityConfigRead,
    NavChildRead,
    NavItemRead,
    PageCollectionRead,
    PageCopyRead,
    PoemRead,
    ResumeExperienceRead,
    ResumeRead,
    ResumeSkillGroupRead,
    SiteConfigRead,
    SiteProfileRead,
    SocialLinkRead,
)


def get_site_config(session: Session) -> SiteConfigRead:
    site = repo.find_site_profile(session)
    if site is None:
        raise LookupError("site profile is missing")

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
        raise LookupError("community config is missing")
    return CommunityConfigRead.model_validate(config)


def get_resume(session: Session) -> ResumeRead:
    basics = repo.find_resume_basics(session)
    if basics is None:
        raise LookupError("resume basics are missing")

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
