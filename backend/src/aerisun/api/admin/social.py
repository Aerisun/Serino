from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session, selectinload

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.social.models import Friend
from aerisun.domain.social.service import (
    check_friend_now,
    create_friend_feed_admin,
    delete_friend_feed_admin,
    list_friend_feeds_admin,
    trigger_single_crawl,
    update_friend_feed_admin,
)

from .content import build_crud_router
from .deps import get_current_admin
from .schemas import (
    FeedCrawlAllResultRead,
    FeedCrawlResultRead,
    FriendAdminRead,
    FriendCreate,
    FriendFeedSourceAdminRead,
    FriendFeedSourceCreate,
    FriendFeedSourceUpdate,
    FriendUpdate,
)

router = APIRouter(prefix="/social", tags=["admin-social"])

friends_router = build_crud_router(
    Friend,
    create_schema=FriendCreate,
    update_schema=FriendUpdate,
    read_schema=FriendAdminRead,
    prefix="/friends",
    tag="admin-social",
    base_query_factory=lambda session: session.query(Friend).options(selectinload(Friend.feed_sources)),
)

router.include_router(friends_router)


@router.post("/friends/{friend_id}/check", summary="立即检查友链网站与 RSS")
def check_friend_health(
    friend_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return check_friend_now(session, friend_id)


@router.post("/feeds/crawl", response_model=FeedCrawlAllResultRead, summary="手动触发全量抓取")
def trigger_feed_crawl(
    _admin: AdminUser = Depends(get_current_admin),
) -> Any:
    from aerisun.domain.social.crawler import crawl_all_feeds

    return crawl_all_feeds()


@router.post("/feeds/{feed_id}/crawl", response_model=FeedCrawlResultRead, summary="手动触发单源抓取")
def trigger_single_feed_crawl(
    feed_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return trigger_single_crawl(session, feed_id)


@router.get("/friends/{friend_id}/feeds", response_model=list[FriendFeedSourceAdminRead], summary="获取友链订阅源")
def list_friend_feeds(
    friend_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return list_friend_feeds_admin(session, friend_id)


@router.post(
    "/friends/{friend_id}/feeds",
    response_model=FriendFeedSourceAdminRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建订阅源",
)
def create_friend_feed(
    friend_id: str,
    payload: FriendFeedSourceCreate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return create_friend_feed_admin(session, friend_id, payload)


@router.put("/feeds/{feed_id}", response_model=FriendFeedSourceAdminRead, summary="更新订阅源")
def update_friend_feed(
    feed_id: str,
    payload: FriendFeedSourceUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return update_friend_feed_admin(session, feed_id, payload)


@router.delete("/feeds/{feed_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除订阅源")
def delete_friend_feed(
    feed_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    delete_friend_feed_admin(session, feed_id)
