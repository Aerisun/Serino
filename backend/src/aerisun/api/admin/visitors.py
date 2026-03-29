from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from aerisun.api.deps.site_auth import get_current_site_user
from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.ops.config_revisions import capture_config_resource, create_config_revision
from aerisun.domain.site_auth.models import SiteUser
from aerisun.domain.site_auth.schemas import (
    SiteAdminEmailIdentityBindRequest,
    SiteAdminIdentityAdminRead,
    SiteAuthConfigAdminRead,
    SiteAuthConfigAdminUpdate,
    SiteUserAdminRead,
)
from aerisun.domain.site_auth.service import (
    bind_site_admin_identity_by_email,
    bind_site_admin_identity_from_current_user,
    delete_site_admin_identity,
    get_site_auth_admin_config,
    list_site_admin_identities_admin,
    list_site_users_admin,
    update_site_auth_admin_config,
)

from .deps import get_current_admin
from .schemas import PaginatedResponse, build_paginated_response

router = APIRouter(prefix="/visitors", tags=["admin-visitors"])


@router.get("/config", response_model=SiteAuthConfigAdminRead, summary="获取访客认证配置")
def get_visitor_auth_config(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> SiteAuthConfigAdminRead:
    return get_site_auth_admin_config(session)


@router.put("/config", response_model=SiteAuthConfigAdminRead, summary="更新访客认证配置")
def update_visitor_auth_config(
    payload: SiteAuthConfigAdminUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> SiteAuthConfigAdminRead:
    before_snapshot = capture_config_resource(session, "visitors.auth")
    result = update_site_auth_admin_config(session, payload)
    after_snapshot = capture_config_resource(session, "visitors.auth")
    create_config_revision(
        session,
        actor_id=_admin.id,
        resource_key="visitors.auth",
        operation="update",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    return result


@router.get("/users", response_model=PaginatedResponse[SiteUserAdminRead], summary="获取站点访客用户列表")
def list_visitor_users(
    mode: Literal["all", "email", "binding"] = Query(default="all"),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    items, total = list_site_users_admin(
        session,
        auth_mode=mode,
        search=search,
        page=page,
        page_size=page_size,
    )
    return build_paginated_response(items, total=total, page=page, page_size=page_size)


@router.get("/admin-identities", response_model=list[SiteAdminIdentityAdminRead], summary="获取管理员前台身份绑定")
def list_admin_identities(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[SiteAdminIdentityAdminRead]:
    return list_site_admin_identities_admin(session)


@router.post(
    "/admin-identities/email",
    response_model=SiteAdminIdentityAdminRead,
    summary="通过邮箱绑定管理员前台身份",
)
def bind_admin_identity_email(
    payload: SiteAdminEmailIdentityBindRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> SiteAdminIdentityAdminRead:
    return bind_site_admin_identity_by_email(session, payload, admin_user_id=admin.id)


@router.post(
    "/admin-identities/bind-current",
    response_model=SiteAdminIdentityAdminRead,
    summary="绑定当前前台登录身份为管理员",
)
def bind_current_admin_identity(
    provider: Literal["email", "google", "github"] = Query(...),
    admin: AdminUser = Depends(get_current_admin),
    current_site_user: SiteUser = Depends(get_current_site_user),
    session: Session = Depends(get_session),
) -> SiteAdminIdentityAdminRead:
    return bind_site_admin_identity_from_current_user(
        session,
        current_site_user,
        provider=provider,
        admin_user_id=admin.id,
    )


@router.delete("/admin-identities/{identity_id}", status_code=204, summary="删除管理员前台身份绑定")
def delete_admin_identity_endpoint(
    identity_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    delete_site_admin_identity(session, identity_id)
