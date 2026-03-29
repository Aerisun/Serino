from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.ops.config_revisions import capture_config_resource, create_config_revision
from aerisun.domain.subscription.schemas import (
    ContentNotificationDeliveryAdminRead,
    ContentSubscriberAdminRead,
    ContentSubscriptionConfigAdminRead,
    ContentSubscriptionConfigAdminUpdate,
    ContentSubscriptionTestResult,
)
from aerisun.domain.subscription.service import (
    get_subscription_admin_config,
    list_admin_subscribers,
    list_subscriber_delivery_history,
    send_subscription_test_email,
    update_subscription_admin_config,
)

from .deps import get_current_admin
from .schemas import PaginatedResponse, build_paginated_response

router = APIRouter(prefix="/subscriptions", tags=["admin-site-config"])


@router.get("/config", response_model=ContentSubscriptionConfigAdminRead, summary="获取内容订阅配置")
def get_content_subscription_config(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ContentSubscriptionConfigAdminRead:
    return get_subscription_admin_config(session)


@router.put("/config", response_model=ContentSubscriptionConfigAdminRead, summary="更新内容订阅配置")
def update_content_subscription_config(
    payload: ContentSubscriptionConfigAdminUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ContentSubscriptionConfigAdminRead:
    before_snapshot = capture_config_resource(session, "subscriptions.config")
    result = update_subscription_admin_config(session, payload)
    after_snapshot = capture_config_resource(session, "subscriptions.config")
    create_config_revision(
        session,
        actor_id=_admin.id,
        resource_key="subscriptions.config",
        operation="update",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    return result


@router.post("/config/test", response_model=ContentSubscriptionTestResult, summary="测试内容订阅 SMTP 发信")
def test_content_subscription_config(
    payload: ContentSubscriptionConfigAdminUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ContentSubscriptionTestResult:
    return send_subscription_test_email(session, payload)


@router.get(
    "/subscribers",
    response_model=PaginatedResponse[ContentSubscriberAdminRead],
    summary="获取内容订阅者列表",
)
def list_content_subscribers(
    mode: Literal["all", "email", "binding", "subscriber"] = Query(default="all"),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    items, total = list_admin_subscribers(
        session,
        mode=mode,
        search=search,
        page=page,
        page_size=page_size,
    )
    return build_paginated_response(items, total=total, page=page, page_size=page_size)


@router.get(
    "/subscribers/{email}/messages",
    response_model=PaginatedResponse[ContentNotificationDeliveryAdminRead],
    summary="获取订阅者发送记录",
)
def list_content_subscriber_messages(
    email: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    items, total = list_subscriber_delivery_history(
        session,
        email=email,
        page=page,
        page_size=page_size,
    )
    return build_paginated_response(items, total=total, page=page, page_size=page_size)
