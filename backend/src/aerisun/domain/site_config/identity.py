from __future__ import annotations

from collections.abc import Mapping

SEARCH_OPTIMIZATION_FLAG_KEY = "search_optimization"


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split())


def read_search_identity_names(feature_flags: object) -> tuple[str, str]:
    if not isinstance(feature_flags, Mapping):
        return "", ""
    search_optimization = feature_flags.get(SEARCH_OPTIMIZATION_FLAG_KEY)
    if not isinstance(search_optimization, Mapping):
        return "", ""
    return (
        _clean_text(search_optimization.get("real_name")),
        _clean_text(search_optimization.get("english_name")),
    )


def build_site_brand_title(display_name: object, real_name: object = "", english_name: object = "") -> str:
    display = _clean_text(display_name)
    real = _clean_text(real_name)
    english = _clean_text(english_name)
    if display and real and english:
        return f"{display} - {real}({english})"
    return display
