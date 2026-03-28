from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.subscription.schemas import (
    ContentSubscriptionConfigAdminRead,
    ContentSubscriptionConfigAdminUpdate,
    ContentSubscriptionTestResult,
)
from aerisun.domain.subscription.service import (
    get_subscription_admin_config,
    send_subscription_test_email,
    update_subscription_admin_config,
)

from .deps import get_current_admin

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
    return update_subscription_admin_config(session, payload)


@router.post("/config/test", response_model=ContentSubscriptionTestResult, summary="测试内容订阅 SMTP 发信")
def test_content_subscription_config(
    payload: ContentSubscriptionConfigAdminUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ContentSubscriptionTestResult:
    return send_subscription_test_email(session, payload)
