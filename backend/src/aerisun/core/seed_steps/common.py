from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def is_empty(session: Session, model) -> bool:  # type: ignore[no-untyped-def]
    return session.scalar(select(func.count(model.id))) == 0
