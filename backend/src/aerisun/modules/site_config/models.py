"""Compatibility exports for the old modules.site_config.models path.

The active runtime models live in ``aerisun.models``. This module re-exports
their site configuration tables so older imports resolve to the single source
of truth instead of a second, divergent schema copy.
"""

from __future__ import annotations

from aerisun.models import (
    PageCopy,
    PageDisplayOption,
    Poem,
    ResumeBasics,
    ResumeExperience,
    ResumeSkillGroup,
    SiteProfile,
    SocialLink,
)

ResumeBasic = ResumeBasics
ResumeSkill = ResumeSkillGroup

__all__ = [
    "PageCopy",
    "PageDisplayOption",
    "Poem",
    "ResumeBasic",
    "ResumeExperience",
    "ResumeSkill",
    "SiteProfile",
    "SocialLink",
]
