"""Compatibility exports for the old modules.site_config.schemas path."""

from __future__ import annotations

from aerisun.schemas import PageCollectionRead, ResumeRead, SiteConfigRead

PagesRead = PageCollectionRead
SiteRead = SiteConfigRead

__all__ = [
    "PagesRead",
    "ResumeRead",
    "SiteRead",
]
