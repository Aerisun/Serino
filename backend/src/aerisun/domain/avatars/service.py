from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from urllib.parse import quote

from dicebear import Avatar, Style

NOTIONISTS_AVATAR_BASE_URL = "/api/v1/avatars/10.x/notionists/svg"
NOTIONISTS_SVG_CACHE_SIZE = 256


@lru_cache(maxsize=1)
def _notionists_style() -> Style:
    definition = files("dicebear_styles").joinpath("notionists.json").read_text("utf-8")
    return Style.from_json(definition)


def normalize_avatar_seed(seed: str | None) -> str:
    normalized = (seed or "").strip()
    return normalized or "visitor"


def notionists_avatar_url(seed: str | None) -> str:
    return f"{NOTIONISTS_AVATAR_BASE_URL}?seed={quote(normalize_avatar_seed(seed))}"


def _render_notionists_svg_uncached(seed: str) -> str:
    return Avatar(_notionists_style(), {"seed": seed}).to_string()


@lru_cache(maxsize=NOTIONISTS_SVG_CACHE_SIZE)
def _cached_render_notionists_svg(seed: str) -> str:
    return _render_notionists_svg_uncached(seed)


def render_notionists_svg(seed: str | None) -> str:
    return _cached_render_notionists_svg(normalize_avatar_seed(seed))
