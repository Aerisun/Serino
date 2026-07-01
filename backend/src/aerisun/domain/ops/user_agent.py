"""User-Agent parsing helpers built on top of :mod:`ua_parser`.

The middleware/beacon only stores the raw ``User-Agent`` string, which is hard
to read in the admin dashboard.  This module turns that raw string into a small
set of human friendly fields (browser / os / device type) and provides a more
reliable bot heuristic than naive substring matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ua_parser import parse

# Device families that ua-parser reports for tablet-class hardware.  Everything
# else with a concrete (non "Other"/"Spider") family is treated as a phone.
_TABLET_MARKERS = (
    "ipad",
    "tablet",
    "kindle",
    "playbook",
    "galaxy tab",
    "nexus 7",
    "nexus 9",
    "nexus 10",
    "surface",
)

# Extra substrings that flag automated clients which ua-parser may not classify
# as a "Spider" device (CLI tools, libraries, headless browsers, monitors).
_BOT_MARKERS = (
    "bot",
    "spider",
    "crawler",
    "crawl",
    "slurp",
    "curl",
    "wget",
    "headless",
    "python-requests",
    "httpx",
    "axios",
    "okhttp",
    "go-http-client",
    "java/",
    "uptime",
    "monitor",
    "facebookexternalhit",
    "embedly",
    "preview",
)

DEVICE_DESKTOP = "desktop"
DEVICE_MOBILE = "mobile"
DEVICE_TABLET = "tablet"
DEVICE_BOT = "bot"
DEVICE_UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class UserAgentInfo:
    browser: str | None = None
    browser_version: str | None = None
    os: str | None = None
    os_version: str | None = None
    device_type: str = DEVICE_UNKNOWN
    is_bot: bool = False


def _join_version(*parts: str | None) -> str | None:
    cleaned = [part for part in parts if part not in (None, "")]
    return ".".join(cleaned) if cleaned else None


def _classify_device(device_family: str | None, os_family: str | None, lowered: str) -> str:
    if device_family:
        family_lower = device_family.lower()
        if family_lower == "spider":
            return DEVICE_BOT
        if family_lower not in ("other", ""):
            if any(marker in family_lower for marker in _TABLET_MARKERS):
                return DEVICE_TABLET
            return DEVICE_MOBILE

    # Fall back to OS / UA hints when ua-parser reports a generic device.
    if "ipad" in lowered:
        return DEVICE_TABLET
    if os_family:
        os_lower = os_family.lower()
        if os_lower in ("ios",):
            return DEVICE_TABLET if "ipad" in lowered else DEVICE_MOBILE
        if os_lower == "android":
            return DEVICE_MOBILE if "mobile" in lowered else DEVICE_TABLET
        if os_lower in ("windows", "mac os x", "linux", "ubuntu", "chrome os", "fedora", "debian"):
            return DEVICE_DESKTOP
    if "mobile" in lowered:
        return DEVICE_MOBILE
    return DEVICE_DESKTOP


@lru_cache(maxsize=4096)
def parse_user_agent(user_agent: str | None) -> UserAgentInfo:
    """Parse a raw ``User-Agent`` string into structured fields.

    Results are memoised because the same UA string repeats across many visits.
    """

    if not user_agent or not user_agent.strip():
        return UserAgentInfo()

    lowered = user_agent.lower()
    result = parse(user_agent)

    browser = result.user_agent.family if result.user_agent else None
    browser_version = _join_version(result.user_agent.major, result.user_agent.minor) if result.user_agent else None
    os_family = result.os.family if result.os else None
    os_version = _join_version(result.os.major, result.os.minor) if result.os else None
    device_family = result.device.family if result.device else None

    device_type = _classify_device(device_family, os_family, lowered)
    is_bot = device_type == DEVICE_BOT or any(marker in lowered for marker in _BOT_MARKERS)
    if is_bot and device_type != DEVICE_BOT:
        device_type = DEVICE_BOT

    if browser in (None, "Other", ""):
        browser = None
        browser_version = None
    if os_family in (None, "Other", ""):
        os_family = None
        os_version = None

    return UserAgentInfo(
        browser=browser,
        browser_version=browser_version,
        os=os_family,
        os_version=os_version,
        device_type=device_type,
        is_bot=is_bot,
    )
