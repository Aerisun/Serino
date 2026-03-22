from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.social.models import Friend, FriendFeedSource

from .content import build_crud_router
from .deps import get_current_admin
from .schemas import (
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
)

router.include_router(friends_router)


# --- Feed crawl triggers ---


@router.post("/feeds/crawl", summary="手动触发全量抓取")
def trigger_feed_crawl(
    _admin: AdminUser = Depends(get_current_admin),
) -> Any:
    """手动触发所有已启用订阅源的抓取任务。"""
    from aerisun.domain.social.crawler import crawl_all_feeds

    return crawl_all_feeds()


@router.post("/feeds/{feed_id}/crawl", summary="手动触发单源抓取")
def trigger_single_feed_crawl(
    feed_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """手动触发指定订阅源的抓取任务。"""
    from aerisun.core.settings import get_settings
    from aerisun.domain.social.crawler import crawl_single_source

    source = session.get(FriendFeedSource, feed_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Feed source not found")
    friend = session.get(Friend, source.friend_id)
    if friend is None:
        raise HTTPException(status_code=404, detail="Friend not found")

    result = crawl_single_source(session, source, friend, get_settings())
    session.commit()
    return result


# --- FriendFeedSource as sub-resource of friends ---


@router.get(
    "/friends/{friend_id}/feeds", response_model=list[FriendFeedSourceAdminRead],
    summary="获取友链订阅源",
)
def list_friend_feeds(
    friend_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """列出指定友链关联的所有订阅源。"""
    friend = session.get(Friend, friend_id)
    if friend is None:
        raise HTTPException(status_code=404, detail="Friend not found")
    sources = (
        session.query(FriendFeedSource)
        .filter(FriendFeedSource.friend_id == friend_id)
        .all()
    )
    return [FriendFeedSourceAdminRead.model_validate(s) for s in sources]


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
    """为指定友链添加一个新的订阅源。"""
    friend = session.get(Friend, friend_id)
    if friend is None:
        raise HTTPException(status_code=404, detail="Friend not found")
    data = payload.model_dump()
    data["friend_id"] = friend_id
    obj = FriendFeedSource(**data)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return FriendFeedSourceAdminRead.model_validate(obj)


@router.put("/feeds/{feed_id}", response_model=FriendFeedSourceAdminRead, summary="更新订阅源")
def update_friend_feed(
    feed_id: str,
    payload: FriendFeedSourceUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """更新指定订阅源的配置信息。"""
    obj = session.get(FriendFeedSource, feed_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Feed source not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    session.commit()
    session.refresh(obj)
    return FriendFeedSourceAdminRead.model_validate(obj)


@router.delete("/feeds/{feed_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除订阅源")
def delete_friend_feed(
    feed_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    """删除指定的订阅源记录。"""
    obj = session.get(FriendFeedSource, feed_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Feed source not found")
    session.delete(obj)
    session.commit()
