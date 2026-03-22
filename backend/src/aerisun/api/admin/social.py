from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.models import AdminUser, Friend, FriendFeedSource

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


# --- FriendFeedSource as sub-resource of friends ---

@router.get("/friends/{friend_id}/feeds", response_model=list[FriendFeedSourceAdminRead])
def list_friend_feeds(
    friend_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
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
)
def create_friend_feed(
    friend_id: str,
    payload: FriendFeedSourceCreate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
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


@router.put("/feeds/{feed_id}", response_model=FriendFeedSourceAdminRead)
def update_friend_feed(
    feed_id: str,
    payload: FriendFeedSourceUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    obj = session.get(FriendFeedSource, feed_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Feed source not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    session.commit()
    session.refresh(obj)
    return FriendFeedSourceAdminRead.model_validate(obj)


@router.delete("/feeds/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_friend_feed(
    feed_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    obj = session.get(FriendFeedSource, feed_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Feed source not found")
    session.delete(obj)
    session.commit()
