from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.subscription.schemas import ContentSubscriptionPublicCreate, ContentSubscriptionPublicRead
from aerisun.domain.subscription.service import create_or_update_public_subscription

router = APIRouter(prefix="/api/v1/site/subscriptions", tags=["site"])


@router.post("/", response_model=ContentSubscriptionPublicRead, status_code=status.HTTP_201_CREATED)
def subscribe_to_content(
    payload: ContentSubscriptionPublicCreate,
    session: Session = Depends(get_session),
) -> ContentSubscriptionPublicRead:
    return create_or_update_public_subscription(session, payload)
