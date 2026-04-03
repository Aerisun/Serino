from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.media.schemas import (
    AssetAdminRead,
    AssetAdminUpdate,
    AssetUploadCompleteWrite,
    AssetUploadPlanRead,
    AssetUploadPlanWrite,
)
from aerisun.domain.media.service import (
    bulk_delete_assets,
    complete_asset_upload,
    delete_asset,
    get_asset,
    list_assets,
    prepare_asset_upload,
    update_asset,
    upload_asset,
)

from .deps import get_current_admin
from .schemas import BulkActionResponse, BulkDeleteRequest, PaginatedResponse

router = APIRouter(prefix="/assets", tags=["admin-assets"])


@router.get("/", response_model=PaginatedResponse[AssetAdminRead], summary="获取资源列表")
def list_assets_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, max_length=200),
    scope: str = Query(default="user", pattern="^(system|user)$"),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return list_assets(session, page=page, page_size=page_size, q=q, scope=scope)


@router.post("/", response_model=AssetAdminRead, status_code=status.HTTP_201_CREATED, summary="上传资源")
def upload_asset_endpoint(
    file: Annotated[UploadFile, File(...)],
    visibility: Annotated[str, Form()] = "internal",
    scope: Annotated[str, Form()] = "user",
    category: Annotated[str, Form()] = "general",
    note: Annotated[str | None, Form()] = None,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    content = file.file.read()
    return upload_asset(
        session,
        file.filename or "upload",
        content,
        file.content_type,
        visibility=visibility,
        scope=scope,
        category=category,
        note=note,
    )


@router.post("/init-upload", response_model=AssetUploadPlanRead, summary="初始化资源上传")
def init_upload_asset_endpoint(
    payload: AssetUploadPlanWrite,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return prepare_asset_upload(session, payload)


@router.post("/complete-upload", response_model=AssetAdminRead, summary="完成资源上传")
def complete_upload_asset_endpoint(
    payload: AssetUploadCompleteWrite,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return complete_asset_upload(session, payload)


@router.post("/bulk-delete", response_model=BulkActionResponse, summary="批量删除资源")
def bulk_delete_assets_endpoint(
    payload: BulkDeleteRequest,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return {"affected": bulk_delete_assets(session, payload.ids)}


@router.get("/{asset_id}", response_model=AssetAdminRead, summary="获取单个资源")
def get_asset_endpoint(
    asset_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return get_asset(session, asset_id)


@router.patch("/{asset_id}", response_model=AssetAdminRead, summary="更新资源")
def update_asset_endpoint(
    asset_id: str,
    payload: AssetAdminUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Any:
    return update_asset(session, asset_id, payload)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除资源")
def delete_asset_endpoint(
    asset_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    delete_asset(session, asset_id)
