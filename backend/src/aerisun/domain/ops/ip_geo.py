from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from aerisun.core.settings import get_settings


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
    lowered = ip.lower()
    if ip in {"unknown", "127.0.0.1", "::1"}:
        return False
    return not (
        lowered.startswith("10.")
        or lowered.startswith("192.168.")
        or lowered.startswith("172.16.")
        or lowered.startswith("172.17.")
        or lowered.startswith("172.18.")
        or lowered.startswith("172.19.")
        or lowered.startswith("172.2")
        or lowered.startswith("172.30.")
        or lowered.startswith("172.31.")
        or lowered.startswith("fc")
        or lowered.startswith("fd")
    )


def lookup_ip_geolocation(ip: str) -> IpGeoResult:
    settings = get_settings()
    if not settings.ip_geo_enabled or not _is_public_ip(ip):
        return IpGeoResult()

    now = datetime.now(UTC)
    cached = _CACHE.get(ip)
    if cached and cached[0] > now:
        return cached[1]

    result = IpGeoResult()
    try:
        with httpx.Client(timeout=settings.ip_geo_timeout_seconds) as client:
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
        result = IpGeoResult()

    _CACHE[ip] = (now + timedelta(seconds=settings.ip_geo_cache_ttl_seconds), result)
    return result
