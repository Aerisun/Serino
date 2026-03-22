from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.site_config.models import (
    CommunityConfig,
    NavItem,
    PageCopy,
    PageDisplayOption,
    Poem,
    SiteProfile,
    SocialLink,
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


# --- SiteProfile: single-row GET/PUT ---


@router.get("/profile", response_model=SiteProfileAdminRead, summary="获取站点资料")
def get_profile(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """返回站点基本资料配置。"""
    profile = session.query(SiteProfile).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Site profile not configured")
    return SiteProfileAdminRead.model_validate(profile)


@router.put("/profile", response_model=SiteProfileAdminRead, summary="更新站点资料")
def update_profile(
    payload: SiteProfileUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """更新站点名称、描述、头像等基本资料。"""
    profile = session.query(SiteProfile).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Site profile not configured")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    session.commit()
    session.refresh(profile)
    return SiteProfileAdminRead.model_validate(profile)


@router.get(
    "/community-config",
    response_model=CommunityConfigAdminRead,
    summary="获取社区评论配置",
)
def get_community_config(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """返回社区评论系统的当前配置。"""
    config = session.query(CommunityConfig).first()
    if config is None:
        raise HTTPException(status_code=404, detail="Community config not configured")
    return CommunityConfigAdminRead.model_validate(config)


@router.put(
    "/community-config",
    response_model=CommunityConfigAdminRead,
    summary="更新社区评论配置",
)
def update_community_config(
    payload: CommunityConfigUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """更新社区评论系统的配置项。"""
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


# --- NavItem reorder (must be registered before CRUD router) ---


@router.put("/nav-items/reorder", response_model=list[NavItemAdminRead], summary="重排导航项顺序")
def reorder_nav_items(
    items: list[NavReorderItem],
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """批量更新导航项的父级关系和排序索引。"""
    for reorder_item in items:
        nav_item = session.get(NavItem, reorder_item.id)
        if nav_item is None:
            raise HTTPException(
                status_code=404, detail=f"NavItem {reorder_item.id} not found"
            )
        nav_item.parent_id = reorder_item.parent_id
        nav_item.order_index = reorder_item.order_index
    session.commit()
    all_items = session.query(NavItem).order_by(NavItem.order_index.asc()).all()
    return [NavItemAdminRead.model_validate(item) for item in all_items]


nav_items_router = build_crud_router(
    NavItem,
    create_schema=NavItemCreate,
    update_schema=NavItemUpdate,
    read_schema=NavItemAdminRead,
    prefix="/nav-items",
    tag="admin-site-config",
)

router.include_router(nav_items_router)
