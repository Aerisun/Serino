from __future__ import annotations

import json
import logging
import mimetypes
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aerisun.core.db import get_session_factory, init_db
from aerisun.core.settings import BACKEND_ROOT, get_settings
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.engagement.models import Comment, GuestbookEntry, Reaction
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.media.models import Asset
from aerisun.domain.ops.models import TrafficDailySnapshot, VisitRecord
from aerisun.domain.site_auth.models import SiteAuthConfig
from aerisun.domain.site_config.models import (
    CommunityConfig,
    NavItem,
    PageCopy,
    PageDisplayOption,
    Poem,
    ResumeBasics,
    ResumeExperience,
    ResumeSkillGroup,
    RuntimeSiteSettings,
    SiteProfile,
    SocialLink,
)
from aerisun.domain.social.models import Friend, FriendFeedItem, FriendFeedSource
from aerisun.domain.waline.service import build_comment_path, connect_waline_db, make_waline_comment_row


def _ensure_seed_content_asset(
    session: Session,
    *,
    file_name: str,
    content: bytes,
    mime_type: str | None,
    category: str,
    visibility: str = "internal",
    note: str | None = None,
) -> str:
    settings = get_settings()
    media_dir = settings.media_dir.expanduser().resolve()
    digest = __import__("hashlib").sha256(content).hexdigest()[:12]
    guessed_ext = mimetypes.guess_extension(mime_type or "") or ".bin"
    ext = Path(file_name).suffix.lower().lstrip(".") or guessed_ext.lstrip(".")
    resource_key = f"{visibility}/assets/{category}/{digest}.{ext}"
    existing = session.query(Asset).filter(Asset.resource_key == resource_key).first()
    if existing is not None:
        if existing.scope != "system":
            existing.scope = "system"
        if note and not existing.note:
            existing.note = note
        session.flush()
        return f"/media/{existing.resource_key}"

    storage_path = media_dir / resource_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    if not storage_path.exists():
        storage_path.write_bytes(content)

    asset = Asset(
        file_name=file_name,
        resource_key=resource_key,
        visibility=visibility,
        scope="system",
        category=category,
        note=note,
        storage_path=str(storage_path),
        mime_type=mime_type,
        byte_size=len(content),
        sha256=__import__("hashlib").sha256(content).hexdigest(),
    )
    session.add(asset)
    session.flush()
    return f"/media/{asset.resource_key}"


def _build_seed_avatar_svg(label: str) -> bytes:
    initials = (label.strip()[:2] or "A").upper()
    color_seed = __import__("hashlib").sha256(label.encode("utf-8")).hexdigest()[:6]
    bg = f"#{color_seed}"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"
viewBox="0 0 256 256" role="img" aria-label="{label}">
<rect width="256" height="256" rx="56" fill="{bg}"/>
<text x="50%" y="54%" text-anchor="middle" dominant-baseline="middle"
font-family="Inter, Arial, sans-serif" font-size="88" font-weight="700" fill="white">{initials}</text>
</svg>'''
    return svg.encode("utf-8")


def _ensure_seed_asset(
    session: Session,
    *,
    source_path: Path,
    category: str,
    visibility: str = "internal",
    note: str | None = None,
) -> str:
    settings = get_settings()
    media_dir = settings.media_dir.expanduser().resolve()
    if not source_path.exists():
        return ""

    content = source_path.read_bytes()
    digest = __import__("hashlib").sha256(content).hexdigest()[:12]
    ext = source_path.suffix.lower().lstrip(".") or "bin"
    resource_key = f"{visibility}/assets/{category}/{digest}.{ext}"
    existing = session.query(Asset).filter(Asset.resource_key == resource_key).first()
    if existing is not None:
        if existing.scope != "system":
            existing.scope = "system"
        if note and not existing.note:
            existing.note = note
        session.flush()
        return f"/media/{existing.resource_key}"

    storage_path = media_dir / resource_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    if not storage_path.exists():
        storage_path.write_bytes(content)

    mime_type, _ = mimetypes.guess_type(source_path.name)
    asset = Asset(
        file_name=source_path.name,
        resource_key=resource_key,
        visibility=visibility,
        scope="system",
        category=category,
        note=note,
        storage_path=str(storage_path),
        mime_type=mime_type,
        byte_size=len(content),
        sha256=__import__("hashlib").sha256(content).hexdigest(),
    )
    session.add(asset)
    session.flush()
    return f"/media/{asset.resource_key}"


DEFAULT_SITE_PROFILE = {
    "name": "Felix",
    "title": "Aerisun",
    "bio": "我做网页设计，也写前端，把视觉、节奏、内容和交互整理成一个自然流动的个人空间。",
    "role": "UI/UX Designer · Frontend Developer",
    "footer_text": "Aerisun · Built with care and a small stack.",
    "author": "Felix",
    "og_image": "__SEEDED_OG_IMAGE__",
    "site_icon_url": "__SEEDED_SITE_ICON__",
    "hero_image_url": "__SEEDED_HERO_IMAGE__",
    "hero_poster_url": "__SEEDED_HERO_POSTER__",
    "meta_description": "Felix 的个人网站 - UI/UX 设计师与前端开发者",
    "copyright": "All rights reserved",
    "hero_video_url": "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260306_115329_5e00c9c5-4d69-49b7-94c3-9c31c60bb644.mp4",
    "poem_source": "custom",
    "poem_hitokoto_types": ["d", "i"],
    "poem_hitokoto_keywords": [],
    "hero_actions": json.dumps(
        [
            {"label": "简历", "href": "/resume", "icon_key": "resume"},
            {"label": "留言板", "href": "/guestbook", "icon_key": "guestbook"},
        ],
        ensure_ascii=False,
    ),
    "feature_flags": {"toc": True, "reading_progress": True, "social_sharing": True},
}

DEFAULT_SOCIAL_LINKS = [
    {"name": "GitHub", "href": "https://github.com/", "icon_key": "github", "placement": "hero", "order_index": 0},
    {"name": "Telegram", "href": "https://t.me/", "icon_key": "telegram", "placement": "hero", "order_index": 1},
    {"name": "X", "href": "https://x.com/", "icon_key": "x", "placement": "hero", "order_index": 2},
    {
        "name": "网易云",
        "href": "https://music.163.com/",
        "icon_key": "netease",
        "placement": "footer",
        "order_index": 3,
    },
]

DEFAULT_POEMS = [
    "在清晨和夜色之间，留一点呼吸的缝隙。",
    "把结构放稳，故事就会慢慢长出来。",
    "玻璃不会说话，但会把光留给你。",
    "最小的系统，也可以有完整的节奏。",
    "慢一点，不代表退后。",
    "记录不是负担，而是回声。",
    "让页面像一条安静的河。",
    "让交互只做必要的那一下。",
    "把复杂藏进秩序里。",
    "把想法写下来，它才有形状。",
    "每次重建，都是一次确认。",
    "留白不是空，留白是方向。",
]

DEFAULT_PAGE_COPIES = [
    {
        "page_key": "activity",
        "label": None,
        "nav_label": None,
        "title": "友邻与最近动态",
        "subtitle": "展示朋友动态、最近活动和贡献热力图。",
        "description": "首页活动区配置。",
        "search_placeholder": None,
        "empty_message": None,
        "max_width": "max-w-4xl",
        "page_size": None,
        "download_label": None,
        "extras": {
            "dashboardLabel": "Dashboard",
            "friendCircleTitle": "朋友圈",
            "friendCircleViewAllLabel": "查看全部",
            "friendCircleErrorTitle": "友邻动态加载失败",
            "friendCircleRetryLabel": "重试",
            "friendCircleEmptyMessage": "还没有公开的友邻动态",
            "recentActivityTitle": "最近动态",
            "recentActivityErrorTitle": "最近动态加载失败",
            "recentActivityRetryLabel": "重试",
            "recentActivityEmptyMessage": "暂时还没有公开的最近动态",
            "heatmapTitle": "Activity",
            "heatmapLoadingLabel": "加载中",
            "heatmapErrorLabel": "加载失败",
            "heatmapTotalTemplate": "{total} contributions",
            "heatmapThisWeekLabel": "This week",
            "heatmapPeakWeekLabel": "Peak week",
            "heatmapAverageWeekLabel": "Avg / week",
        },
    },
    {
        "page_key": "notFound",
        "label": None,
        "nav_label": None,
        "title": "这个页面没有留下来",
        "subtitle": "似乎已经离开了当前的路径。",
        "description": "你访问的页面不存在，或者已经被移动。",
        "search_placeholder": None,
        "empty_message": None,
        "max_width": "max-w-2xl",
        "page_size": None,
        "download_label": None,
        "extras": {
            "metaTitle": "页面未找到",
            "metaDescription": "你访问的页面不存在，或者已经被移动。",
            "badgeLabel": "Shell mismatch",
            "homeLabel": "返回首页",
            "backLabel": "返回上页",
        },
    },
    {
        "page_key": "posts",
        "label": "Blog",
        "nav_label": "帖子",
        "title": "Posts",
        "subtitle": "整理过的想法与实践记录。",
        "description": "文章列表与文章详情页文案。",
        "search_placeholder": "搜索文章...",
        "empty_message": "没有找到匹配的文章",
        "max_width": "max-w-3xl",
        "page_size": None,
        "download_label": None,
        "extras": {
            "category_all_label": "全部",
            "category_fallback_label": "未分类",
            "errorTitle": "文章加载失败",
            "retryLabel": "重试",
            "loadMoreLabel": "加载更多...",
            "detailBackLabel": "返回",
            "detailListLabel": "返回列表",
            "detailMissingTitle": "文章不存在",
            "detailMissingDescription": "你访问的文章暂时不存在。",
            "detailEndLabel": "— 完 —",
        },
    },
    {
        "page_key": "diary",
        "label": None,
        "nav_label": "日记",
        "title": "日记",
        "subtitle": "每天一点点，记录生活的温度。",
        "description": "日记页文案。",
        "search_placeholder": None,
        "empty_message": "今天还没有新的日记",
        "max_width": "max-w-2xl",
        "page_size": None,
        "download_label": None,
        "extras": {
            "errorTitle": "日记加载失败",
            "retryLabel": "重试",
            "loadMoreLabel": "加载更多...",
            "detailCtaLabel": "查看详情",
            "detailBackLabel": "返回",
            "detailListLabel": "返回列表",
            "detailMissingTitle": "日记不存在",
            "detailMissingDescription": "你访问的日记暂时不存在。",
            "detailEndLabel": "— 今日份记录 —",
        },
    },
    {
        "page_key": "friends",
        "label": None,
        "nav_label": "友链",
        "title": "朋友们",
        "subtitle": "海内存知己，天涯若比邻。",
        "description": "友链与 Friend Circle 页面文案。",
        "search_placeholder": None,
        "empty_message": "暂时没有友链内容",
        "max_width": "max-w-4xl",
        "page_size": 10,
        "download_label": None,
        "extras": {
            "circle_title": "Friend Circle",
            "errorTitle": "友链页面加载失败",
            "statusLabel": "状态",
            "loadingLabel": "正在加载...",
            "loadMoreLabel": "加载更多",
            "retryLabel": "重试加载",
            "summaryTemplate": "{sites} 个站点 · 共 {articles} 条动态",
            "footerSummaryTemplate": "已连接 {sites} 个站点，最近抓取 {articles} 条公开动态",
        },
    },
    {
        "page_key": "excerpts",
        "label": None,
        "nav_label": "文摘",
        "title": "文摘",
        "subtitle": "摘录那些让我停下来想一想的文字。",
        "description": "文摘页文案。",
        "search_placeholder": None,
        "empty_message": "还没有整理好的文摘",
        "max_width": "max-w-3xl",
        "page_size": None,
        "download_label": None,
        "extras": {
            "modalCloseLabel": "关闭",
            "commentsOpenLabel": "查看评论",
            "commentsCloseLabel": "收起评论",
            "errorTitle": "文摘加载失败",
            "retryLabel": "重试",
            "loadMoreLabel": "加载更多...",
        },
    },
    {
        "page_key": "thoughts",
        "label": None,
        "nav_label": "碎碎念",
        "title": "碎碎念",
        "subtitle": "一些不成文的想法，随手记下的片段。",
        "description": "碎碎念页文案。",
        "search_placeholder": None,
        "empty_message": "最近没有新的碎碎念",
        "max_width": "max-w-2xl",
        "page_size": None,
        "download_label": None,
        "extras": {
            "errorTitle": "碎碎念加载失败",
            "retryLabel": "重试",
            "loadMoreLabel": "加载更多...",
        },
    },
    {
        "page_key": "guestbook",
        "label": None,
        "nav_label": "留言板",
        "title": "留言板",
        "subtitle": "留下你的足迹，说点什么吧。",
        "description": "留言板页文案。",
        "search_placeholder": None,
        "empty_message": "还没有人留言",
        "max_width": "max-w-2xl",
        "page_size": None,
        "download_label": None,
        "extras": {
            "promptTitle": "留言提示",
            "nameFieldLabel": "昵称",
            "contentFieldLabel": "正文",
            "submitFieldLabel": "按钮",
            "namePlaceholder": "你的名字",
            "contentPlaceholder": "想说的话",
            "submitLabel": "提交留言",
            "submittingLabel": "提交留言",
            "loadingLabel": "留言板正在更新",
            "retryLabel": "重试加载",
        },
    },
    {
        "page_key": "resume",
        "label": None,
        "nav_label": "简历",
        "title": "Felix",
        "subtitle": "UI/UX Designer · Frontend Developer",
        "description": "简历页配置。",
        "search_placeholder": None,
        "empty_message": None,
        "max_width": "max-w-3xl",
        "page_size": None,
        "download_label": "下载 PDF",
        "extras": {},
    },
    {
        "page_key": "calendar",
        "label": None,
        "nav_label": "日历",
        "title": "日历",
        "subtitle": "记录每一天的痕迹。",
        "description": "日历与活动投影页面文案。",
        "search_placeholder": None,
        "empty_message": "日历里还没有内容",
        "max_width": "max-w-4xl",
        "page_size": None,
        "download_label": None,
        "extras": {
            "weekdayLabels": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
            "monthLabels": ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"],
            "loadingLabel": "正在加载日历",
            "retryLabel": "重试加载",
            "todayLabel": "今日",
            "errorTitle": "日历加载失败",
            "selectedEmptyMessage": "这一天没有记录",
            "postTypeLabel": "帖子",
            "diaryTypeLabel": "日记",
            "excerptTypeLabel": "文摘",
        },
    },
]

DEFAULT_PAGE_OPTIONS = [
    {"page_key": "activity", "is_enabled": True, "settings": {}},
    {"page_key": "posts", "is_enabled": True, "settings": {"show_search": True}},
    {"page_key": "diary", "is_enabled": True, "settings": {}},
    {"page_key": "friends", "is_enabled": True, "settings": {"circle_page_size": 10}},
    {"page_key": "excerpts", "is_enabled": True, "settings": {}},
    {"page_key": "thoughts", "is_enabled": True, "settings": {}},
    {"page_key": "guestbook", "is_enabled": True, "settings": {}},
    {"page_key": "resume", "is_enabled": True, "settings": {"show_download": True}},
    {"page_key": "calendar", "is_enabled": True, "settings": {}},
]

DEFAULT_NAV_ITEMS = [
    {"label": "首页", "href": "/", "page_key": "home", "trigger": "arrow", "order_index": 0},
    {
        "label": "简历",
        "href": "/resume",
        "page_key": "resume",
        "trigger": "none",
        "order_index": 0,
        "_parent_label": "首页",
    },
    {
        "label": "留言板",
        "href": "/guestbook",
        "page_key": "guestbook",
        "trigger": "none",
        "order_index": 1,
        "_parent_label": "首页",
    },
    {
        "label": "日历",
        "href": "/calendar",
        "page_key": "calendar",
        "trigger": "none",
        "order_index": 2,
        "_parent_label": "首页",
    },
    {"label": "帖子", "href": "/posts", "page_key": "posts", "trigger": "none", "order_index": 1},
    {"label": "友链", "href": "/friends", "page_key": "friends", "trigger": "none", "order_index": 2},
    {"label": "更多", "href": None, "page_key": "more", "trigger": "hover", "order_index": 3},
    {
        "label": "碎碎念",
        "href": "/thoughts",
        "page_key": "thoughts",
        "trigger": "none",
        "order_index": 0,
        "_parent_label": "更多",
    },
    {
        "label": "日记",
        "href": "/diary",
        "page_key": "diary",
        "trigger": "none",
        "order_index": 1,
        "_parent_label": "更多",
    },
    {
        "label": "文摘",
        "href": "/excerpts",
        "page_key": "excerpts",
        "trigger": "none",
        "order_index": 2,
        "_parent_label": "更多",
    },
]

DEFAULT_COMMENT_AVATAR_PRESETS = [
    {
        "key": "shiro",
        "label": "Shiro",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Shiro",
        "note": "社区默认头像预设：Shiro（seed 初始化）",
    },
    {
        "key": "glass",
        "label": "Glass",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Glass",
        "note": "社区默认头像预设：Glass（seed 初始化）",
    },
    {
        "key": "aurora",
        "label": "Aurora",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Aurora",
        "note": "社区默认头像预设：Aurora（seed 初始化）",
    },
    {
        "key": "paper",
        "label": "Paper",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Paper",
        "note": "社区默认头像预设：Paper（seed 初始化）",
    },
    {
        "key": "dawn",
        "label": "Dawn",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Dawn",
        "note": "社区默认头像预设：Dawn（seed 初始化）",
    },
    {
        "key": "pebble",
        "label": "Pebble",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Pebble",
        "note": "社区默认头像预设：Pebble（seed 初始化）",
    },
    {
        "key": "amber",
        "label": "Amber",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Amber",
        "note": "社区默认头像预设：Amber（seed 初始化）",
    },
    {
        "key": "mint",
        "label": "Mint",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Mint",
        "note": "社区默认头像预设：Mint（seed 初始化）",
    },
    {
        "key": "cinder",
        "label": "Cinder",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Cinder",
        "note": "社区默认头像预设：Cinder（seed 初始化）",
    },
    {
        "key": "tide",
        "label": "Tide",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Tide",
        "note": "社区默认头像预设：Tide（seed 初始化）",
    },
    {
        "key": "plum",
        "label": "Plum",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Plum",
        "note": "社区默认头像预设：Plum（seed 初始化）",
    },
    {
        "key": "linen",
        "label": "Linen",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Linen",
        "note": "社区默认头像预设：Linen（seed 初始化）",
    },
]


def build_default_community_config() -> dict[str, object]:
    settings = get_settings()

    return {
        "provider": "waline",
        "server_url": settings.waline_server_url.strip(),
        "surfaces": [
            {
                "key": "posts",
                "label": "文章评论",
                "path": "/posts/{slug}",
                "enabled": True,
            },
            {
                "key": "diary",
                "label": "日记评论",
                "path": "/diary/{slug}",
                "enabled": True,
            },
            {
                "key": "guestbook",
                "label": "留言板",
                "path": "/guestbook",
                "enabled": True,
            },
            {
                "key": "thoughts",
                "label": "碎碎念评论",
                "path": "/thoughts/{slug}",
                "enabled": True,
            },
            {
                "key": "excerpts",
                "label": "文摘评论",
                "path": "/excerpts/{slug}",
                "enabled": True,
            },
        ],
        "meta": ["nick", "mail"],
        "required_meta": ["nick"],
        "emoji_presets": ["twemoji", "qq", "bilibili"],
        "enable_enjoy_search": True,
        "image_uploader": False,
        "login_mode": "force",
        "oauth_url": None,
        "oauth_providers": ["github", "google"],
        "anonymous_enabled": True,
        "moderation_mode": "all_pending",
        "default_sorting": "latest",
        "page_size": 20,
        "image_max_bytes": 524288,
        "avatar_presets": [preset.copy() for preset in DEFAULT_COMMENT_AVATAR_PRESETS],
        "guest_avatar_mode": "preset",
        "draft_enabled": True,
        "avatar_strategy": "dicebear-notionists",
        "avatar_helper_copy": "登录后评论会绑定到当前邮箱或第三方身份，邮箱不会公开显示。",
        "migration_state": "not_started",
    }


def _coerce_community_surfaces(value: object) -> list[dict[str, object]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _merge_community_surfaces(
    current_surfaces: object,
    default_surfaces: list[dict[str, object]],
) -> list[dict[str, object]]:
    existing = _coerce_community_surfaces(current_surfaces)
    existing_by_key = {
        str(item.get("key") or "").strip(): item for item in existing if str(item.get("key") or "").strip()
    }

    merged: list[dict[str, object]] = []
    seen_keys: set[str] = set()
    for default_surface in default_surfaces:
        key = str(default_surface.get("key") or "").strip()
        current = existing_by_key.get(key, {})
        merged.append(
            {
                **default_surface,
                **{name: value for name, value in current.items() if name != "key"},
                "key": key,
            }
        )
        seen_keys.add(key)

    for item in existing:
        key = str(item.get("key") or "").strip()
        if not key or key in seen_keys:
            continue
        merged.append(item)

    return merged


def _normalize_community_server_url(current_url: str | None, default_url: str) -> str:
    normalized_default = default_url.strip() or "/waline"
    normalized_current = (current_url or "").strip().rstrip("/")
    if not normalized_current:
        return normalized_default

    if normalized_current in {
        "http://localhost:8360",
        "http://127.0.0.1:8360",
        "https://localhost:8360",
        "https://127.0.0.1:8360",
    }:
        return normalized_default

    return normalized_current


def _seed_community_config(session: Session) -> None:
    default_config = build_default_community_config()
    config = session.scalars(select(CommunityConfig).order_by(CommunityConfig.created_at.asc())).first()

    if config is None:
        session.add(CommunityConfig(**default_config))
        return

    default_server_url = str(default_config["server_url"]).strip()
    config.server_url = _normalize_community_server_url(config.server_url, default_server_url)
    config.surfaces = _merge_community_surfaces(config.surfaces, list(default_config["surfaces"]))


def _seed_site_auth_config(session: Session) -> None:
    from aerisun.domain.site_auth.service import build_default_site_auth_config

    default_config = build_default_site_auth_config(session)
    config = session.scalars(select(SiteAuthConfig).order_by(SiteAuthConfig.created_at.asc())).first()
    if config is None:
        session.add(SiteAuthConfig(**default_config))
        return

    if config.visitor_oauth_providers is None:
        config.visitor_oauth_providers = list(default_config["visitor_oauth_providers"])
    if config.admin_auth_methods is None:
        config.admin_auth_methods = list(default_config["admin_auth_methods"])
    if getattr(config, "admin_email_enabled", None) is None:
        config.admin_email_enabled = bool(default_config["admin_email_enabled"])
    if not config.google_client_id:
        config.google_client_id = str(default_config["google_client_id"])
    if not config.google_client_secret:
        config.google_client_secret = str(default_config["google_client_secret"])
    if not config.github_client_id:
        config.github_client_id = str(default_config["github_client_id"])
    if not config.github_client_secret:
        config.github_client_secret = str(default_config["github_client_secret"])


def _seed_runtime_site_settings(session: Session) -> None:
    runtime = session.scalars(select(RuntimeSiteSettings).order_by(RuntimeSiteSettings.created_at.asc())).first()
    if runtime is not None:
        return

    site = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
    title = (site.title if site else "").strip()
    description = (site.meta_description if site else "").strip()
    session.add(
        RuntimeSiteSettings(
            public_site_url="",
            production_cors_origins=[],
            seo_default_title=title,
            seo_default_description=description,
            rss_title=title,
            rss_description=description,
            robots_indexing_enabled=True,
            sitemap_static_pages=[
                {"path": "/", "changefreq": "daily", "priority": "1.0"},
                {"path": "/posts", "changefreq": "daily", "priority": "0.9"},
                {"path": "/diary", "changefreq": "daily", "priority": "0.8"},
                {"path": "/thoughts", "changefreq": "weekly", "priority": "0.7"},
                {"path": "/excerpts", "changefreq": "weekly", "priority": "0.7"},
                {"path": "/friends", "changefreq": "weekly", "priority": "0.6"},
                {"path": "/guestbook", "changefreq": "weekly", "priority": "0.5"},
                {"path": "/resume", "changefreq": "monthly", "priority": "0.6"},
                {"path": "/calendar", "changefreq": "daily", "priority": "0.5"},
            ],
        )
    )


DEFAULT_RESUME = {
    "title": "Felix",
    "subtitle": "UI/UX Designer · Frontend Developer",
    "summary": """## Profile
专注把视觉、节奏和交互组织成清晰、克制、可维护的产品体验。

## Experience
### Personal Website & Design System
**Aerisun** · 2024 - Now

- 重构站点信息架构与前后台配置逻辑
- 把展示页、后台和数据结构统一成一套可维护系统
- 持续打磨内容型网站的版式、节奏和视觉完成度

## Skills
- React / TypeScript / Tailwind CSS
- Design Systems / Motion / Information Architecture
- FastAPI / SQLAlchemy / SQLite

## Selected Projects
- 个人网站与内容系统
- 管理后台体验优化
- 简历模板与 Markdown 渲染方案""",
    "download_label": "下载 PDF",
    "template_key": "editorial",
    "accent_tone": "amber",
    "location": "上海 / Remote",
    "availability": "可接受远程合作与品牌项目咨询",
    "email": "felix@example.com",
    "website": "https://aerisun.local/resume",
    "profile_image_url": "__SEEDED_RESUME_AVATAR__",
    "highlights": [
        "8+ 年数字产品体验设计与前端落地经验",
        "擅长内容型网站、品牌官网与设计系统",
        "能独立完成视觉、交互、前端实现与交付规范",
    ],
}

DEFAULT_SKILLS = [
    {"category": "Frontend", "items": ["React", "TypeScript", "Vite", "Tailwind CSS"], "order_index": 0},
    {
        "category": "Design",
        "items": ["UI 系统", "Glassmorphism", "Motion Design", "Information Architecture"],
        "order_index": 1,
    },
    {"category": "Backend", "items": ["FastAPI", "SQLAlchemy", "SQLite", "Docker"], "order_index": 2},
]

DEFAULT_EXPERIENCES = [
    {
        "title": "个人网站与设计系统",
        "company": "Aerisun",
        "period": "2024 - Now",
        "location": "Remote",
        "employment_type": "独立项目",
        "summary": "构建个人网站、设计令牌和可恢复的内容平台。",
        "achievements": [
            "重构站点信息架构，让内容展示和后台配置保持一致",
            "统一设计 token 与组件风格，降低页面维护成本",
            "为文章、简历、留言等页面建立可扩展模板策略",
        ],
        "tech_stack": ["React", "TypeScript", "Tailwind", "FastAPI"],
        "order_index": 0,
    },
    {
        "title": "前端与视觉实现",
        "company": "Independent",
        "period": "2022 - 2024",
        "location": "上海",
        "employment_type": "全职 / 合作",
        "summary": "负责个人项目中的页面节奏、动效和交互组织。",
        "achievements": [
            "为多个项目输出高保真界面方案与交互规范",
            "推动设计到代码的映射规则，减少实现偏差",
            "优化响应式与细节动效，提升整体完成度",
        ],
        "tech_stack": ["Figma", "React", "Framer Motion"],
        "order_index": 1,
    },
]

DEFAULT_POSTS = [
    {
        "slug": "from-zero-design-system",
        "title": "从零搭建个人设计系统的完整思路",
        "summary": "设计系统不只是组件库，它更像是一套把视觉秩序、协作方式与交付节奏串起来的语言。",
        "body": (
            "设计系统真正有价值的部分，不在于组件数量，而在于它有没有把视觉层级、状态表达和内容节奏说清楚。"
            "对个人站来说，它同样可以帮助我把页面气质、动效速度和排版密度保持在同一条线上。"
        ),
        "tags": ["design-system", "frontend"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 21, 9, 0, tzinfo=UTC),
        "category": "设计",
        "view_count": 1247,
    },
    {
        "slug": "liquid-glass-css-notes",
        "title": "液态玻璃效果的 CSS 实现与优化",
        "summary": "从 blur、边框高光到暗色模式折射，这篇文章记录了 Liquid Glass 在 Web 上的取舍。",
        "body": (
            "我把 Liquid Glass 拆成了三层：基础材质、边缘高光和运动反馈。亮色模式更像磨砂玻璃，"
            "暗色模式则更依赖 blur 与边框亮度的平衡。真正的难点不是写出效果，而是让它在不同页面里保持克制。"
        ),
        "tags": ["css", "glass", "performance"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 18, 20, 30, tzinfo=UTC),
        "category": "技术",
        "view_count": 3082,
    },
    {
        "slug": "why-i-choose-indie-design",
        "title": "为什么我选择做独立设计师",
        "summary": "独立不只是工作方式变化，它会同时改变你看待时间、责任和表达的角度。",
        "body": (
            "离开团队之后，我最先感受到的不是自由，而是所有决定都必须由自己承担。也是在这个过程中，"
            "我开始更认真地处理个人表达、项目边界和长期维护成本。网站本身也是这个思路的一部分。"
        ),
        "tags": ["essay", "career"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 14, 8, 15, tzinfo=UTC),
        "category": "随想",
        "view_count": 892,
    },
    {
        "slug": "react-19-design-pattern-shifts",
        "title": "React 19 中值得关注的设计模式变化",
        "summary": "Server Components 和 Actions 正在重塑前端架构，这对设计师和前端开发者意味着什么。",
        "body": (
            "React 19 带来的变化，本质上是在重新分配界面、状态和数据之间的边界。对前端来说，"
            "这不是某个 API 的更新，而是对页面如何被拆分、何时响应、如何组织交互的一次整体提示。"
        ),
        "tags": ["react", "architecture"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 12, 16, 0, tzinfo=UTC),
        "category": "技术",
        "view_count": 2156,
    },
    {
        "slug": "typographic-rhythm-and-spacing",
        "title": "网页排版中的节奏感：间距与留白",
        "summary": "好的排版不是对齐和居中，而是建立阅读节奏。从音乐的角度理解视觉设计中的韵律。",
        "body": (
            "排版真正决定气质的，不是单个字体本身，而是段落之间、标题上下、内容前后那一连串被安排好的停顿。"
            "留白不是空着，而是在替阅读建立呼吸的间隔。"
        ),
        "tags": ["typography", "layout"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 9, 10, 45, tzinfo=UTC),
        "category": "设计",
        "view_count": 1873,
    },
    {
        "slug": "framer-motion-page-transitions",
        "title": "用 Framer Motion 做有质感的页面过渡",
        "summary": "动画不该是装饰，它是信息层级的一部分。分享几个常用过渡模式和背后的判断。",
        "body": (
            "页面过渡如果只是为了“好看”，通常很快就会显得多余。真正耐看的动效是在切换时帮用户理解层级变化，"
            "让视线知道自己正在从哪里离开、要往哪里抵达。"
        ),
        "tags": ["animation", "react"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 6, 19, 20, tzinfo=UTC),
        "category": "技术",
        "view_count": 4210,
    },
    {
        "slug": "solo-workflow-tools-and-rhythm",
        "title": "一个人的工作流：工具、习惯与心态",
        "summary": "作为独立设计师，我每天的工作流程是怎样的，用了哪些工具，踩过哪些坑。",
        "body": (
            "一个人的工作流最难的从来不是工具选择，而是如何给自己建立节奏。没有团队的默认结构之后，"
            "你需要自己决定什么时候深度创作，什么时候整理，什么时候停下来复盘。"
        ),
        "tags": ["workflow", "productivity"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 3, 9, 50, tzinfo=UTC),
        "category": "随想",
        "view_count": 625,
    },
    {
        "slug": "dark-mode-design-details",
        "title": "深色模式设计的七个容易忽略的细节",
        "summary": "深色模式不是简单地把白换成黑。阴影、对比度、饱和度都需要重新审视。",
        "body": (
            "深色模式最大的误区，是把亮色模式的关系原样压暗。真正要被重新设计的，是层级感、边缘感和焦点落点。"
            "只有这些关系成立了，深色界面才会显得稳定而不刺眼。"
        ),
        "tags": ["dark-mode", "ui"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 2, 28, 21, 5, tzinfo=UTC),
        "category": "设计",
        "view_count": 3140,
    },
]

DEFAULT_DIARY_ENTRIES = [
    {
        "slug": "spring-equinox-and-warm-light",
        "title": "春分，天气转暖",
        "summary": "阳光从窗帘缝隙里漏进来，整个房间都有一点松动感。",
        "body": (
            "今天把博客首页重新整理了一遍，花了一上午调 Hero 的呼吸感和玻璃层次。下午去咖啡店坐了两个小时，"
            "回来的路上看到树上的花苞终于鼓起来了，春天像是在慢慢试探地靠近。"
        ),
        "tags": ["life", "spring"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 21, 12, 0, tzinfo=UTC),
        "weather": "sunny",
        "mood": "☀️",
        "poem": "春风如贵客，一到便繁华。——袁枚",
    },
    {
        "slug": "rain-day-and-lofi",
        "title": "下雨的一天",
        "summary": "雨声和 lo-fi 混在一起的时候，写代码的节奏会变得很稳。",
        "body": (
            "今天没有出门，把友链页的假数据重新梳理了一次，也顺手重排了页面间距。中午只简单煮了碗面，"
            "下午继续修动效节奏。一个人在雨天里工作，意外地不觉得孤单。"
        ),
        "tags": ["rain", "worklog"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 19, 14, 45, tzinfo=UTC),
        "weather": "rainy",
        "mood": "🌧️",
        "poem": "小楼一夜听春雨，深巷明朝卖杏花。——陆游",
    },
    {
        "slug": "windy-library-day",
        "title": "风大的图书馆日",
        "summary": "出门时几乎被风推着走，回来时手里多了两本书和一杯热可可。",
        "body": (
            "今天去图书馆归还了上周借的书，又带回两本关于字体与写作的作品。回来的路上一直在想，"
            "网站里的排版为什么总能透露出作者的节奏感。或许页面其实也是一种书写。"
        ),
        "tags": ["library", "reading"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 17, 18, 10, tzinfo=UTC),
        "weather": "windy",
        "mood": "🍃",
        "poem": "解落三秋叶，能开二月花。——李峤",
    },
    {
        "slug": "evening-tram-and-orange-sky",
        "title": "傍晚电车与橙色天光",
        "summary": "夕阳落得很慢，车窗把每个人都镀成了柔和的轮廓。",
        "body": (
            "傍晚坐电车回家的路上，看到天边从浅金一点点沉进橙色。那种颜色很难描述，像刚刚被烤热的玻璃。"
            "我忽然意识到，最近网站里很多暖色过渡，其实都来自这种傍晚记忆。"
        ),
        "tags": ["commute", "sunset"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 15, 18, 40, tzinfo=UTC),
        "weather": "cloudy",
        "mood": "🌇",
        "poem": "落霞与孤鹜齐飞，秋水共长天一色。——王勃",
    },
    {
        "slug": "quiet-sunday-cleanup",
        "title": "安静的周末整理",
        "summary": "清理桌面、归档文件、擦掉屏幕边角的灰，一切都慢下来一点。",
        "body": (
            "今天没有写太多代码，只是把零散的文件和灵感卡片重新归了类。整理这种事很奇怪，它不直接产出什么，"
            "却会让脑子重新变得清楚。晚上顺手把日历页的细节也对齐了一遍。"
        ),
        "tags": ["weekend", "cleanup"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 13, 11, 20, tzinfo=UTC),
        "weather": "sunny",
        "mood": "🧺",
        "poem": "偷得浮生半日闲。——李涉",
    },
    {
        "slug": "midnight-css-and-tea",
        "title": "深夜 CSS 和一杯热茶",
        "summary": "夜里安静到只剩键盘声，调细节时会比白天更专注。",
        "body": (
            "把一段 hover 过渡从 0.3 秒改到 0.45 秒，整个页面都像松了一口气。深夜做这种微调总有一点仪式感，"
            "像给页面悄悄盖上一层更柔软的光。茶喝到最后，已经有些凉了。"
        ),
        "tags": ["night", "css"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 11, 0, 35, tzinfo=UTC),
        "weather": "rainy",
        "mood": "🍵",
        "poem": "何当共剪西窗烛，却话巴山夜雨时。——李商隐",
    },
    {
        "slug": "bookstore-after-rain",
        "title": "雨后去了一趟书店",
        "summary": "空气里有纸张和潮气混在一起的味道，很适合慢慢走。",
        "body": (
            "下午雨停后去了常去的那家独立书店，翻到几本关于版式和建筑的旧书。书店里很安静，灯也不亮，"
            "但有一种很稳定的秩序感。回来之后我把首页的分隔和留白又调整了一次。"
        ),
        "tags": ["bookstore", "reading"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 9, 16, 5, tzinfo=UTC),
        "weather": "cloudy",
        "mood": "📚",
        "poem": "纸上得来终觉浅，绝知此事要躬行。——陆游",
    },
]

DEFAULT_THOUGHTS = [
    {
        "slug": "spacing-rhythm-note",
        "title": "排版节奏的一点记录",
        "summary": "今天只是把字距从 -0.02em 调到 -0.03em，页面气质就完全不一样了。",
        "body": "设计里最迷人的地方，是那些看似只差一点点、实际却会改变整段阅读呼吸感的细节。",
        "tags": ["design", "typography"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 21, 15, 5, tzinfo=UTC),
        "mood": "🎨",
    },
    {
        "slug": "less-but-better-note",
        "title": "少即是多，还是少但更好",
        "summary": "删掉一个不必要的层级，往往比再加一个漂亮组件更难。",
        "body": (
            "最近越来越确信，前端不该一味堆视觉效果。真正重要的是信息的显隐、节奏的松紧，"
            "还有用户什么时候该被提醒、什么时候该被放过。"
        ),
        "tags": ["product", "reflection"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 20, 10, 20, tzinfo=UTC),
        "mood": "💭",
    },
    {
        "slug": "frontend-as-craft",
        "title": "前端有点像手工活",
        "summary": "都是把零散的东西拼成一个完整且可用的整体。",
        "body": "越做越觉得前端和手工很像。你得在结构、材料、手感和最终呈现之间来回试，才能找到一个刚刚好的平衡点。",
        "tags": ["frontend", "craft"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 16, 9, 35, tzinfo=UTC),
        "mood": "☕",
    },
    {
        "slug": "ui-is-editing",
        "title": "界面设计本质上也像编辑",
        "summary": "不是一味往里放内容，而是不断删去那些不该留下的句子。",
        "body": (
            "界面里每一个边界、间距和按钮文案，都像是在替用户做一次编辑判断。真正困难的不是加什么，"
            "而是删掉什么之后页面依然成立。"
        ),
        "tags": ["ui", "editing"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 15, 9, 10, tzinfo=UTC),
        "mood": "✂️",
    },
    {
        "slug": "soft-motion-note",
        "title": "柔一点的动效会更耐看",
        "summary": "同样的位移，稍微慢一点、轻一点，页面气氛就会完全不同。",
        "body": (
            "最近越来越喜欢那些不抢戏的动效。它们不会立刻让人注意到，但会让整页的节奏变得更顺，"
            "像把一个句子的停顿放在了更对的位置。"
        ),
        "tags": ["motion", "frontend"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 13, 22, 40, tzinfo=UTC),
        "mood": "🌫️",
    },
    {
        "slug": "tiny-delight-matters",
        "title": "那些很小的愉悦其实很重要",
        "summary": "比如图标对齐一像素，比如 hover 之后多出来的一点呼吸。",
        "body": (
            "产品里真正留下来的记忆，很多时候都不是功能本身，而是那个刚刚好的小瞬间。它也许很小，"
            "但会让人觉得这个界面是被认真照顾过的。"
        ),
        "tags": ["details", "product"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 12, 20, 15, tzinfo=UTC),
        "mood": "✨",
    },
    {
        "slug": "interface-is-tone",
        "title": "界面其实也有语气",
        "summary": "同样一句提示，用什么排版、间距和色彩说出来，感觉完全不同。",
        "body": (
            "我越来越相信，界面不是纯信息容器，它也在说话。它的语气来自字重、留白、层级、边界和动效的速度，"
            "这些东西会一起决定用户感受到的是催促还是邀请。"
        ),
        "tags": ["tone", "writing"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 10, 8, 25, tzinfo=UTC),
        "mood": "🫧",
    },
    {
        "slug": "shipping-beats-polish",
        "title": "先落地，再打磨",
        "summary": "很多细节只有真正上线之后，才知道值不值得继续抛光。",
        "body": (
            "不是说打磨不重要，而是有些判断必须在真实使用里完成。先把结构搭起来，再去看哪里值得继续投入，"
            "这比把每个角落都提前磨到极致更可靠。"
        ),
        "tags": ["shipping", "workflow"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 8, 17, 50, tzinfo=UTC),
        "mood": "🛠️",
    },
]

DEFAULT_EXCERPTS = [
    {
        "slug": "harmony-in-blank-space",
        "title": "关于留白的节选",
        "summary": "留白不是空，而是给观看者留下参与意义生成的空间。",
        "body": "最好的设计往往不是把每一个角落都填满，而是知道在哪里停下来。那个停顿本身，会让画面从有限延伸到无限。",
        "tags": ["reading", "aesthetics"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 17, 8, 0, tzinfo=UTC),
        "author_name": "李欧梵",
        "source": "《中国现代文学与现代性十讲》",
    },
    {
        "slug": "good-design-note",
        "title": "少，但更好",
        "summary": "不是少做东西，而是把非必要部分真正拿掉。",
        "body": (
            "当一个界面去掉多余装饰之后，剩下的层级、边界和节奏都会被放大。"
            "所以极简不是偷懒，而是把判断压力提前放回设计者自己身上。"
        ),
        "tags": ["reading", "minimalism"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 15, 11, 30, tzinfo=UTC),
        "author_name": "Dieter Rams",
        "source": "Less but Better",
    },
    {
        "slug": "repeat-has-power",
        "title": "重复本身的力量",
        "summary": "真正改变人的，通常不是瞬间爆发，而是长期重复。",
        "body": "写作、设计、编程这些事，其实都依赖节律。你不断重复某种动作，慢慢就会在里面长出属于自己的结构和判断。",
        "tags": ["writing", "habits"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 12, 19, 45, tzinfo=UTC),
        "author_name": "村上春树",
        "source": "《我的职业是小说家》",
    },
    {
        "slug": "slow-work-note",
        "title": "慢工并不等于迟钝",
        "summary": "真正慢下来时，你反而会更清楚自己为什么这么做。",
        "body": (
            "所谓慢，不是拖延，而是在每个决定落下之前，给它一点真正被看见的时间。"
            "很多表面上的效率，其实只是把判断推迟到更后面。"
        ),
        "tags": ["reading", "pace"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 10, 14, 10, tzinfo=UTC),
        "author_name": "约翰·伯格",
        "source": "《观看之道》",
    },
    {
        "slug": "poetry-and-interface",
        "title": "界面也需要一点诗意",
        "summary": "不是为了装饰，而是为了让理性之外还留一点呼吸。",
        "body": (
            "当设计只剩功能和效率，它当然能运转，但不一定能被喜欢。诗意不是多余物，"
            "它是让系统从“可用”转向“愿意停留”的那一层温度。"
        ),
        "tags": ["reading", "interface"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 8, 11, 5, tzinfo=UTC),
        "author_name": "原研哉",
        "source": "《设计中的设计》",
    },
    {
        "slug": "honest-materials",
        "title": "材料应该诚实地被使用",
        "summary": "数字界面也一样，视觉语言不该伪装自己是什么。",
        "body": (
            "当一种材料被过度装饰，它原有的特质反而会消失。界面中的玻璃、纸感、金属感也应该如此，"
            "关键不在像不像，而在它是否帮助用户理解层级与关系。"
        ),
        "tags": ["materials", "design"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 6, 10, 0, tzinfo=UTC),
        "author_name": "彼得·卒姆托",
        "source": "《思考建筑》",
    },
    {
        "slug": "quiet-systems",
        "title": "好的系统通常是安静的",
        "summary": "它不会一直提醒你自己存在，但会在需要的时候稳稳接住。",
        "body": "系统感并不意味着强烈的控制感。相反，真正成熟的结构往往很轻，它只是在背后默默让内容和行为都有了位置。",
        "tags": ["systems", "product"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 4, 9, 25, tzinfo=UTC),
        "author_name": "唐纳德·诺曼",
        "source": "《设计心理学》",
    },
]

DEFAULT_FRIENDS = [
    {
        "name": "Miku's Blog",
        "url": "https://miku.example.com",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Miku",
        "description": "记录生活与技术的小站",
        "status": "active",
        "order_index": 0,
    },
    {
        "name": "AkaraChen",
        "url": "https://akara.example.com",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Akara",
        "description": "位于互联网边缘的小站。",
        "status": "active",
        "order_index": 1,
    },
    {
        "name": "夏目的博客",
        "url": "https://natsume.example.com",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Natsume",
        "description": "总有人间一两风，填我十万八千梦。",
        "status": "active",
        "order_index": 2,
    },
    {
        "name": "保罗的小宇宙",
        "url": "https://paul.example.com",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Paul",
        "description": "Still single, still waiting...",
        "status": "active",
        "order_index": 3,
    },
    {
        "name": "猫羽のブログ",
        "url": "https://nekoha.example.com",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Nekoha",
        "description": "空中有颗星为你而亮",
        "status": "active",
        "order_index": 4,
    },
    {
        "name": "Erhecy's Blog",
        "url": "https://erhecy.example.com",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Erhecy",
        "description": "欢迎来到咱的博客！",
        "status": "active",
        "order_index": 5,
    },
    {
        "name": "轻雅阁",
        "url": "https://qingya.example.com",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Qingya",
        "description": "新时代教师的日常",
        "status": "active",
        "order_index": 6,
    },
    {
        "name": "柏园猫のBlog",
        "url": "https://baiyuan.example.com",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=BaiYuan",
        "description": "人与人虽然相距遥远，但又彼此相依",
        "status": "active",
        "order_index": 7,
    },
    {
        "name": "Lucifer's Blog",
        "url": "https://lucifer.example.com",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=Lucifer",
        "description": "Keep moving",
        "status": "active",
        "order_index": 8,
    },
    {
        "name": "Quiet Terminal",
        "url": "https://quiet-terminal.example.com",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=QuietTerminal",
        "description": "偶尔更新系统、Linux 和小工具。",
        "status": "active",
        "order_index": 9,
    },
    {
        "name": "Sunset Archive",
        "url": "https://sunset-archive.example.com",
        "avatar_url": "https://api.dicebear.com/9.x/notionists/svg?seed=SunsetArchive",
        "description": "停更中的旧站，但还留着一些文章。",
        "status": "archived",
        "order_index": 10,
    },
]

DEFAULT_FRIEND_FEED_SOURCES = [
    {
        "friend_name": "Miku's Blog",
        "feed_url": "https://miku.example.com/feed.xml",
        "last_fetched_at": datetime(2026, 3, 16, 9, 0, tzinfo=UTC),
        "is_enabled": True,
    },
    {
        "friend_name": "AkaraChen",
        "feed_url": "https://akara.example.com/rss.xml",
        "last_fetched_at": datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
        "is_enabled": True,
    },
    {
        "friend_name": "夏目的博客",
        "feed_url": "https://natsume.example.com/atom.xml",
        "last_fetched_at": datetime(2026, 3, 18, 10, 0, tzinfo=UTC),
        "is_enabled": True,
    },
    {
        "friend_name": "保罗的小宇宙",
        "feed_url": "https://paul.example.com/feed.xml",
        "last_fetched_at": datetime(2026, 3, 16, 21, 0, tzinfo=UTC),
        "is_enabled": True,
    },
    {
        "friend_name": "猫羽のブログ",
        "feed_url": "https://nekoha.example.com/feed.xml",
        "last_fetched_at": datetime(2026, 3, 19, 13, 0, tzinfo=UTC),
        "is_enabled": True,
    },
    {
        "friend_name": "Erhecy's Blog",
        "feed_url": "https://erhecy.example.com/feed.xml",
        "last_fetched_at": datetime(2026, 3, 18, 18, 0, tzinfo=UTC),
        "is_enabled": True,
    },
    {
        "friend_name": "轻雅阁",
        "feed_url": "https://qingya.example.com/feed.xml",
        "last_fetched_at": datetime(2026, 3, 18, 7, 0, tzinfo=UTC),
        "is_enabled": True,
    },
    {
        "friend_name": "柏园猫のBlog",
        "feed_url": "https://baiyuan.example.com/feed.xml",
        "last_fetched_at": datetime(2026, 3, 17, 22, 0, tzinfo=UTC),
        "is_enabled": True,
    },
    {
        "friend_name": "Lucifer's Blog",
        "feed_url": "https://lucifer.example.com/feed.xml",
        "last_fetched_at": datetime(2026, 3, 17, 20, 0, tzinfo=UTC),
        "is_enabled": True,
    },
    {
        "friend_name": "Quiet Terminal",
        "feed_url": "https://quiet-terminal.example.com/feed.xml",
        "last_fetched_at": datetime(2026, 3, 19, 11, 0, tzinfo=UTC),
        "is_enabled": False,
    },
    {
        "friend_name": "Sunset Archive",
        "feed_url": "https://sunset-archive.example.com/feed.xml",
        "last_fetched_at": datetime(2026, 3, 20, 8, 0, tzinfo=UTC),
        "is_enabled": True,
    },
]

DEFAULT_FRIEND_FEED_ITEMS = [
    {
        "friend_name": "Miku's Blog",
        "title": "“糖”",
        "url": "https://miku.example.com/posts/candy",
        "summary": "一篇关于日常感受的短文。",
        "published_at": datetime(2026, 3, 16, 8, 30, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "AkaraChen",
        "title": "如何使用 Cloudflare API 为网站新增数据监测大屏",
        "url": "https://akara.example.com/posts/cloudflare-dashboard",
        "summary": "记录一次网站数据面板搭建过程。",
        "published_at": datetime(2026, 3, 10, 11, 0, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "夏目的博客",
        "title": "网络流算法详解",
        "url": "https://natsume.example.com/posts/network-flow",
        "summary": "把几类经典网络流题型梳理成一份笔记。",
        "published_at": datetime(2026, 3, 18, 9, 30, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "Erhecy's Blog",
        "title": "在博客中优雅地添加 Bilibili 追番页面",
        "url": "https://erhecy.example.com/posts/bilibili-following",
        "summary": "记录一次追番页面和数据同步的实现过程。",
        "published_at": datetime(2026, 3, 13, 18, 45, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "柏园猫のBlog",
        "title": "一招解决 Origin 运行报错：找不到 mfc140u.dll",
        "url": "https://baiyuan.example.com/posts/fix-mfc140u",
        "summary": "整理一次桌面软件依赖缺失的排查记录。",
        "published_at": datetime(2026, 3, 11, 8, 20, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "保罗的小宇宙",
        "title": "Hand Motion Retargeting",
        "url": "https://paul.example.com/posts/hand-motion-retargeting",
        "summary": "记录手部动作重定向的一些实验。",
        "published_at": datetime(2026, 3, 10, 16, 10, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "Lucifer's Blog",
        "title": "To panic! or Not to panic!",
        "url": "https://lucifer.example.com/posts/to-panic-or-not",
        "summary": "关于错误恢复和调试心态的一篇记录。",
        "published_at": datetime(2026, 3, 10, 14, 25, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "轻雅阁",
        "title": "碎碎念：找实习、生病与一块薯饼的治愈",
        "url": "https://qingya.example.com/posts/internship-and-hashbrown",
        "summary": "把最近一段时间的生活碎片整理成一篇短文。",
        "published_at": datetime(2026, 3, 10, 9, 50, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "猫羽のブログ",
        "title": "AI 时代的重构方式：从 RFC 到五个 Plan",
        "url": "https://nekoha.example.com/posts/ai-refactor-rfc-plan",
        "summary": "记录一次多人并行协作下的重构节奏。",
        "published_at": datetime(2026, 3, 10, 8, 40, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "柏园猫のBlog",
        "title": "使用 Python 绘制中国省份管网老化分布地图",
        "url": "https://baiyuan.example.com/posts/pipeline-aging-map",
        "summary": "一次数据可视化小练习。",
        "published_at": datetime(2026, 3, 6, 16, 30, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "猫羽のブログ",
        "title": "键盘上的春节",
        "url": "https://nekoha.example.com/posts/spring-festival-on-keyboard",
        "summary": "把节日气息写进键帽与输入法里。",
        "published_at": datetime(2026, 3, 2, 11, 15, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "保罗的小宇宙",
        "title": "TraceDiary 开发复盘：我如何并行协作 4 个 Agent",
        "url": "https://paul.example.com/posts/tracediary-retro",
        "summary": "一次 Agent 并行协作开发的过程记录。",
        "published_at": datetime(2026, 2, 27, 20, 10, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "AkaraChen",
        "title": "Astrbot / 夕颜是如何炼成的",
        "url": "https://akara.example.com/posts/astrbot-build-log",
        "summary": "一次机器人项目从想法到落地的复盘。",
        "published_at": datetime(2026, 2, 27, 18, 20, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "保罗的小宇宙",
        "title": "我用 Vibe Coding 开发了一个照片标注工具 ImgStamp",
        "url": "https://paul.example.com/posts/imgstamp",
        "summary": "一个小工具项目的从零到一。",
        "published_at": datetime(2026, 2, 26, 21, 5, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "AkaraChen",
        "title": "Gravatar Mirror",
        "url": "https://akara.example.com/posts/gravatar-mirror",
        "summary": "给头像服务做一次加速与镜像。",
        "published_at": datetime(2026, 2, 25, 9, 0, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "Quiet Terminal",
        "title": "这篇不会出现在公开接口里",
        "url": "https://quiet-terminal.example.com/posts/private-feed-entry",
        "summary": "用于验证禁用 feed source 不会被 public API 返回。",
        "published_at": datetime(2026, 3, 19, 10, 30, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
    {
        "friend_name": "Sunset Archive",
        "title": "归档站点的旧文章",
        "url": "https://sunset-archive.example.com/posts/archive-note",
        "summary": "用于验证 archived 友链不会出现在 public feed。",
        "published_at": datetime(2026, 3, 20, 7, 45, tzinfo=UTC),
        "raw_payload": {"source": "seed"},
    },
]

DEFAULT_LEGACY_GUESTBOOK_ENTRIES = [
    {
        "name": "Elena Torres",
        "email": "elena@example.com",
        "website": "https://elena.example.com",
        "body": "你的博客设计真的很稳，评论区换成现在这套以后，整体气质终于统一起来了。",
        "status": "approved",
        "created_at": datetime(2026, 3, 21, 10, 0, tzinfo=UTC),
    },
    {
        "name": "新访客",
        "email": None,
        "website": None,
        "body": "测试一条待审核留言，方便在后台里看见 pending 状态。",
        "status": "pending",
        "created_at": datetime(2026, 3, 21, 10, 30, tzinfo=UTC),
    },
]

DEFAULT_LEGACY_COMMENTS = [
    {
        "key": "legacy-post-root",
        "content_type": "posts",
        "content_slug": "from-zero-design-system",
        "author_name": "林小北",
        "author_email": "linxiaobei@example.com",
        "body": (
            "写得真好，尤其是关于节奏感的那段，让我重新想了一遍自己的排版系统。支持 **Markdown** 的评论区看着顺手多了。"
        ),
        "status": "approved",
        "created_at": datetime(2026, 3, 20, 8, 30, tzinfo=UTC),
        "parent_key": None,
    },
    {
        "key": "legacy-post-reply",
        "content_type": "posts",
        "content_slug": "from-zero-design-system",
        "author_name": "Felix",
        "author_email": None,
        "body": "谢谢，你这句“排版系统”很精准。我后面也想把评论区的样式继续收得更稳一些。",
        "status": "approved",
        "created_at": datetime(2026, 3, 20, 9, 5, tzinfo=UTC),
        "parent_key": "legacy-post-root",
    },
    {
        "key": "legacy-post-second",
        "content_type": "posts",
        "content_slug": "liquid-glass-css-notes",
        "author_name": "Kai Nakamura",
        "author_email": "kai@example.com",
        "body": "这一篇的性能部分很有用。`backdrop-filter` 一旦铺太大，低端设备确实会立刻吃不消。",
        "status": "approved",
        "created_at": datetime(2026, 3, 20, 11, 20, tzinfo=UTC),
        "parent_key": None,
    },
    {
        "key": "legacy-diary-root",
        "content_type": "diary",
        "content_slug": "spring-equinox-and-warm-light",
        "author_name": "纸鹤",
        "author_email": None,
        "body": "这篇日记读起来很有画面感，尤其是“夜风里有隐约的花香”这一句。",
        "status": "approved",
        "created_at": datetime(2026, 3, 20, 21, 10, tzinfo=UTC),
        "parent_key": None,
    },
]

DEFAULT_WALINE_COMMENTS = [
    {
        "key": "waline-post-root",
        "url": "/posts/from-zero-design-system",
        "nick": "林小北",
        "mail": "linxiaobei@example.com",
        "link": None,
        "comment": (
            "写得真好，尤其是关于节奏感的那段，让我重新想了一遍自己的排版系统。支持 **Markdown** 的评论区看着顺手多了。"
        ),
        "status": "approved",
        "created_at": datetime(2026, 3, 20, 8, 30, tzinfo=UTC),
        "parent_key": None,
    },
    {
        "key": "waline-post-reply",
        "url": "/posts/from-zero-design-system",
        "nick": "Felix",
        "mail": None,
        "link": None,
        "comment": "谢谢，你这句“排版系统”很精准。我后面也想把评论区的样式继续收得更稳一些。",
        "status": "approved",
        "created_at": datetime(2026, 3, 20, 9, 5, tzinfo=UTC),
        "parent_key": "waline-post-root",
    },
    {
        "key": "waline-post-second",
        "url": "/posts/liquid-glass-css-notes",
        "nick": "Kai Nakamura",
        "mail": "kai@example.com",
        "link": "https://kai.example.com",
        "comment": "这一篇的性能部分很有用。`backdrop-filter` 一旦铺太大，低端设备确实会立刻吃不消。",
        "status": "approved",
        "created_at": datetime(2026, 3, 20, 11, 20, tzinfo=UTC),
        "parent_key": None,
    },
    {
        "key": "waline-diary-root",
        "url": "/diary/spring-equinox-and-warm-light",
        "nick": "纸鹤",
        "mail": None,
        "link": None,
        "comment": "这篇日记读起来很有画面感，尤其是“夜风里有隐约的花香”这一句。",
        "status": "approved",
        "created_at": datetime(2026, 3, 20, 21, 10, tzinfo=UTC),
        "parent_key": None,
    },
    {
        "key": "waline-guestbook-root",
        "url": "/guestbook",
        "nick": "Elena Torres",
        "mail": "elena@example.com",
        "link": "https://elena.example.com",
        "comment": "你的博客设计真的很稳，评论区换成现在这套以后，整体气质终于统一起来了。",
        "status": "approved",
        "created_at": datetime(2026, 3, 21, 10, 0, tzinfo=UTC),
        "parent_key": None,
    },
    {
        "key": "waline-guestbook-pending",
        "url": "/guestbook",
        "nick": "新访客",
        "mail": None,
        "link": None,
        "comment": "测试一条待审核留言，方便在后台里看见 pending 状态。",
        "status": "waiting",
        "created_at": datetime(2026, 3, 21, 10, 30, tzinfo=UTC),
        "parent_key": None,
    },
]

DEFAULT_REACTIONS = [
    {
        "content_type": "posts",
        "content_slug": "from-zero-design-system",
        "reaction_type": "like",
        "client_token": "Elena Torres",
    },
    {
        "content_type": "posts",
        "content_slug": "from-zero-design-system",
        "reaction_type": "like",
        "client_token": "Kai Nakamura",
    },
    {
        "content_type": "diary",
        "content_slug": "spring-equinox-and-warm-light",
        "reaction_type": "like",
        "client_token": "David Okoro",
    },
]


def _build_default_waline_counters() -> list[dict[str, object]]:
    reaction_counts = Counter(
        build_comment_path(str(item["content_type"]), str(item["content_slug"]))
        for item in DEFAULT_REACTIONS
        if str(item["reaction_type"]) == "like"
    )
    counters: list[dict[str, object]] = []
    for content_type, entries in (
        ("posts", DEFAULT_POSTS),
        ("diary", DEFAULT_DIARY_ENTRIES),
        ("thoughts", DEFAULT_THOUGHTS),
        ("excerpts", DEFAULT_EXCERPTS),
    ):
        for entry in entries:
            path = build_comment_path(content_type, str(entry["slug"]))
            counters.append(
                {
                    "url": path,
                    "time": int(entry.get("view_count", 0) or 0),
                    "reaction0": reaction_counts.get(path, 0),
                }
            )
    return counters


DEFAULT_WALINE_COUNTERS = _build_default_waline_counters()

DEFAULT_TRAFFIC_SNAPSHOT_SERIES = {
    "/": [96, 108, 118, 126, 140, 152, 164, 171, 186, 201, 215, 238, 252, 276],
    "/posts/from-zero-design-system": [34, 38, 42, 47, 51, 56, 61, 66, 72, 78, 85, 93, 101, 112],
    "/posts/crafting-an-editorial-homepage": [18, 21, 25, 29, 33, 36, 40, 43, 47, 52, 57, 63, 68, 74],
    "/diary/spring-equinox-and-warm-light": [9, 11, 12, 15, 16, 18, 20, 21, 24, 25, 27, 30, 32, 35],
    "/thoughts/small-routines-build-better-systems": [7, 8, 10, 10, 12, 13, 15, 16, 16, 18, 19, 20, 22, 24],
    "/excerpts/quiet-rhythm-and-better-interfaces": [5, 6, 7, 8, 9, 10, 11, 11, 12, 13, 14, 15, 16, 18],
}

DEFAULT_TRAFFIC_REACTION_SERIES = {
    "/": [3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7, 7, 8],
    "/posts/from-zero-design-system": [1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 5],
    "/posts/crafting-an-editorial-homepage": [0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3],
    "/diary/spring-equinox-and-warm-light": [0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 2, 2],
    "/thoughts/small-routines-build-better-systems": [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1],
    "/excerpts/quiet-rhythm-and-better-interfaces": [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
}


def _build_default_traffic_snapshots() -> list[dict[str, object]]:
    today = datetime.now(UTC).date()
    snapshots: list[dict[str, object]] = []
    for url, cumulative_views in DEFAULT_TRAFFIC_SNAPSHOT_SERIES.items():
        cumulative_reactions = DEFAULT_TRAFFIC_REACTION_SERIES.get(url, [0] * len(cumulative_views))
        previous_views = 0
        for index, total_views in enumerate(cumulative_views):
            snapshot_date = today - timedelta(days=len(cumulative_views) - index - 1)
            daily_views = total_views - previous_views
            previous_views = total_views
            snapshots.append(
                {
                    "snapshot_date": snapshot_date,
                    "url": url,
                    "cumulative_views": total_views,
                    "daily_views": daily_views,
                    "cumulative_reactions": cumulative_reactions[index] if index < len(cumulative_reactions) else 0,
                }
            )
    return snapshots


DEFAULT_TRAFFIC_SNAPSHOTS = _build_default_traffic_snapshots()


def _is_empty(session: Session, model) -> bool:  # type: ignore[no-untyped-def]
    return session.scalar(select(func.count(model.id))) == 0


def _clear_seed_data(session: Session) -> None:
    """Delete all seed data to allow a clean reseed. Development only."""
    _logger = logging.getLogger("aerisun.seed")
    _logger.info("Force reseed: clearing existing seed data...")
    for model in [
        Comment,
        GuestbookEntry,
        Reaction,
        FriendFeedItem,
        FriendFeedSource,
        Friend,
        ResumeExperience,
        ResumeSkillGroup,
        ResumeBasics,
        NavItem,
        PageDisplayOption,
        PageCopy,
        Poem,
        SocialLink,
        CommunityConfig,
        SiteProfile,
        PostEntry,
        DiaryEntry,
        ThoughtEntry,
        ExcerptEntry,
        Asset,
        TrafficDailySnapshot,
        VisitRecord,
        AdminUser,
    ]:
        count = session.query(model).delete()
        if count:
            _logger.info("  Cleared %d rows from %s", count, model.__tablename__)
    session.flush()


def _seed_content_entries(session: Session, model, entries: list[dict]) -> None:  # type: ignore[no-untyped-def]
    existing_slugs = set(session.scalars(select(model.slug)).all())
    missing_entries = [entry for entry in entries if entry["slug"] not in existing_slugs]
    if missing_entries:
        session.add_all([model(**entry) for entry in missing_entries])


def _merge_page_copy(existing: PageCopy, default_item: dict) -> bool:
    changed = False
    scalar_fields = (
        "label",
        "nav_label",
        "title",
        "subtitle",
        "description",
        "search_placeholder",
        "empty_message",
        "max_width",
        "page_size",
        "download_label",
    )
    for field in scalar_fields:
        current_value = getattr(existing, field)
        default_value = default_item.get(field)
        if current_value is None and default_value is not None:
            setattr(existing, field, default_value)
            changed = True

    default_extras = default_item.get("extras") or {}
    existing_extras = dict(existing.extras or {})
    for key, value in default_extras.items():
        if key not in existing_extras or existing_extras[key] in (None, ""):
            existing_extras[key] = value
            changed = True

    if existing.page_key == "calendar" and existing_extras.get("weekdayLabels") == [
        "周日",
        "周一",
        "周二",
        "周三",
        "周四",
        "周五",
        "周六",
    ]:
        existing_extras["weekdayLabels"] = default_extras.get("weekdayLabels", existing_extras["weekdayLabels"])

        changed = True

    if changed:
        existing.extras = existing_extras
    return changed


def _seed_missing_page_copies(session: Session) -> None:
    existing_by_key = {page_copy.page_key: page_copy for page_copy in session.scalars(select(PageCopy)).all()}

    for item in DEFAULT_PAGE_COPIES:
        page_copy = existing_by_key.get(item["page_key"])
        if page_copy is None:
            session.add(PageCopy(**item))
            continue
        _merge_page_copy(page_copy, item)


def _seed_missing_page_options(session: Session) -> None:
    existing_keys = set(session.scalars(select(PageDisplayOption.page_key)).all())
    missing_items = [item for item in DEFAULT_PAGE_OPTIONS if item["page_key"] not in existing_keys]
    if missing_items:
        session.add_all([PageDisplayOption(**item) for item in missing_items])


def _seed_social_data(session: Session) -> None:
    friends_by_name = {friend.name: friend for friend in session.scalars(select(Friend)).all()}

    for item in DEFAULT_FRIENDS:
        friend = friends_by_name.get(item["name"])
        if friend is None:
            friend = Friend(**item)
            session.add(friend)
            session.flush()
            friends_by_name[friend.name] = friend
            continue

        if not friend.description:
            friend.description = item["description"]
        if not friend.avatar_url:
            friend.avatar_url = item["avatar_url"]
        if not friend.url:
            friend.url = item["url"]
        if friend.status in {"", "pending"}:
            friend.status = item["status"]
        if friend.order_index == 0:
            friend.order_index = item["order_index"]

    sources_by_name = {
        friend.name: source
        for source, friend in session.execute(
            select(FriendFeedSource, Friend).join(Friend, FriendFeedSource.friend_id == Friend.id)
        ).all()
    }
    for item in DEFAULT_FRIEND_FEED_SOURCES:
        source = sources_by_name.get(item["friend_name"])
        if source is None:
            source = FriendFeedSource(
                friend_id=friends_by_name[item["friend_name"]].id,
                feed_url=item["feed_url"],
                last_fetched_at=item["last_fetched_at"],
                is_enabled=item["is_enabled"],
            )
            session.add(source)
            session.flush()
            sources_by_name[item["friend_name"]] = source
            continue

        if not source.feed_url:
            source.feed_url = item["feed_url"]
        if source.last_fetched_at is None:
            source.last_fetched_at = item["last_fetched_at"]

    existing_feed_urls = set(session.scalars(select(FriendFeedItem.url)).all())
    missing_feed_items = [item for item in DEFAULT_FRIEND_FEED_ITEMS if item["url"] not in existing_feed_urls]

    if missing_feed_items:
        session.add_all(
            [
                FriendFeedItem(
                    source_id=sources_by_name[item["friend_name"]].id,
                    title=item["title"],
                    url=item["url"],
                    summary=item["summary"],
                    published_at=item["published_at"],
                    raw_payload=item["raw_payload"],
                )
                for item in missing_feed_items
            ]
        )


def _seed_engagement_data(session: Session) -> None:
    existing_reactions = {
        (item.content_type, item.content_slug, item.reaction_type, item.client_token)
        for item in session.scalars(select(Reaction)).all()
    }
    missing_reactions = [
        item
        for item in DEFAULT_REACTIONS
        if (
            item["content_type"],
            item["content_slug"],
            item["reaction_type"],
            item["client_token"],
        )
        not in existing_reactions
    ]
    if missing_reactions:
        session.add_all([Reaction(**item) for item in missing_reactions])


def _seed_traffic_snapshot_data(session: Session) -> None:
    existing = session.scalar(select(func.count(TrafficDailySnapshot.id)))
    if existing and int(existing) > 0:
        return

    session.add_all([TrafficDailySnapshot(**item) for item in DEFAULT_TRAFFIC_SNAPSHOTS])


def _seed_visit_record_data(session: Session) -> None:
    existing = session.scalar(select(func.count(VisitRecord.id)))
    if existing and int(existing) > 0:
        return

    now = datetime.now(UTC)
    sample = []
    ip_pool = [
        "203.0.113.10",
        "203.0.113.11",
        "203.0.113.12",
        "198.51.100.7",
        "198.51.100.8",
    ]
    paths = [
        "/",
        "/posts/from-zero-design-system",
        "/posts/crafting-an-editorial-homepage",
        "/posts/liquid-glass-css-notes",
        "/diary/spring-equinox-and-warm-light",
        "/thoughts/small-routines-build-better-systems",
        "/resume",
        "/friends",
        "/guestbook",
    ]

    # 过去 14 天：按天生成一点“像真的”的访问分布
    for day_offset in range(14):
        day = now - timedelta(days=13 - day_offset)
        visits_today = 3 + (day_offset % 6)  # 3..8
        for idx in range(visits_today):
            path = paths[(day_offset * 3 + idx) % len(paths)]
            ip = ip_pool[(day_offset + idx) % len(ip_pool)]
            sample.append(
                VisitRecord(
                    visited_at=day.replace(hour=(9 + idx) % 24, minute=(idx * 7) % 60, second=0, microsecond=0),
                    path=path,
                    ip_address=ip,
                    user_agent="Mozilla/5.0 (Seed) AppleWebKit/537.36",
                    referer="https://example.com" if idx % 3 == 0 else None,
                    status_code=200,
                    duration_ms=60 + (idx * 23) % 240,
                    is_bot=False,
                )
            )

    # 加一条 bot（默认统计会过滤）
    sample.append(
        VisitRecord(
            visited_at=now - timedelta(hours=6),
            path="/robots.txt",
            ip_address="192.0.2.66",
            user_agent="Googlebot/2.1 (+http://www.google.com/bot.html)",
            referer=None,
            status_code=200,
            duration_ms=20,
            is_bot=True,
        )
    )

    session.add_all(sample)


def _seed_legacy_guestbook_data(session: Session) -> None:
    if not _is_empty(session, GuestbookEntry):
        return

    session.add_all([GuestbookEntry(**item) for item in DEFAULT_LEGACY_GUESTBOOK_ENTRIES])


def _seed_legacy_comment_data(session: Session) -> None:
    if not _is_empty(session, Comment):
        return

    inserted_ids: dict[str, str] = {}
    for item in DEFAULT_LEGACY_COMMENTS:
        parent_key = item.get("parent_key")
        parent_id = inserted_ids.get(str(parent_key)) if parent_key else None
        comment = Comment(
            content_type=str(item["content_type"]),
            content_slug=str(item["content_slug"]),
            parent_id=parent_id,
            author_name=str(item["author_name"]),
            author_email=str(item["author_email"]) if item.get("author_email") is not None else None,
            body=str(item["body"]),
            status=str(item["status"]),
            created_at=item["created_at"],  # type: ignore[arg-type]
            updated_at=item["created_at"],  # type: ignore[arg-type]
        )
        session.add(comment)
        session.flush()
        inserted_ids[str(item["key"])] = comment.id


def _clear_waline_seed_data() -> None:
    _logger = logging.getLogger("aerisun.seed")
    _logger.info("Force reseed: clearing existing Waline seed data...")
    with connect_waline_db() as connection:
        connection.execute("DELETE FROM wl_comment")
        connection.execute("DELETE FROM wl_counter")
        connection.execute("DELETE FROM sqlite_sequence WHERE name IN ('wl_comment', 'wl_counter')")
        connection.commit()


def _insert_waline_seed_comment(connection, item: dict[str, object], inserted_ids: dict[str, int]) -> int:  # type: ignore[no-untyped-def]
    parent_key = item.get("parent_key")
    parent_id = inserted_ids.get(str(parent_key)) if parent_key else None
    root_id = parent_id
    if parent_id is not None:
        root_row = connection.execute("SELECT rid FROM wl_comment WHERE id = ?", (parent_id,)).fetchone()
        root_id = int(root_row["rid"]) if root_row and root_row["rid"] is not None else parent_id

    row = make_waline_comment_row(
        comment=str(item["comment"]),
        nick=str(item["nick"]),
        mail=str(item["mail"]) if item.get("mail") is not None else None,
        link=str(item["link"]) if item.get("link") is not None else None,
        status=str(item["status"]),
        url=str(item["url"]),
        parent_id=parent_id,
        root_id=root_id,
        created_at=item["created_at"],  # type: ignore[arg-type]
        updated_at=item["created_at"],  # type: ignore[arg-type]
        inserted_at=item["created_at"],  # type: ignore[arg-type]
    )
    cursor = connection.execute(
        """
        INSERT INTO wl_comment (
            user_id, comment, insertedAt, ip, link, mail, nick, pid, rid,
            sticky, status, "like", ua, url, createdAt, updatedAt
        ) VALUES (
            :user_id, :comment, :insertedAt, :ip, :link, :mail, :nick, :pid, :rid,
            :sticky, :status, :like, :ua, :url, :createdAt, :updatedAt
        )
        """,
        row,
    )
    comment_id = int(cursor.lastrowid)
    if parent_id is None:
        connection.execute("UPDATE wl_comment SET rid = ? WHERE id = ?", (comment_id, comment_id))
    inserted_ids[str(item["key"])] = comment_id
    return comment_id


def _seed_waline_comment_data() -> None:
    with connect_waline_db() as connection:
        existing = connection.execute("SELECT COUNT(*) FROM wl_comment").fetchone()
        if existing and int(existing[0]) > 0:
            return

        inserted_ids: dict[str, int] = {}
        for item in DEFAULT_WALINE_COMMENTS:
            _insert_waline_seed_comment(connection, item, inserted_ids)

        connection.commit()


def _seed_dev_admin(session: Session) -> None:
    """Create a default admin account in development mode (admin / admin123)."""
    settings = get_settings()
    if settings.environment != "development":
        return
    if not _is_empty(session, AdminUser):
        return
    password_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
    session.add(AdminUser(username="admin", password_hash=password_hash))


def _seed_waline_counter_data() -> None:
    with connect_waline_db() as connection:
        existing = connection.execute("SELECT COUNT(*) FROM wl_counter").fetchone()
        if existing and int(existing[0]) > 0:
            return

        for item in DEFAULT_WALINE_COUNTERS:
            connection.execute(
                """
                INSERT INTO wl_counter (
                    time, reaction0, reaction1, reaction2, reaction3, reaction4,
                    reaction5, reaction6, reaction7, reaction8, url
                ) VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0, ?)
                """,
                (int(item["time"]), int(item["reaction0"]), str(item["url"])),
            )

        connection.commit()


def seed_reference_data(*, force: bool = False) -> None:
    settings = get_settings()
    settings.ensure_directories()
    init_db()
    session = get_session_factory()()
    try:
        if force:
            _clear_seed_data(session)
            _clear_waline_seed_data()

        frontend_public_dir = BACKEND_ROOT.parent / "frontend" / "public"
        frontend_public_images = frontend_public_dir / "images"
        seeded_og_image = _ensure_seed_asset(
            session,
            source_path=frontend_public_images / "hero_bg.jpeg",
            category="site-og",
            note="站点默认 OG 分享图（seed 初始化）",
        )
        seeded_site_icon = _ensure_seed_asset(
            session,
            source_path=frontend_public_dir / "favicon.svg",
            category="site-icon",
            note="站点默认标签页图标（seed 初始化）",
        )
        seeded_hero_image = _ensure_seed_asset(
            session,
            source_path=frontend_public_images / "avatar.webp",
            category="hero-image",
            note="首页 Hero 默认视觉图（seed 初始化）",
        )
        seeded_hero_poster = _ensure_seed_asset(
            session,
            source_path=frontend_public_images / "hero_bg.jpeg",
            category="hero-poster",
            note="首页 Hero 视频默认封面图（seed 初始化）",
        )
        seeded_resume_avatar = _ensure_seed_asset(
            session,
            source_path=frontend_public_images / "avatar.webp",
            category="resume-avatar",
            note="简历默认头像（seed 初始化）",
        )

        if _is_empty(session, SiteProfile):
            site_payload = {
                **DEFAULT_SITE_PROFILE,
                "og_image": seeded_og_image,
                "site_icon_url": seeded_site_icon,
                "hero_image_url": seeded_hero_image,
                "hero_poster_url": seeded_hero_poster,
            }
            site = SiteProfile(**site_payload)
            session.add(site)
            session.flush()

            session.add_all([SocialLink(site_profile_id=site.id, **item) for item in DEFAULT_SOCIAL_LINKS])
            session.add_all(
                [
                    Poem(site_profile_id=site.id, order_index=index, content=text)
                    for index, text in enumerate(DEFAULT_POEMS)
                ]
            )
            session.add_all([PageCopy(**item) for item in DEFAULT_PAGE_COPIES])
            session.add_all([PageDisplayOption(**item) for item in DEFAULT_PAGE_OPTIONS])
            resume_payload = {**DEFAULT_RESUME, "profile_image_url": seeded_resume_avatar}
            resume = ResumeBasics(**resume_payload)
            session.add(resume)
            session.flush()
            session.add_all([ResumeSkillGroup(resume_basics_id=resume.id, **group) for group in DEFAULT_SKILLS])

            session.add_all(
                [ResumeExperience(resume_basics_id=resume.id, **experience) for experience in DEFAULT_EXPERIENCES]
            )

        _seed_missing_page_copies(session)
        _seed_missing_page_options(session)

        if _is_empty(session, NavItem):
            site = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
            if site is not None:
                label_to_id: dict[str, str] = {}
                # First pass: top-level items
                for item_data in DEFAULT_NAV_ITEMS:
                    if "_parent_label" not in item_data:
                        nav = NavItem(
                            site_profile_id=site.id,
                            label=item_data["label"],
                            href=item_data["href"],
                            page_key=item_data.get("page_key"),
                            trigger=item_data.get("trigger", "none"),
                            order_index=item_data["order_index"],
                        )
                        session.add(nav)
                        session.flush()
                        label_to_id[nav.label] = nav.id
                # Second pass: children
                for item_data in DEFAULT_NAV_ITEMS:
                    if "_parent_label" in item_data:
                        nav = NavItem(
                            site_profile_id=site.id,
                            parent_id=label_to_id[item_data["_parent_label"]],
                            label=item_data["label"],
                            href=item_data["href"],
                            page_key=item_data.get("page_key"),
                            trigger=item_data.get("trigger", "none"),
                            order_index=item_data["order_index"],
                        )
                        session.add(nav)

        _seed_community_config(session)
        _seed_site_auth_config(session)
        _seed_runtime_site_settings(session)

        _seed_content_entries(session, PostEntry, DEFAULT_POSTS)
        _seed_content_entries(session, DiaryEntry, DEFAULT_DIARY_ENTRIES)
        _seed_content_entries(session, ThoughtEntry, DEFAULT_THOUGHTS)
        _seed_content_entries(session, ExcerptEntry, DEFAULT_EXCERPTS)
        _seed_social_data(session)
        _seed_engagement_data(session)
        _seed_traffic_snapshot_data(session)
        _seed_visit_record_data(session)
        _seed_legacy_guestbook_data(session)
        _seed_legacy_comment_data(session)
        _seed_dev_admin(session)
        session.commit()
    finally:
        session.close()

    _seed_waline_comment_data()
    _seed_waline_counter_data()


def main() -> None:
    seed_reference_data()


if __name__ == "__main__":
    main()
