from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.ops.config_revisions import capture_config_resource, create_config_revision
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
    return get_site_profile_admin(session)


@router.put("/profile", response_model=SiteProfileAdminRead, summary="更新站点资料")
def update_profile(
    payload: SiteProfileUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    before_snapshot = capture_config_resource(session, "site.profile")
    result = update_site_profile_admin(session, payload)
    after_snapshot = capture_config_resource(session, "site.profile")
    create_config_revision(
        session,
        actor_id=_admin.id,
        resource_key="site.profile",
        operation="update",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    return result


@router.get("/community-config", response_model=CommunityConfigAdminRead, summary="获取社区评论配置")
def get_community_config(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return get_community_config_admin(session)


@router.put("/community-config", response_model=CommunityConfigAdminRead, summary="更新社区评论配置")
def update_community_config(
    payload: CommunityConfigUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    before_snapshot = capture_config_resource(session, "site.community")
    result = update_community_config_admin(session, payload)
    after_snapshot = capture_config_resource(session, "site.community")
    create_config_revision(
        session,
        actor_id=_admin.id,
        resource_key="site.community",
        operation="update",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    return result


social_links_router = build_crud_router(
    SocialLink,
    create_schema=SocialLinkCreate,
    update_schema=SocialLinkUpdate,
    read_schema=SocialLinkAdminRead,
    prefix="/social-links",
    tag="admin-site-config",
    base_query_factory=lambda session: site_profile_scoped_query(session, SocialLink),
    prepare_create_data=attach_site_profile_id,
    config_resource_key="site.social_links",
    capture_before=lambda session: capture_config_resource(session, "site.social_links"),
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
    config_resource_key="site.poems",
    capture_before=lambda session: capture_config_resource(session, "site.poems"),
)

page_copy_router = build_crud_router(
    PageCopy,
    create_schema=PageCopyCreate,
    update_schema=PageCopyUpdate,
    read_schema=PageCopyAdminRead,
    prefix="/page-copy",
    tag="admin-site-config",
    config_resource_key="site.pages",
    capture_before=lambda session: capture_config_resource(session, "site.pages"),
)

display_options_router = build_crud_router(
    PageDisplayOption,
    create_schema=PageDisplayOptionCreate,
    update_schema=PageDisplayOptionUpdate,
    read_schema=PageDisplayOptionAdminRead,
    prefix="/display-options",
    tag="admin-site-config",
    config_resource_key="site.pages",
    capture_before=lambda session: capture_config_resource(session, "site.pages"),
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
    before_snapshot = capture_config_resource(session, "site.navigation")
    result = reorder_nav_items_admin(session, items)
    after_snapshot = capture_config_resource(session, "site.navigation")
    create_config_revision(
        session,
        actor_id=_admin.id,
        resource_key="site.navigation",
        operation="update",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    return result


nav_items_router = build_crud_router(
    NavItem,
    create_schema=NavItemCreate,
    update_schema=NavItemUpdate,
    read_schema=NavItemAdminRead,
    prefix="/nav-items",
    tag="admin-site-config",
    base_query_factory=lambda session: site_profile_scoped_query(session, NavItem),
    prepare_create_data=attach_site_profile_id,
    config_resource_key="site.navigation",
    capture_before=lambda session: capture_config_resource(session, "site.navigation"),
)

router.include_router(nav_items_router)
