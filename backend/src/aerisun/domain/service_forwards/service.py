from __future__ import annotations

import fcntl
import hashlib
import ipaddress
import json
import os
import re
import tempfile
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import httpx

from aerisun.core.settings import Settings, get_settings
from aerisun.core.time import shanghai_now
from aerisun.domain.exceptions import (
    ResourceNotFound,
    ServiceUnavailable,
    StateConflict,
    ValidationError,
)

from .schemas import ServiceForwardRead, ServiceForwardWrite

_RESERVED_SLUGS = {
    "admin",
    "api",
    "assets",
    "bootstrap.js",
    "calendar",
    "diary",
    "excerpts",
    "feed.xml",
    "feeds",
    "feeds.xml",
    "fonts",
    "friends",
    "guestbook",
    "index.html",
    "llms.txt",
    "manifest.webmanifest",
    "mcp",
    "media",
    "notes",
    "posts",
    "preview",
    "registerSW.js",
    "resume",
    "resume.md",
    "robots.txt",
    "rss.xml",
    "sitemap.xml",
    "sw.js",
    "thoughts",
    "waline",
}
_MAGIC_DNS_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_MAGIC_DNS_FQDN_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_METADATA_RE = re.compile(r"^# (?P<key>serino-route-[a-z-]+): (?P<value>.*)$")
_ROUTE_ID_RE = re.compile(r"^[0-9a-f]{16}$")
_STATUS_FILE_NAME = ".service-forward-status.json"
_LOCK_FILE_NAME = ".serino-routes.lock"


@dataclass(frozen=True)
class _ResolvedTarget:
    upstream: str
    base_path: str
    target_url: str


def route_id_for_path(path: str) -> str:
    return hashlib.sha256(path.encode()).hexdigest()[:16]


def _validate_slug(slug: str, settings: Settings | None = None) -> None:
    reserved_slugs = set(_RESERVED_SLUGS)
    if settings is not None:
        for configured_path in (settings.api_base_path, settings.admin_base_path, settings.waline_base_path):
            top_level = configured_path.strip("/").split("/", 1)[0]
            if top_level:
                reserved_slugs.add(top_level)
    if slug in reserved_slugs:
        raise ValidationError(f"SLUG /{slug} 已由 Serino 使用")


def _normalize_tailscale_host(raw_host: str) -> str:
    host = raw_host.strip().lower().rstrip(".")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if _MAGIC_DNS_LABEL_RE.fullmatch(host):
            return host
        if host.endswith(".ts.net") and _MAGIC_DNS_FQDN_RE.fullmatch(host):
            return host
        raise ValidationError("请输入 Tailscale IP、MagicDNS 设备名或 .ts.net 地址") from None

    tailscale_v4 = ipaddress.ip_network("100.64.0.0/10")
    tailscale_v6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")
    if address not in tailscale_v4 and address not in tailscale_v6:
        raise ValidationError("目标 IP 不属于 Tailscale 地址范围")
    return address.compressed


def _normalize_tailscale_target_url(raw_url: str) -> _ResolvedTarget:
    try:
        parsed = urlsplit(raw_url)
        port = parsed.port
    except ValueError:
        raise ValidationError("请输入完整的 Tailscale HTTP 或 HTTPS 服务网址") from None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValidationError("请输入完整的 Tailscale HTTP 或 HTTPS 服务网址")
    if parsed.username is not None or parsed.password is not None:
        raise ValidationError("Tailscale 服务网址不能包含用户名或密码")
    if parsed.query or parsed.fragment:
        raise ValidationError("Tailscale 服务网址不能包含查询参数或片段")

    host = _normalize_tailscale_host(parsed.hostname)
    base_path = parsed.path.rstrip("/")
    if base_path:
        if re.search(r"[\x00-\x20\\\"{}]", base_path) or re.search(r"%(?![0-9a-fA-F]{2})", base_path):
            raise ValidationError("Tailscale 服务网址包含不支持的路径字符")
        decoded_segments = unquote(base_path).split("/")
        if any(segment in {".", ".."} for segment in decoded_segments):
            raise ValidationError("Tailscale 服务网址不能包含相对路径")

    rendered_host = f"[{host}]" if ":" in host else host
    authority = f"{rendered_host}:{port}" if port is not None else rendered_host
    upstream = f"{parsed.scheme}://{authority}"
    return _ResolvedTarget(
        upstream=upstream,
        base_path=base_path,
        target_url=f"{upstream}{base_path}",
    )


def _target_from_payload(payload: ServiceForwardWrite) -> _ResolvedTarget:
    if payload.source == "tailscale":
        return _normalize_tailscale_target_url(payload.target_url or "")
    upstream = f"http://127.0.0.1:{payload.port}"
    return _ResolvedTarget(upstream=upstream, base_path="", target_url=upstream)


def render_route_file(payload: ServiceForwardWrite) -> tuple[str, str, str]:
    _validate_slug(payload.slug)
    path = f"/{payload.slug}"
    route_id = route_id_for_path(path)
    target = _target_from_payload(payload)
    lines = [
        "# Managed by Serino admin. This file is local to this server.",
        "# serino-route-schema: 3",
        f"# serino-route-name: {payload.name}",
        f"# serino-route-source: {payload.source}",
        f"# serino-route-path: {path}",
        f"# serino-route-upstream: {target.upstream}",
    ]
    if target.base_path:
        lines.append(f"# serino-route-base-path: {target.base_path}")
    lines.extend(
        [
            f"@serino_user_route_{route_id} path {path} {path}/*",
            f"handle @serino_user_route_{route_id} {{",
        ]
    )
    if target.base_path:
        lines.append(f"    uri replace {path} {target.base_path} 1")
    else:
        lines.append(f"    uri strip_prefix {path}")
    lines.extend(
        [
            f"    reverse_proxy {target.upstream} {{",
        ]
    )
    if target.upstream.startswith("https://"):
        lines.append("        header_up Host {upstream_hostport}")
    lines.extend(
        [
            "        stream_close_delay 5m",
            "    }",
            "}",
            "",
        ]
    )
    return route_id, target.target_url, "\n".join(lines)


@contextmanager
def _routes_lock(routes_dir: Path):
    routes_dir.mkdir(mode=0o770, parents=True, exist_ok=True)
    lock_path = routes_dir / _LOCK_FILE_NAME
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o770, parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.chmod(0o640)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _read_metadata(path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                match = _METADATA_RE.match(line.rstrip("\n"))
                if match:
                    metadata[match.group("key")] = match.group("value")
    except (OSError, UnicodeError):
        return {}
    return metadata


def _status_path(settings: Settings) -> Path:
    return settings.caddy_routes_dir.expanduser().resolve() / _STATUS_FILE_NAME


def _read_status_cache(settings: Settings) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(_status_path(settings).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {key: value for key, value in payload.items() if isinstance(key, str) and isinstance(value, dict)}


def _write_status_cache(settings: Settings, cache: dict[str, dict[str, Any]]) -> None:
    _atomic_write(_status_path(settings), json.dumps(cache, ensure_ascii=False, sort_keys=True))


def _invalidate_status(settings: Settings, *route_ids: str) -> None:
    cache = _read_status_cache(settings)
    changed = False
    for route_id in route_ids:
        if route_id in cache:
            cache.pop(route_id, None)
            changed = True
    if changed:
        _write_status_cache(settings, cache)


def _public_url(settings: Settings, route_path: str) -> str:
    return f"{settings.site_url.rstrip('/')}{route_path}"


def _parse_route_file(
    path: Path,
    settings: Settings,
    status_cache: dict[str, dict[str, Any]] | None = None,
) -> ServiceForwardRead | None:
    metadata = _read_metadata(path)
    route_path = metadata.get("serino-route-path", "")
    upstream = metadata.get("serino-route-upstream", "")
    if not route_path.startswith("/") or not upstream:
        return None
    parsed = urlsplit(upstream)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    base_path = metadata.get("serino-route-base-path", "")
    if base_path and not base_path.startswith("/"):
        return None
    target_url = f"{upstream.rstrip('/')}{base_path}"
    slug = route_path.removeprefix("/")
    source = metadata.get("serino-route-source", "custom")
    if source not in {"local", "tailscale"}:
        source = "custom"
    route_id = route_id_for_path(route_path)
    cached_status = (status_cache or {}).get(route_id, {})
    if cached_status.get("target_url") != target_url:
        cached_status = {}
    checked_at: datetime | None = None
    if isinstance(cached_status.get("checked_at"), str):
        try:
            checked_at = datetime.fromisoformat(cached_status["checked_at"])
        except ValueError:
            checked_at = None
    cached_state = cached_status.get("status")
    status = cached_state if cached_state in {"reachable", "unreachable"} else "unchecked"
    status_message = cached_status.get("status_message")
    return ServiceForwardRead(
        id=route_id,
        name=metadata.get("serino-route-name") or slug,
        slug=slug,
        path=route_path,
        source=source,
        target_url=target_url,
        public_url=_public_url(settings, route_path),
        status=status,
        checked_at=checked_at,
        status_message=status_message if isinstance(status_message, str) else None,
    )


def list_service_forwards(settings: Settings | None = None) -> list[ServiceForwardRead]:
    active_settings = settings or get_settings()
    routes_dir = active_settings.caddy_routes_dir.expanduser().resolve()
    if not routes_dir.is_dir():
        return []
    status_cache = _read_status_cache(active_settings)
    routes = [
        route
        for route_file in sorted(routes_dir.glob("route-*.caddy"))
        if (route := _parse_route_file(route_file, active_settings, status_cache)) is not None
    ]
    return sorted(routes, key=lambda route: route.path)


def _route_file(settings: Settings, route_id: str, *, require_exists: bool = True) -> Path:
    if not _ROUTE_ID_RE.fullmatch(route_id):
        raise ResourceNotFound("服务转发规则不存在")
    path = settings.caddy_routes_dir.expanduser().resolve() / f"route-{route_id}.caddy"
    if require_exists and not path.is_file():
        raise ResourceNotFound("服务转发规则不存在")
    return path


def _reload_caddy_config(settings: Settings) -> None:
    admin_url = settings.caddy_admin_url.strip()
    if not admin_url:
        return
    with httpx.Client(timeout=httpx.Timeout(15.0, connect=3.0), trust_env=False) as client:
        response = client.post(
            admin_url.rstrip("/") + "/load",
            content="import /etc/caddy/Caddyfile\n",
            headers={
                "Content-Type": "text/caddyfile",
                "Cache-Control": "must-revalidate",
            },
        )
        response.raise_for_status()


def _reload_or_rollback(settings: Settings, snapshots: dict[Path, bytes | None]) -> None:
    try:
        _reload_caddy_config(settings)
        return
    except Exception:
        for path, previous_content in snapshots.items():
            if previous_content is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, previous_content.decode("utf-8"))
        with suppress(Exception):
            _reload_caddy_config(settings)
        raise ServiceUnavailable("Caddy 未能加载服务转发配置，已恢复原配置") from None


def _ensure_path_available(
    settings: Settings,
    slug: str,
    *,
    exclude_route_id: str | None = None,
) -> None:
    candidate = f"/{slug}"
    for route in list_service_forwards(settings):
        if route.id == exclude_route_id:
            continue
        if candidate == route.path or candidate.startswith(f"{route.path}/") or route.path.startswith(f"{candidate}/"):
            raise StateConflict(f"SLUG {candidate} 与已有转发 {route.path} 冲突")


def create_service_forward(
    payload: ServiceForwardWrite,
    settings: Settings | None = None,
) -> ServiceForwardRead:
    active_settings = settings or get_settings()
    _validate_slug(payload.slug, active_settings)
    route_id, _upstream, content = render_route_file(payload)
    routes_dir = active_settings.caddy_routes_dir.expanduser().resolve()
    route_path = routes_dir / f"route-{route_id}.caddy"
    with _routes_lock(routes_dir):
        _ensure_path_available(active_settings, payload.slug)
        if route_path.exists():
            raise StateConflict(f"SLUG /{payload.slug} 已存在")
        _atomic_write(route_path, content)
        _reload_or_rollback(active_settings, {route_path: None})
    route = _parse_route_file(route_path, active_settings)
    if route is None:
        raise RuntimeError("无法读取刚写入的服务转发规则")
    return route


def update_service_forward(
    route_id: str,
    payload: ServiceForwardWrite,
    settings: Settings | None = None,
) -> ServiceForwardRead:
    active_settings = settings or get_settings()
    _validate_slug(payload.slug, active_settings)
    routes_dir = active_settings.caddy_routes_dir.expanduser().resolve()
    new_route_id, _upstream, content = render_route_file(payload)
    new_path = routes_dir / f"route-{new_route_id}.caddy"
    with _routes_lock(routes_dir):
        old_path = _route_file(active_settings, route_id)
        _ensure_path_available(active_settings, payload.slug, exclude_route_id=route_id)
        snapshots: dict[Path, bytes | None] = {old_path: old_path.read_bytes()}
        if new_path != old_path:
            snapshots[new_path] = new_path.read_bytes() if new_path.exists() else None
        _atomic_write(new_path, content)
        if new_path != old_path:
            old_path.unlink()
        _reload_or_rollback(active_settings, snapshots)
        _invalidate_status(active_settings, route_id, new_route_id)
    route = _parse_route_file(new_path, active_settings)
    if route is None:
        raise RuntimeError("无法读取刚更新的服务转发规则")
    return route


def delete_service_forward(route_id: str, settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()
    routes_dir = active_settings.caddy_routes_dir.expanduser().resolve()
    with _routes_lock(routes_dir):
        path = _route_file(active_settings, route_id)
        previous_content = path.read_bytes()
        path.unlink()
        _reload_or_rollback(active_settings, {path: previous_content})
        _invalidate_status(active_settings, route_id)


def _probe_target(target_url: str) -> tuple[str, str]:
    try:
        timeout = httpx.Timeout(5.0, connect=3.0)
        with (
            httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client,
            client.stream("GET", target_url) as response,
        ):
            return "reachable", f"目标服务返回 HTTP {response.status_code}"
    except (httpx.HTTPError, OSError) as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        return "unreachable", f"无法连接目标服务：{detail}"


def test_service_forward(route_id: str, settings: Settings | None = None) -> ServiceForwardRead:
    active_settings = settings or get_settings()
    routes_dir = active_settings.caddy_routes_dir.expanduser().resolve()
    with _routes_lock(routes_dir):
        path = _route_file(active_settings, route_id)
        route = _parse_route_file(path, active_settings)
        if route is None:
            raise ResourceNotFound("服务转发规则不存在")
    status, message = _probe_target(route.target_url)
    checked_at = shanghai_now()
    with _routes_lock(routes_dir):
        current_path = _route_file(active_settings, route_id)
        current_route = _parse_route_file(current_path, active_settings)
        if current_route is None:
            raise ResourceNotFound("服务转发规则不存在")
        if current_route.target_url != route.target_url:
            return current_route
        cache = _read_status_cache(active_settings)
        cache[route_id] = {
            "target_url": current_route.target_url,
            "status": status,
            "checked_at": checked_at.isoformat(),
            "status_message": message,
        }
        _write_status_cache(active_settings, cache)
    return current_route.model_copy(update={"status": status, "checked_at": checked_at, "status_message": message})
