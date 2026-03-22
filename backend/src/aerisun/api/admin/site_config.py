from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.models import (
    AdminUser,
    CommunityConfig,
    PageCopy,
    PageDisplayOption,
    Poem,
    SiteProfile,
    SocialLink,
)

from .content import build_crud_router
from .deps import get_current_admin
from .schemas import (
    PageCopyAdminRead,
    PageCopyCreate,
    PageCopyUpdate,
    PageDisplayOptionAdminRead,
    PageDisplayOptionCreate,
    PageDisplayOptionUpdate,
    CommunityConfigAdminRead,
    CommunityConfigUpdate,
    PoemAdminRead,
    PoemCreate,
    PoemUpdate,
    SiteProfileAdminRead,
    SiteProfileUpdate,
    SocialLinkAdminRead,
    SocialLinkCreate,
    SocialLinkUpdate,
)

router = APIRouter(prefix="/site-config", tags=["admin-site-config"])


# --- SiteProfile: single-row GET/PUT ---

@router.get("/profile", response_model=SiteProfileAdminRead)
def get_profile(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    profile = session.query(SiteProfile).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Site profile not configured")
    return SiteProfileAdminRead.model_validate(profile)


@router.put("/profile", response_model=SiteProfileAdminRead)
def update_profile(
    payload: SiteProfileUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    profile = session.query(SiteProfile).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Site profile not configured")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    session.commit()
    session.refresh(profile)
    return SiteProfileAdminRead.model_validate(profile)


@router.get("/community-config", response_model=CommunityConfigAdminRead)
def get_community_config(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    config = session.query(CommunityConfig).first()
    if config is None:
        raise HTTPException(status_code=404, detail="Community config not configured")
    return CommunityConfigAdminRead.model_validate(config)


@router.put("/community-config", response_model=CommunityConfigAdminRead)
def update_community_config(
    payload: CommunityConfigUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    config = session.query(CommunityConfig).first()
    if config is None:
        raise HTTPException(status_code=404, detail="Community config not configured")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(config, key, value)
    session.commit()
    session.refresh(config)
    return CommunityConfigAdminRead.model_validate(config)


# --- Sub-resources via CRUD factory ---

social_links_router = build_crud_router(
    SocialLink,
    create_schema=SocialLinkCreate,
    update_schema=SocialLinkUpdate,
    read_schema=SocialLinkAdminRead,
    prefix="/social-links",
    tag="admin-site-config",
)

poems_router = build_crud_router(
    Poem,
    create_schema=PoemCreate,
    update_schema=PoemUpdate,
    read_schema=PoemAdminRead,
    prefix="/poems",
    tag="admin-site-config",
)

page_copy_router = build_crud_router(
    PageCopy,
    create_schema=PageCopyCreate,
    update_schema=PageCopyUpdate,
    read_schema=PageCopyAdminRead,
    prefix="/page-copy",
    tag="admin-site-config",
)

display_options_router = build_crud_router(
    PageDisplayOption,
    create_schema=PageDisplayOptionCreate,
    update_schema=PageDisplayOptionUpdate,
    read_schema=PageDisplayOptionAdminRead,
    prefix="/display-options",
    tag="admin-site-config",
)

router.include_router(social_links_router)
router.include_router(poems_router)
router.include_router(page_copy_router)
router.include_router(display_options_router)
