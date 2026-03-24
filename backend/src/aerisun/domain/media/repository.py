from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aerisun.domain.media.models import Asset


def find_assets_paginated(session: Session, *, page: int, page_size: int) -> tuple[list[Asset], int]:
    """Paginated query for assets. Returns (items, total)."""
    total = session.scalar(select(func.count(Asset.id))) or 0
    items = list(
        session.query(Asset).order_by(Asset.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    return items, total


def create_asset(session: Session, **kwargs) -> Asset:
    """Create a new Asset record. Caller must commit."""
    asset = Asset(**kwargs)
    session.add(asset)
    return asset


def find_asset_by_id(session: Session, asset_id: str) -> Asset | None:
    """Find asset by primary key."""
    return session.get(Asset, asset_id)


def delete_asset(session: Session, asset: Asset) -> None:
    """Delete an asset record. Caller must commit."""
    session.delete(asset)


def delete_assets_by_ids(session: Session, ids: list[str]) -> int:
    """Bulk delete assets by ID list. Caller must commit. Returns affected count."""
    affected = session.query(Asset).filter(Asset.id.in_(ids)).delete(synchronize_session="fetch")
    return affected
