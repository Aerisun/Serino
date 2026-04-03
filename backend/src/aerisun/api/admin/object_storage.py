from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.media.object_storage import (
    get_object_storage_config_read,
    test_object_storage_config,
    update_object_storage_config,
)
from aerisun.domain.media.schemas import (
    ObjectStorageConfigRead,
    ObjectStorageConfigUpdate,
    ObjectStorageHealthRead,
)
from aerisun.domain.ops.config_revisions import capture_config_resource, create_config_revision

from .deps import get_current_admin

router = APIRouter(prefix="/object-storage/config", tags=["admin-object-storage"])


@router.get("", response_model=ObjectStorageConfigRead, summary="获取 OSS 加速配置")
def get_object_storage_config(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ObjectStorageConfigRead:
    return get_object_storage_config_read(session)


@router.put("", response_model=ObjectStorageConfigRead, summary="更新 OSS 加速配置")
def put_object_storage_config(
    payload: ObjectStorageConfigUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ObjectStorageConfigRead:
    before_snapshot = capture_config_resource(session, "integrations.object_storage")
    result = update_object_storage_config(session, payload)
    after_snapshot = capture_config_resource(session, "integrations.object_storage")
    create_config_revision(
        session,
        actor_id=admin.id,
        resource_key="integrations.object_storage",
        operation="update",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    return result


@router.post("/test", response_model=ObjectStorageHealthRead, summary="测试 OSS 加速配置")
def post_object_storage_config_test(
    payload: ObjectStorageConfigUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ObjectStorageHealthRead:
    return test_object_storage_config(session, payload)
