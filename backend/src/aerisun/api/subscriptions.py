from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from aerisun.api.deps.site_auth import get_current_site_user, get_current_site_user_optional
from aerisun.core.db import get_session
from aerisun.domain.site_auth.models import SiteUser
from aerisun.domain.subscription.schemas import (
    ContentSubscriptionPublicCreate,
    ContentSubscriptionPublicEmailRequest,
    ContentSubscriptionPublicRead,
    ContentSubscriptionPublicStatusRead,
    ContentSubscriptionPublicUnsubscribeResult,
)
from aerisun.domain.subscription.service import (
    create_or_update_public_subscription,
    get_public_subscription_for_email,
    unsubscribe_public_subscription,
)

router = APIRouter(prefix="/api/v1/site/subscriptions", tags=["site"])


@router.post("/", response_model=ContentSubscriptionPublicRead, status_code=status.HTTP_201_CREATED)
def subscribe_to_content(
    payload: ContentSubscriptionPublicCreate,
    current_user: SiteUser | None = Depends(get_current_site_user_optional),
    session: Session = Depends(get_session),
) -> ContentSubscriptionPublicRead:
    return create_or_update_public_subscription(session, payload, current_user=current_user)


@router.post("/status", response_model=ContentSubscriptionPublicStatusRead, summary="按邮箱读取订阅状态")
def get_subscription_status_by_email(
    payload: ContentSubscriptionPublicEmailRequest,
    session: Session = Depends(get_session),
) -> ContentSubscriptionPublicStatusRead:
    return get_public_subscription_for_email(
        session,
        email=payload.email,
    )


@router.post("/unsubscribe", response_model=ContentSubscriptionPublicUnsubscribeResult, summary="按邮箱取消订阅")
def unsubscribe_subscription_by_email(
    payload: ContentSubscriptionPublicEmailRequest,
    session: Session = Depends(get_session),
) -> ContentSubscriptionPublicUnsubscribeResult:
    return unsubscribe_public_subscription(
        session,
        email=payload.email,
    )


@router.get("/me", response_model=ContentSubscriptionPublicStatusRead, summary="读取当前登录用户订阅状态")
def get_my_subscription_status(
    current_user: SiteUser = Depends(get_current_site_user),
    session: Session = Depends(get_session),
) -> ContentSubscriptionPublicStatusRead:
    return get_public_subscription_for_email(
        session,
        email=current_user.email,
    )


@router.delete("/me", response_model=ContentSubscriptionPublicUnsubscribeResult, summary="取消当前登录用户订阅")
def unsubscribe_my_subscription(
    current_user: SiteUser = Depends(get_current_site_user),
    session: Session = Depends(get_session),
) -> ContentSubscriptionPublicUnsubscribeResult:
    return unsubscribe_public_subscription(
        session,
        email=current_user.email,
    )
