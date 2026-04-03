from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from aerisun.domain.media.models import Asset, AssetMirrorQueueItem, AssetRemoteDeleteQueueItem, ObjectStorageConfig


def find_assets_paginated(
    session: Session,
    *,
    page: int,
    page_size: int,
    q: str | None = None,
    scope: str | None = None,
) -> tuple[list[Asset], int]:
    """Paginated query for assets. Returns (items, total)."""
    query = session.query(Asset)
    if scope and scope.strip():
        query = query.filter(Asset.scope == scope.strip())
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Asset.file_name.ilike(pattern),
                Asset.resource_key.ilike(pattern),
                Asset.category.ilike(pattern),
                Asset.visibility.ilike(pattern),
                Asset.note.ilike(pattern),
            )
        )

    total = query.order_by(None).with_entities(func.count(Asset.id)).scalar() or 0
    items = list(query.order_by(Asset.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all())
    return items, total


def create_asset(session: Session, **kwargs) -> Asset:
    """Create a new Asset record. Caller must commit."""
    asset = Asset(**kwargs)
    session.add(asset)
    return asset


def find_asset_by_id(session: Session, asset_id: str) -> Asset | None:
    """Find asset by primary key."""
    return session.get(Asset, asset_id)


def find_asset_by_resource_key(session: Session, resource_key: str) -> Asset | None:
    """Find asset by normalized resource key."""
    return session.query(Asset).filter(Asset.resource_key == resource_key).first()


def update_asset(session: Session, asset: Asset, **kwargs) -> Asset:
    """Update an asset record. Caller must commit."""
    for key, value in kwargs.items():
        setattr(asset, key, value)
    return asset


def delete_asset(session: Session, asset: Asset) -> None:
    """Delete an asset record. Caller must commit."""
    session.delete(asset)


def delete_assets_by_ids(session: Session, ids: list[str]) -> int:
    """Bulk delete assets by ID list. Caller must commit. Returns affected count."""
    affected = session.query(Asset).filter(Asset.id.in_(ids)).delete(synchronize_session="fetch")
    return affected


def get_object_storage_config(session: Session) -> ObjectStorageConfig | None:
    return session.query(ObjectStorageConfig).order_by(ObjectStorageConfig.created_at.asc()).first()


def create_object_storage_config(session: Session, **kwargs) -> ObjectStorageConfig:
    config = ObjectStorageConfig(**kwargs)
    session.add(config)
    return config


def find_active_mirror_queue_item_for_asset(session: Session, asset_id: str) -> AssetMirrorQueueItem | None:
    return (
        session.query(AssetMirrorQueueItem)
        .filter(
            AssetMirrorQueueItem.asset_id == asset_id,
            AssetMirrorQueueItem.status.in_(("queued", "running", "retrying")),
        )
        .order_by(AssetMirrorQueueItem.created_at.desc())
        .first()
    )


def create_mirror_queue_item(session: Session, **kwargs) -> AssetMirrorQueueItem:
    item = AssetMirrorQueueItem(**kwargs)
    session.add(item)
    return item


def find_running_mirror_queue_item(session: Session) -> AssetMirrorQueueItem | None:
    return (
        session.query(AssetMirrorQueueItem)
        .filter(AssetMirrorQueueItem.status == "running")
        .order_by(AssetMirrorQueueItem.started_at.asc(), AssetMirrorQueueItem.created_at.asc())
        .first()
    )


def find_due_mirror_queue_item(session: Session, *, now: datetime) -> AssetMirrorQueueItem | None:
    return (
        session.query(AssetMirrorQueueItem)
        .filter(
            AssetMirrorQueueItem.status.in_(("queued", "retrying")),
            AssetMirrorQueueItem.next_retry_at <= now,
        )
        .order_by(AssetMirrorQueueItem.next_retry_at.asc(), AssetMirrorQueueItem.created_at.asc())
        .first()
    )


def get_mirror_queue_item(session: Session, queue_item_id: str) -> AssetMirrorQueueItem | None:
    return session.get(AssetMirrorQueueItem, queue_item_id)


def find_active_remote_delete_queue_item(session: Session, object_key: str) -> AssetRemoteDeleteQueueItem | None:
    return (
        session.query(AssetRemoteDeleteQueueItem)
        .filter(
            AssetRemoteDeleteQueueItem.object_key == object_key,
            AssetRemoteDeleteQueueItem.status.in_(("queued", "running", "retrying")),
        )
        .order_by(AssetRemoteDeleteQueueItem.created_at.desc())
        .first()
    )


def create_remote_delete_queue_item(session: Session, **kwargs) -> AssetRemoteDeleteQueueItem:
    item = AssetRemoteDeleteQueueItem(**kwargs)
    session.add(item)
    return item


def find_running_remote_delete_queue_item(session: Session) -> AssetRemoteDeleteQueueItem | None:
    return (
        session.query(AssetRemoteDeleteQueueItem)
        .filter(AssetRemoteDeleteQueueItem.status == "running")
        .order_by(AssetRemoteDeleteQueueItem.started_at.asc(), AssetRemoteDeleteQueueItem.created_at.asc())
        .first()
    )


def find_due_remote_delete_queue_item(session: Session, *, now: datetime) -> AssetRemoteDeleteQueueItem | None:
    return (
        session.query(AssetRemoteDeleteQueueItem)
        .filter(
            AssetRemoteDeleteQueueItem.status.in_(("queued", "retrying")),
            AssetRemoteDeleteQueueItem.next_retry_at <= now,
        )
        .order_by(AssetRemoteDeleteQueueItem.next_retry_at.asc(), AssetRemoteDeleteQueueItem.created_at.asc())
        .first()
    )


def get_remote_delete_queue_item(session: Session, queue_item_id: str) -> AssetRemoteDeleteQueueItem | None:
    return session.get(AssetRemoteDeleteQueueItem, queue_item_id)
