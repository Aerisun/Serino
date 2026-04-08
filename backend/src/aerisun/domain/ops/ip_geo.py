from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from ipaddress import ip_address

import httpx

from aerisun.core.settings import get_settings
from aerisun.core.time import shanghai_now

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IpGeoResult:
    city: str | None = None
    region: str | None = None
    country: str | None = None
    isp: str | None = None
    owner: str | None = None

    @property
    def location_label(self) -> str | None:
        parts = [part for part in (self.country, self.region, self.city) if part]
        return " / ".join(parts) if parts else None


_CACHE: dict[str, tuple[datetime, IpGeoResult]] = {}


def _is_public_ip(ip: str) -> bool:
    normalized = (ip or "").strip()
    if not normalized:
        return False
    if normalized.lower() == "unknown":
        return False

    # Common proxy header value format: "client, proxy1, proxy2"
    candidate = normalized.split(",", 1)[0].strip()
    if not candidate:
        return False

    try:
        parsed = ip_address(candidate)
    except ValueError:
        return False
    return parsed.is_global


def lookup_ip_geolocation(ip: str) -> IpGeoResult:
    settings = get_settings()
    if not settings.ip_geo_enabled or not _is_public_ip(ip):
        return IpGeoResult()

    now = shanghai_now()
    cached = _CACHE.get(ip)
    if cached and cached[0] > now:
        return cached[1]

    result = IpGeoResult()
    try:
        with httpx.Client(timeout=settings.ip_geo_timeout_seconds, follow_redirects=True) as client:
            response = client.get(f"{settings.ip_geo_api_base_url}/{ip}")
            response.raise_for_status()
            payload = response.json()
            result = IpGeoResult(
                city=payload.get("cityName") or payload.get("city") or None,
                region=payload.get("regionName") or payload.get("region") or None,
                country=payload.get("countryName") or payload.get("country") or None,
                isp=payload.get("isp") or None,
                owner=payload.get("organizationName") or payload.get("owner") or None,
            )
    except Exception:
        logger.warning("IP geolocation lookup failed for %s", ip, exc_info=True)
        result = IpGeoResult()

    _CACHE[ip] = (now + timedelta(seconds=settings.ip_geo_cache_ttl_seconds), result)
    return result
