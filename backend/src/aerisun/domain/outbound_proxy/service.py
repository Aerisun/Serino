from __future__ import annotations

import os
import socket
import threading
import time
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from sqlalchemy.orm import Session

from aerisun.domain.exceptions import ResourceNotFound, ValidationError
from aerisun.domain.site_config import repository as site_repo

from .schemas import OutboundProxyConfigRead, OutboundProxyConfigUpdate, OutboundProxyHealthRead

OUTBOUND_PROXY_FLAG_KEY = "outbound_proxy_config"
OUTBOUND_PROXY_HOST = "127.0.0.1"
OUTBOUND_PROXY_HOST_CANDIDATES = ("127.0.0.1", "host.docker.internal", "gateway.docker.internal")
OUTBOUND_PROXY_HEALTHCHECK_URL = "https://example.com/"
OUTBOUND_PROXY_ENV_KEYS = (
    "HTTPS_PROXY",
    "https_proxy",
    "HTTP_PROXY",
    "http_proxy",
    "ALL_PROXY",
    "all_proxy",
)
OutboundProxyScope = Literal["webhook", "oauth"]

_DEFAULT_OUTBOUND_PROXY_CONFIG: dict[str, Any] = {
    "proxy_port": None,
    "webhook_enabled": False,
    "oauth_enabled": False,
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
        if "oauth_enabled" in raw:
            data["oauth_enabled"] = bool(raw.get("oauth_enabled"))
        targets = raw.get("targets")
        if isinstance(targets, dict):
            if "webhook_enabled" not in raw:
                data["webhook_enabled"] = bool(targets.get("webhook", False))
            if "oauth_enabled" not in raw:
                data["oauth_enabled"] = bool(targets.get("oauth", False))
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
    if config.oauth_enabled and config.proxy_port is None:
        raise ValidationError("开启 OAuth 代理前，请先设置代理端口")
    return config


def _build_proxy_url(port: int) -> str:
    return f"http://{OUTBOUND_PROXY_HOST}:{port}"


def _scope_label(scope: OutboundProxyScope) -> str:
    if scope == "webhook":
        return "Webhook"
    if scope == "oauth":
        return "OAuth"
    raise ValidationError(f"Unsupported outbound proxy scope: {scope}")


def _scope_enabled(config: OutboundProxyConfigRead, scope: OutboundProxyScope) -> bool:
    if scope == "webhook":
        return bool(config.webhook_enabled)
    if scope == "oauth":
        return bool(config.oauth_enabled)
    raise ValidationError(f"Unsupported outbound proxy scope: {scope}")


def _scope_enable_error(scope: OutboundProxyScope) -> str:
    return f"请先在管理台的代理设置里开启{_scope_label(scope)}代理，再继续当前操作。"


def _read_default_gateway_ip() -> str | None:
    try:
        with open("/proc/net/route", encoding="utf-8") as handle:
            next(handle, None)
            for line in handle:
                fields = line.strip().split()
                if len(fields) < 3 or fields[1] != "00000000":
                    continue
                gateway_hex = fields[2]
                if gateway_hex == "00000000":
                    continue
                return socket.inet_ntoa(bytes.fromhex(gateway_hex)[::-1])
    except (OSError, ValueError):
        return None
    return None


def _proxy_candidate_urls(port: int) -> list[str]:
    urls: list[str] = []
    seen_hosts: set[str] = set()
    for host in (*OUTBOUND_PROXY_HOST_CANDIDATES, _read_default_gateway_ip()):
        normalized = str(host or "").strip()
        if not normalized or normalized in seen_hosts:
            continue
        seen_hosts.add(normalized)
        urls.append(f"http://{normalized}:{port}")
    return urls


def _select_proxy_url(port: int) -> str:
    proxy_urls = _proxy_candidate_urls(port)
    for proxy_url in proxy_urls:
        parts = urlsplit(proxy_url)
        host = parts.hostname or OUTBOUND_PROXY_HOST
        try:
            with socket.create_connection((host, port), 0.15):
                return proxy_url
        except OSError:
            continue
    return proxy_urls[0] if proxy_urls else _build_proxy_url(port)


def _proxy_env_urls() -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for key in OUTBOUND_PROXY_ENV_KEYS:
        value = os.environ.get(key, "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def _try_proxy_candidates(
    method: str,
    url: str,
    *,
    proxy_urls: list[str],
    request_kwargs: dict[str, object],
) -> tuple[httpx.Response, str]:
    last_error: httpx.HTTPError | None = None
    for proxy_url in proxy_urls:
        try:
            response = httpx.request(
                method,
                url,
                proxy=proxy_url,
                trust_env=False,
                **request_kwargs,
            )
            return response, proxy_url
        except httpx.HTTPError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise httpx.ConnectError(
        "No outbound proxy candidates available.",
        request=httpx.Request(method, url),
    )


def require_outbound_proxy_scope(
    session: Session,
    *,
    scope: OutboundProxyScope,
) -> OutboundProxyConfigRead:
    config = get_outbound_proxy_config(session)
    if config.proxy_port is None or not _scope_enabled(config, scope):
        raise ValidationError(_scope_enable_error(scope))
    return config


def send_outbound_request(
    session: Session,
    *,
    scope: OutboundProxyScope,
    method: str,
    url: str,
    allow_env_fallback: bool = True,
    **request_kwargs: object,
) -> httpx.Response:
    config = require_outbound_proxy_scope(session, scope=scope)
    preferred_proxy_url = _select_proxy_url(config.proxy_port or 0)
    proxy_urls = [
        preferred_proxy_url,
        *[item for item in _proxy_candidate_urls(config.proxy_port or 0) if item != preferred_proxy_url],
    ]
    try:
        response, _proxy_url = _try_proxy_candidates(
            method,
            url,
            proxy_urls=proxy_urls,
            request_kwargs=request_kwargs,
        )
        return response
    except httpx.HTTPError:
        env_proxy_urls = _proxy_env_urls()
        if not allow_env_fallback or not env_proxy_urls:
            raise
        return httpx.request(method, url, trust_env=True, **request_kwargs)


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
        "proxy": _select_proxy_url(config.proxy_port),
        "trust_env": False,
    }


def test_outbound_proxy_config(
    session: Session,
    payload: OutboundProxyConfigUpdate | None = None,
) -> OutboundProxyHealthRead:
    config = _resolve_outbound_proxy_config(session, payload)
    if config.proxy_port is None:
        raise ValidationError("请先填写代理端口")

    proxy_urls = _proxy_candidate_urls(config.proxy_port)
    started_at = time.perf_counter()
    candidate_errors: list[str] = []

    for proxy_url in proxy_urls:
        parts = urlsplit(proxy_url)
        host = parts.hostname or OUTBOUND_PROXY_HOST
        try:
            with socket.create_connection((host, config.proxy_port), timeout=3.0):
                pass
        except OSError as exc:
            candidate_errors.append(f"{host}:{config.proxy_port} 无法连接：{exc}")
            continue

        try:
            response = httpx.get(
                OUTBOUND_PROXY_HEALTHCHECK_URL,
                proxy=proxy_url,
                timeout=httpx.Timeout(connect=5.0, read=8.0, write=5.0, pool=5.0),
                follow_redirects=True,
                trust_env=False,
            )
        except httpx.HTTPError as exc:
            candidate_errors.append(f"{proxy_url} 转发失败：{exc}")
            continue

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        ok = response.status_code < 500
        summary = (
            f"代理端口连通，当前通过 {proxy_url} 完成 HTTP 出站请求"
            if ok
            else f"代理端口连通，但通过 {proxy_url} 的探测请求返回 HTTP {response.status_code}"
        )
        return OutboundProxyHealthRead(
            ok=ok,
            proxy_url=proxy_url,
            summary=summary,
            latency_ms=latency_ms,
            status_code=response.status_code,
        )

    latency_ms = int((time.perf_counter() - started_at) * 1000)
    summary = "；".join(candidate_errors[:3]) if candidate_errors else "没有可用的代理候选地址"
    return OutboundProxyHealthRead(
        ok=False,
        proxy_url=proxy_urls[0] if proxy_urls else _build_proxy_url(config.proxy_port),
        summary=summary,
        latency_ms=latency_ms,
    )
