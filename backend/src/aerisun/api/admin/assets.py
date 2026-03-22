from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.media.models import Asset
from aerisun.core.settings import get_settings

from .deps import get_current_admin
from .schemas import AssetAdminRead

router = APIRouter(prefix="/assets", tags=["admin-assets"])


@router.get("/", response_model=dict)
def list_assets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    q = session.query(Asset)
    total = q.count()
    items = (
        q.order_by(Asset.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [AssetAdminRead.model_validate(a) for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/", response_model=AssetAdminRead, status_code=status.HTTP_201_CREATED)
def upload_asset(
    file: UploadFile,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    settings = get_settings()
    media_dir = settings.media_dir.expanduser().resolve()
    media_dir.mkdir(parents=True, exist_ok=True)

    content = file.file.read()
    sha = hashlib.sha256(content).hexdigest()
    file_name = file.filename or "upload"
    storage_path = str(media_dir / f"{sha[:12]}_{file_name}")

    with open(storage_path, "wb") as f:
        f.write(content)

    asset = Asset(
        file_name=file_name,
        storage_path=storage_path,
        mime_type=file.content_type,
        byte_size=len(content),
        sha256=sha,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return AssetAdminRead.model_validate(asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    # Attempt to remove file from disk
    from pathlib import Path

    path = Path(asset.storage_path)
    if path.exists():
        path.unlink()
    session.delete(asset)
    session.commit()
