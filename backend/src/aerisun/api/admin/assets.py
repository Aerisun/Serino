from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.core.settings import get_settings
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.media.models import Asset

from .deps import get_current_admin
from .schemas import AssetAdminRead, BulkActionResponse, BulkDeleteRequest, PaginatedResponse

router = APIRouter(prefix="/assets", tags=["admin-assets"])


@router.get("/", response_model=PaginatedResponse[AssetAdminRead], summary="获取资源列表")
def list_assets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """分页查询已上传的媒体资源。"""
    q = session.query(Asset)
    total = q.count()
    items = q.order_by(Asset.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [AssetAdminRead.model_validate(a) for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "/",
    response_model=AssetAdminRead,
    status_code=status.HTTP_201_CREATED,
    summary="上传资源",
)
def upload_asset(
    file: UploadFile,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """接收文件并保存到媒体目录，返回资源元信息。"""
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


@router.post("/bulk-delete", response_model=BulkActionResponse, summary="批量删除资源")
def bulk_delete_assets(
    payload: BulkDeleteRequest,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """根据 ID 列表批量删除媒体资源。"""
    affected = session.query(Asset).filter(Asset.id.in_(payload.ids)).delete(synchronize_session="fetch")
    session.commit()
    return {"affected": affected}


@router.get("/{asset_id}", response_model=AssetAdminRead, summary="获取单个资源")
def get_asset(
    asset_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    """根据 ID 获取单个媒体资源的详细信息。"""
    obj = session.get(Asset, asset_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return AssetAdminRead.model_validate(obj)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除资源")
def delete_asset(
    asset_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    """删除指定资源并移除对应的磁盘文件。"""
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
