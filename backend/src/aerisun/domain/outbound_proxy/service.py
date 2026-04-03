from __future__ import annotations

import socket
import threading
import time
from typing import Any, Literal

import httpx
from sqlalchemy.orm import Session

from aerisun.domain.exceptions import ResourceNotFound, ValidationError
from aerisun.domain.site_config import repository as site_repo

from .schemas import OutboundProxyConfigRead, OutboundProxyConfigUpdate, OutboundProxyHealthRead

OUTBOUND_PROXY_FLAG_KEY = "outbound_proxy_config"
OUTBOUND_PROXY_HOST = "127.0.0.1"
OUTBOUND_PROXY_HEALTHCHECK_URL = "https://example.com/"
OutboundProxyScope = Literal["webhook"]

_DEFAULT_OUTBOUND_PROXY_CONFIG: dict[str, Any] = {
    "proxy_port": None,
    "webhook_enabled": False,
}
_feature_flags_lock = threading.Lock()


def _get_site_profile(session: Session):
    profile = site_repo.find_site_profile(session)
    if profile is None:
        raise ResourceNotFound("Site profile not configured")
    return profile


def _normalize_outbound_proxy_config(raw: Any) -> OutboundProxyConfigRead:
    data = dict(_DEFAULT_OUTBOUND_PROXY_CONFIG)
    if isinstance(raw, dict):
        if "proxy_port" in raw:
            data["proxy_port"] = raw.get("proxy_port")
        if "webhook_enabled" in raw:
            data["webhook_enabled"] = bool(raw.get("webhook_enabled"))
        else:
            targets = raw.get("targets")
            if isinstance(targets, dict):
                data["webhook_enabled"] = bool(targets.get("webhook", False))
    return OutboundProxyConfigRead.model_validate(data)


def _serialize_outbound_proxy_config(config: OutboundProxyConfigRead) -> dict[str, Any]:
    return config.model_dump()


def _resolve_outbound_proxy_config(
    session: Session,
    payload: OutboundProxyConfigUpdate | None = None,
) -> OutboundProxyConfigRead:
    current = get_outbound_proxy_config(session)
    next_data = current.model_dump()
    if payload is not None:
        next_data.update(payload.model_dump(exclude_unset=True))
    config = OutboundProxyConfigRead.model_validate(next_data)
    if config.webhook_enabled and config.proxy_port is None:
        raise ValidationError("开启 Webhook 代理前，请先设置代理端口")
    return config


def _build_proxy_url(port: int) -> str:
    return f"http://{OUTBOUND_PROXY_HOST}:{port}"


def _scope_enabled(config: OutboundProxyConfigRead, scope: OutboundProxyScope) -> bool:
    if scope == "webhook":
        return bool(config.webhook_enabled)
    raise ValidationError(f"Unsupported outbound proxy scope: {scope}")


def get_outbound_proxy_config(session: Session) -> OutboundProxyConfigRead:
    profile = _get_site_profile(session)
    return _normalize_outbound_proxy_config((profile.feature_flags or {}).get(OUTBOUND_PROXY_FLAG_KEY))


def restore_outbound_proxy_config(session: Session, snapshot: dict[str, Any]) -> None:
    profile = _get_site_profile(session)
    config = _normalize_outbound_proxy_config(snapshot)
    feature_flags = dict(profile.feature_flags or {})
    feature_flags[OUTBOUND_PROXY_FLAG_KEY] = _serialize_outbound_proxy_config(config)
    profile.feature_flags = feature_flags
    session.flush()


def update_outbound_proxy_config(
    session: Session,
    payload: OutboundProxyConfigUpdate,
) -> OutboundProxyConfigRead:
    config = _resolve_outbound_proxy_config(session, payload)
    with _feature_flags_lock:
        profile = _get_site_profile(session)
        feature_flags = dict(profile.feature_flags or {})
        feature_flags[OUTBOUND_PROXY_FLAG_KEY] = _serialize_outbound_proxy_config(config)
        profile.feature_flags = feature_flags
        session.commit()
    return get_outbound_proxy_config(session)


def get_outbound_proxy_request_options(
    session: Session,
    *,
    scope: OutboundProxyScope,
) -> dict[str, object]:
    config = get_outbound_proxy_config(session)
    if config.proxy_port is None or not _scope_enabled(config, scope):
        return {}
    return {
        "proxy": _build_proxy_url(config.proxy_port),
        "trust_env": False,
    }


def test_outbound_proxy_config(
    session: Session,
    payload: OutboundProxyConfigUpdate | None = None,
) -> OutboundProxyHealthRead:
    config = _resolve_outbound_proxy_config(session, payload)
    if config.proxy_port is None:
        raise ValidationError("请先填写代理端口")

    proxy_url = _build_proxy_url(config.proxy_port)
    started_at = time.perf_counter()

    try:
        with socket.create_connection((OUTBOUND_PROXY_HOST, config.proxy_port), timeout=3.0):
            pass
    except OSError as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return OutboundProxyHealthRead(
            ok=False,
            proxy_url=proxy_url,
            summary=f"无法连接到 {OUTBOUND_PROXY_HOST}:{config.proxy_port}：{exc}",
            latency_ms=latency_ms,
        )

    try:
        response = httpx.get(
            OUTBOUND_PROXY_HEALTHCHECK_URL,
            proxy=proxy_url,
            timeout=httpx.Timeout(connect=5.0, read=8.0, write=5.0, pool=5.0),
            follow_redirects=True,
            trust_env=False,
        )
    except httpx.HTTPError as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return OutboundProxyHealthRead(
            ok=False,
            proxy_url=proxy_url,
            summary=f"端口可以连接，但代理转发请求失败：{exc}",
            latency_ms=latency_ms,
        )

    latency_ms = int((time.perf_counter() - started_at) * 1000)
    ok = response.status_code < 500
    summary = "代理端口连通，HTTP 出站请求可用" if ok else f"代理端口连通，但探测请求返回 HTTP {response.status_code}"
    return OutboundProxyHealthRead(
        ok=ok,
        proxy_url=proxy_url,
        summary=summary,
        latency_ms=latency_ms,
        status_code=response.status_code,
    )
