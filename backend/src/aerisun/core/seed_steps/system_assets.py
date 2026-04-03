from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from aerisun.core.seed_steps.assets import ensure_seed_asset, ensure_system_asset_reference

SYSTEM_ASSET_ROOT = Path(__file__).resolve().parent / "resources" / "system_assets"


@dataclass(frozen=True)
class CoreSystemAssetSpec:
    label: str
    field_name: str
    source_relative_path: str | None
    category: str
    seed_note: str | None
    reference_note: str


CORE_SYSTEM_ASSET_SPECS = (
    CoreSystemAssetSpec(
        label="Hero 翻转视觉图",
        field_name="hero_image_url",
        source_relative_path="hero_flip_visual.webp",
        category="hero-image",
        seed_note="首页 Hero 翻转视觉图（系统资源初始化）",
        reference_note="首页 Hero 翻转视觉图（系统资源归拢）",
    ),
    CoreSystemAssetSpec(
        label="首页视频封面图",
        field_name="hero_poster_url",
        source_relative_path="hero_video_poster.webp",
        category="hero-poster",
        seed_note="首页 Hero 视频封面图（系统资源初始化）",
        reference_note="首页 Hero 视频封面图（系统资源归拢）",
    ),
    CoreSystemAssetSpec(
        label="首页背景视频",
        field_name="hero_video_url",
        source_relative_path=None,
        category="hero-video",
        seed_note=None,
        reference_note="首页 Hero 背景视频（系统资源归拢）",
    ),
    CoreSystemAssetSpec(
        label="分享图 / 首页背景兜底图",
        field_name="og_image",
        source_relative_path="share_fallback_bg.webp",
        category="site-og",
        seed_note="站点默认 OG 分享图（系统资源初始化）",
        reference_note="站点分享图（系统资源归拢）",
    ),
    CoreSystemAssetSpec(
        label="浏览器标签图标",
        field_name="site_icon_url",
        source_relative_path="browser_tab_icon.svg",
        category="site-icon",
        seed_note="站点默认标签页图标（系统资源初始化）",
        reference_note="站点标签页图标（系统资源归拢）",
    ),
    CoreSystemAssetSpec(
        label="简历头像",
        field_name="profile_image_url",
        source_relative_path="resume_avatar.webp",
        category="resume-avatar",
        seed_note="简历默认头像（系统资源初始化）",
        reference_note="简历默认头像（系统资源归拢）",
    ),
)

_CORE_SYSTEM_ASSET_SPEC_BY_FIELD = {spec.field_name: spec for spec in CORE_SYSTEM_ASSET_SPECS}


def get_system_asset_root() -> Path:
    return SYSTEM_ASSET_ROOT


def seed_core_system_asset_urls(session: Session) -> dict[str, str]:
    asset_root = get_system_asset_root()
    seeded_urls: dict[str, str] = {}
    for spec in CORE_SYSTEM_ASSET_SPECS:
        if spec.source_relative_path is None or spec.seed_note is None:
            continue
        seeded_urls[spec.field_name] = ensure_seed_asset(
            session,
            source_path=asset_root / spec.source_relative_path,
            category=spec.category,
            note=spec.seed_note,
        )
    return seeded_urls


def normalize_core_system_asset_references(session: Session, *, site: object | None, resume: object | None) -> None:
    source_roots = (get_system_asset_root(),)
    if site is not None:
        for field_name in ("og_image", "site_icon_url", "hero_image_url", "hero_poster_url", "hero_video_url"):
            spec = _CORE_SYSTEM_ASSET_SPEC_BY_FIELD[field_name]
            normalized = ensure_system_asset_reference(
                session,
                source_value=getattr(site, field_name),
                category=spec.category,
                note=spec.reference_note,
                source_roots=source_roots,
            )
            if field_name == "hero_video_url":
                setattr(site, field_name, normalized or None)
            else:
                setattr(site, field_name, normalized)

    if resume is not None:
        spec = _CORE_SYSTEM_ASSET_SPEC_BY_FIELD["profile_image_url"]
        resume.profile_image_url = ensure_system_asset_reference(
            session,
            source_value=resume.profile_image_url,
            category=spec.category,
            note=spec.reference_note,
            source_roots=source_roots,
        )
