from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from aerisun.db import get_session
from aerisun.models import AdminUser, Comment, GuestbookEntry, ModerationRecord

from .deps import get_current_admin
from .schemas import CommentAdminRead, GuestbookAdminRead, ModerateAction

router = APIRouter(prefix="/moderation", tags=["admin-moderation"])


@router.get("/comments", response_model=dict)
def list_comments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    q = session.query(Comment)
    if status_filter:
        q = q.filter(Comment.status == status_filter)
    total = q.count()
    items = (
        q.order_by(Comment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [CommentAdminRead.model_validate(c) for c in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/comments/{comment_id}/moderate", response_model=CommentAdminRead)
def moderate_comment(
    comment_id: str,
    payload: ModerateAction,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    comment = session.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    if payload.action == "delete":
        record = ModerationRecord(
            target_type="comment",
            target_id=comment_id,
            action="delete",
            reason=payload.reason,
        )
        session.add(record)
        session.delete(comment)
        session.commit()
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)

    if payload.action in ("approve", "reject"):
        comment.status = "approved" if payload.action == "approve" else "rejected"
        record = ModerationRecord(
            target_type="comment",
            target_id=comment_id,
            action=payload.action,
            reason=payload.reason,
        )
        session.add(record)
        session.commit()
        session.refresh(comment)
        return CommentAdminRead.model_validate(comment)

    raise HTTPException(status_code=400, detail="Invalid action")


@router.get("/guestbook", response_model=dict)
def list_guestbook(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    q = session.query(GuestbookEntry)
    if status_filter:
        q = q.filter(GuestbookEntry.status == status_filter)
    total = q.count()
    items = (
        q.order_by(GuestbookEntry.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [GuestbookAdminRead.model_validate(g) for g in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/guestbook/{entry_id}/moderate", response_model=GuestbookAdminRead)
def moderate_guestbook(
    entry_id: str,
    payload: ModerateAction,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    entry = session.get(GuestbookEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Guestbook entry not found")

    if payload.action == "delete":
        record = ModerationRecord(
            target_type="guestbook",
            target_id=entry_id,
            action="delete",
            reason=payload.reason,
        )
        session.add(record)
        session.delete(entry)
        session.commit()
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)

    if payload.action in ("approve", "reject"):
        entry.status = "approved" if payload.action == "approve" else "rejected"
        record = ModerationRecord(
            target_type="guestbook",
            target_id=entry_id,
            action=payload.action,
            reason=payload.reason,
        )
        session.add(record)
        session.commit()
        session.refresh(entry)
        return GuestbookAdminRead.model_validate(entry)

    raise HTTPException(status_code=400, detail="Invalid action")
