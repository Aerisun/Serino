from __future__ import annotations

from fastapi import APIRouter, Depends, status

from aerisun.domain.iam.models import AdminUser
from aerisun.domain.service_forwards.schemas import ServiceForwardRead, ServiceForwardWrite
from aerisun.domain.service_forwards.service import (
    create_service_forward,
    delete_service_forward,
    list_service_forwards,
    test_service_forward,
    update_service_forward,
)

from .deps import get_current_admin

router = APIRouter(prefix="/service-forwards", tags=["admin-service-forwards"])


@router.get("", response_model=list[ServiceForwardRead], summary="获取服务转发列表")
def list_service_forwards_endpoint(
    _admin: AdminUser = Depends(get_current_admin),
) -> list[ServiceForwardRead]:
    return list_service_forwards()


@router.post("", response_model=ServiceForwardRead, status_code=status.HTTP_201_CREATED, summary="新增服务转发")
def create_service_forward_endpoint(
    payload: ServiceForwardWrite,
    _admin: AdminUser = Depends(get_current_admin),
) -> ServiceForwardRead:
    return create_service_forward(payload)


@router.put("/{route_id}", response_model=ServiceForwardRead, summary="更新服务转发")
def update_service_forward_endpoint(
    route_id: str,
    payload: ServiceForwardWrite,
    _admin: AdminUser = Depends(get_current_admin),
) -> ServiceForwardRead:
    return update_service_forward(route_id, payload)


@router.post("/{route_id}/test", response_model=ServiceForwardRead, summary="检测服务转发目标")
def test_service_forward_endpoint(
    route_id: str,
    _admin: AdminUser = Depends(get_current_admin),
) -> ServiceForwardRead:
    return test_service_forward(route_id)


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除服务转发")
def delete_service_forward_endpoint(
    route_id: str,
    _admin: AdminUser = Depends(get_current_admin),
) -> None:
    delete_service_forward(route_id)
