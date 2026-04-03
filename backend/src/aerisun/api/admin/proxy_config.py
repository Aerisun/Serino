from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.ops.config_revisions import capture_config_resource, create_config_revision
from aerisun.domain.outbound_proxy.schemas import (
    OutboundProxyConfigRead,
    OutboundProxyConfigUpdate,
    OutboundProxyHealthRead,
)
from aerisun.domain.outbound_proxy.service import (
    get_outbound_proxy_config,
    test_outbound_proxy_config,
    update_outbound_proxy_config,
)

from .deps import get_current_admin

router = APIRouter(prefix="/proxy-config", tags=["admin-network"])


@router.get("", response_model=OutboundProxyConfigRead, summary="获取出站代理配置")
def get_proxy_config(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> OutboundProxyConfigRead:
    return get_outbound_proxy_config(session)


@router.put("", response_model=OutboundProxyConfigRead, summary="更新出站代理配置")
def put_proxy_config(
    payload: OutboundProxyConfigUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> OutboundProxyConfigRead:
    before_snapshot = capture_config_resource(session, "network.outbound_proxy")
    result = update_outbound_proxy_config(session, payload)
    after_snapshot = capture_config_resource(session, "network.outbound_proxy")
    create_config_revision(
        session,
        actor_id=admin.id,
        resource_key="network.outbound_proxy",
        operation="update",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    return result


@router.post("/test", response_model=OutboundProxyHealthRead, summary="测试出站代理端口")
def post_proxy_config_test(
    payload: OutboundProxyConfigUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> OutboundProxyHealthRead:
    return test_outbound_proxy_config(session, payload)
