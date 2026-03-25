from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.site_config.models import NavItem, PageCopy, PageDisplayOption, Poem, SocialLink
from aerisun.domain.site_config.service import (
    attach_site_profile_id,
    get_community_config_admin,
    get_site_profile_admin,
    reorder_nav_items_admin,
    site_profile_scoped_query,
    update_community_config_admin,
    update_site_profile_admin,
)

from .content import build_crud_router
from .deps import get_current_admin
from .schemas import (
    CommunityConfigAdminRead,
    CommunityConfigUpdate,
    NavItemAdminRead,
    NavItemCreate,
    NavItemUpdate,
    NavReorderItem,
    PageCopyAdminRead,
    PageCopyCreate,
    PageCopyUpdate,
    PageDisplayOptionAdminRead,
    PageDisplayOptionCreate,
    PageDisplayOptionUpdate,
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


@router.get("/profile", response_model=SiteProfileAdminRead, summary="获取站点资料")
def get_profile(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return SiteProfileAdminRead.model_validate(get_site_profile_admin(session))


@router.put("/profile", response_model=SiteProfileAdminRead, summary="更新站点资料")
def update_profile(
    payload: SiteProfileUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    profile = update_site_profile_admin(session, payload.model_dump(exclude_unset=True))
    return SiteProfileAdminRead.model_validate(profile)


@router.get("/community-config", response_model=CommunityConfigAdminRead, summary="获取社区评论配置")
def get_community_config(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return CommunityConfigAdminRead.model_validate(get_community_config_admin(session))


@router.put("/community-config", response_model=CommunityConfigAdminRead, summary="更新社区评论配置")
def update_community_config(
    payload: CommunityConfigUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    config = update_community_config_admin(session, payload.model_dump(exclude_unset=True))
    return CommunityConfigAdminRead.model_validate(config)


social_links_router = build_crud_router(
    SocialLink,
    create_schema=SocialLinkCreate,
    update_schema=SocialLinkUpdate,
    read_schema=SocialLinkAdminRead,
    prefix="/social-links",
    tag="admin-site-config",
    base_query_factory=lambda session: site_profile_scoped_query(session, SocialLink),
    prepare_create_data=attach_site_profile_id,
)

poems_router = build_crud_router(
    Poem,
    create_schema=PoemCreate,
    update_schema=PoemUpdate,
    read_schema=PoemAdminRead,
    prefix="/poems",
    tag="admin-site-config",
    base_query_factory=lambda session: site_profile_scoped_query(session, Poem),
    prepare_create_data=attach_site_profile_id,
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


@router.put("/nav-items/reorder", response_model=list[NavItemAdminRead], summary="重排导航项顺序")
def reorder_nav_items(
    items: list[NavReorderItem],
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    nav_items = reorder_nav_items_admin(session, items)
    return [NavItemAdminRead.model_validate(item) for item in nav_items]


nav_items_router = build_crud_router(
    NavItem,
    create_schema=NavItemCreate,
    update_schema=NavItemUpdate,
    read_schema=NavItemAdminRead,
    prefix="/nav-items",
    tag="admin-site-config",
    base_query_factory=lambda session: site_profile_scoped_query(session, NavItem),
    prepare_create_data=attach_site_profile_id,
)

router.include_router(nav_items_router)
