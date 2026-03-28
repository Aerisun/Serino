from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from aerisun.domain.site_config.models import (
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


def find_site_profile(session: Session) -> SiteProfile | None:
    """Get the first (primary) site profile."""
    return session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()


def find_social_links(session: Session, site_profile_id: str) -> list[SocialLink]:
    """Get social links for a site profile, ordered by order_index."""
    return list(
        session.scalars(
            select(SocialLink)
            .where(SocialLink.site_profile_id == site_profile_id)
            .order_by(SocialLink.order_index.asc())
        ).all()
    )


def find_poems(session: Session, site_profile_id: str) -> list[Poem]:
    """Get poems for a site profile, ordered by order_index."""
    return list(
        session.scalars(
            select(Poem).where(Poem.site_profile_id == site_profile_id).order_by(Poem.order_index.asc())
        ).all()
    )


def find_enabled_nav_items(session: Session, site_profile_id: str) -> list[NavItem]:
    """Get enabled nav items for a site profile, ordered by order_index."""
    return list(
        session.scalars(
            select(NavItem)
            .where(
                NavItem.site_profile_id == site_profile_id,
                NavItem.is_enabled.is_(True),
            )
            .order_by(NavItem.order_index.asc())
        ).all()
    )


def find_all_page_copies(session: Session) -> list[PageCopy]:
    """Get all page copies ordered by page_key."""
    return list(session.scalars(select(PageCopy).order_by(PageCopy.page_key.asc())).all())


def find_all_page_display_options(session: Session) -> dict[str, PageDisplayOption]:
    """Get all page display options as {page_key: option} dict."""
    options = session.scalars(select(PageDisplayOption)).all()
    return {opt.page_key: opt for opt in options}


def find_community_config(session: Session) -> CommunityConfig | None:
    """Get the first community config."""
    return session.scalars(select(CommunityConfig).order_by(CommunityConfig.created_at.asc())).first()


def find_resume_basics(session: Session) -> ResumeBasics | None:
    """Get the first resume basics record."""
    return session.scalars(select(ResumeBasics).order_by(ResumeBasics.created_at.asc())).first()


def find_resume_skill_groups(session: Session, resume_id: str) -> list[ResumeSkillGroup]:
    """Get skill groups for a resume, ordered by order_index."""
    return list(
        session.scalars(
            select(ResumeSkillGroup)
            .where(ResumeSkillGroup.resume_basics_id == resume_id)
            .order_by(ResumeSkillGroup.order_index.asc())
        ).all()
    )


def find_resume_experiences(session: Session, resume_id: str) -> list[ResumeExperience]:
    """Get experiences for a resume, ordered by order_index."""
    return list(
        session.scalars(
            select(ResumeExperience)
            .where(ResumeExperience.resume_basics_id == resume_id)
            .order_by(ResumeExperience.order_index.asc())
        ).all()
    )
