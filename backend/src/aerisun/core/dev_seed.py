from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import logging
import os
import sqlite3
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

import aerisun.domain.automation.models
import aerisun.domain.subscription.models  # noqa: F401
from aerisun.core.db import get_session_factory, init_db
from aerisun.core.seed_steps.common import is_empty
from aerisun.core.seed_steps.content import (
    seed_content_entries,
    seed_missing_page_copies,
)
from aerisun.core.seed_steps.legacy import (
    seed_dev_admin,
    seed_legacy_comment_data,
    seed_legacy_guestbook_data,
)
from aerisun.core.seed_steps.social import (
    seed_engagement_data,
    seed_social_data,
    seed_traffic_snapshot_data,
    seed_visit_record_data,
)
from aerisun.core.seed_steps.system_assets import normalize_core_system_asset_references, seed_core_system_asset_urls
from aerisun.core.seed_steps.waline import (
    clear_waline_seed_data,
    seed_waline_comment_data,
    seed_waline_counter_data,
)
from aerisun.core.settings import get_settings
from aerisun.core.time import beijing_today
from aerisun.domain.automation.models import WebhookSubscription
from aerisun.domain.automation.settings import AGENT_MODEL_CONFIG_FLAG_KEY, DEFAULT_AGENT_MODEL_CONFIG
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
    Poem,
    ResumeBasics,
    SiteProfile,
    SocialLink,
)
from aerisun.domain.social.models import Friend, FriendFeedItem, FriendFeedSource
from aerisun.domain.subscription.models import ContentSubscriptionConfig
from aerisun.domain.waline.service import build_comment_path

DEFAULT_HERO_VIDEO_URL = (
    "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/"
    "hf_20260306_115329_5e00c9c5-4d69-49b7-94c3-9c31c60bb644.mp4"
)

DEFAULT_SITE_PROFILE = {
    "name": "Felix",
    "title": "Aerisun",
    "bio": "我做网页设计，也写前端，把视觉、节奏、内容和交互整理成一个自然流动的个人空间。",
    "role": "UI/UX Designer · Frontend Developer",
    "og_image": "__SEEDED_OG_IMAGE__",
    "site_icon_url": "__SEEDED_SITE_ICON__",
    "hero_image_url": "__SEEDED_HERO_IMAGE__",
    "hero_poster_url": "__SEEDED_HERO_POSTER__",
    "filing_info": "",
    "hero_video_url": DEFAULT_HERO_VIDEO_URL,
    "poem_source": "hitokoto",
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
        "title": "友邻与最近动态",
        "subtitle": "展示朋友动态、最近活动和贡献热力图。",
        "search_placeholder": None,
        "empty_message": None,
        "max_width": None,
        "page_size": None,
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
            "heatmapThisWeekLabel": "This week",
            "heatmapPeakWeekLabel": "Peak week",
            "heatmapAverageWeekLabel": "Avg / week",
        },
    },
    {
        "page_key": "notFound",
        "title": "这个页面没有留下来",
        "subtitle": "似乎已经离开了当前的路径。",
        "search_placeholder": None,
        "empty_message": None,
        "max_width": None,
        "page_size": None,
        "extras": {
            "metaTitle": "页面未找到",
            "metaDescription": "你访问的页面不存在，或者已经被移动。",
            "badgeLabel": "404",
            "homeLabel": "返回首页",
            "backLabel": "返回上页",
        },
    },
    {
        "page_key": "posts",
        "title": "Posts",
        "subtitle": "整理过的碎碎念与实践记录。",
        "search_placeholder": "搜索文章...",
        "empty_message": "没有找到匹配的文章",
        "max_width": "max-w-3xl",
        "page_size": 15,
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
        "title": "日记",
        "subtitle": "每天一点点，记录生活的温度。",
        "search_placeholder": None,
        "empty_message": "今天还没有新的日记",
        "max_width": "max-w-2xl",
        "page_size": 15,
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
        "title": "朋友们",
        "subtitle": "海内存知己，天涯若比邻",
        "search_placeholder": None,
        "empty_message": "暂时没有友链内容",
        "max_width": "max-w-4xl",
        "page_size": 10,
        "extras": {
            "circle_title": "Friend Circle",
            "errorTitle": "友链页面加载失败",
            "loadingLabel": "正在加载...",
            "loadMoreLabel": "加载更多",
            "retryLabel": "重试加载",
            "refreshLabel": "刷新",
            "refreshAriaLabel": "刷新友链动态",
            "randomPickerLabel": "从最近 {days} 天里随机挑一篇",
            "randomRefreshLabel": "换一篇",
            "randomEmptyTemplate": "最近 {days} 天还没有可展示的友链文章",
            "summaryTemplate": "{sites} 个站点 · 共 {articles} 条动态",
            "footerSummaryTemplate": "已连接 {sites} 个站点，最近抓取 {articles} 条公开动态",
            "randomRecentDays": 66,
            "autoRefreshSeconds": 666,
            "websiteHealthCheckEnabled": True,
            "websiteHealthCheckIntervalMinutes": 360,
            "rssHealthCheckEnabled": True,
            "rssHealthCheckIntervalMinutes": 360,
        },
    },
    {
        "page_key": "excerpts",
        "title": "文摘",
        "subtitle": "整理那些让我停下来想一想的文摘。",
        "search_placeholder": None,
        "empty_message": "还没有整理好的文摘",
        "max_width": "max-w-3xl",
        "page_size": 15,
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
        "title": "碎碎念",
        "subtitle": "一些不成文的碎碎念，随手记下的片段。",
        "search_placeholder": None,
        "empty_message": "最近没有新的碎碎念",
        "max_width": "max-w-2xl",
        "page_size": 15,
        "extras": {
            "errorTitle": "碎碎念加载失败",
            "retryLabel": "重试",
            "loadMoreLabel": "加载更多...",
        },
    },
    {
        "page_key": "guestbook",
        "title": "留言板",
        "subtitle": "留下你的足迹，说点什么吧。",
        "search_placeholder": None,
        "empty_message": "还没有人留言",
        "max_width": "max-w-2xl",
        "page_size": None,
        "extras": {
            "contentPlaceholder": "想说的话",
            "submitLabel": "提交留言",
            "submittingLabel": "提交留言",
            "loadingLabel": "留言板正在更新",
            "retryLabel": "重试加载",
        },
    },
    {
        "page_key": "calendar",
        "title": "日历",
        "subtitle": "记录每一天的痕迹。",
        "search_placeholder": None,
        "empty_message": "日历里还没有内容",
        "max_width": "max-w-4xl",
        "page_size": None,
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
        "image_uploader": True,
        "anonymous_enabled": True,
        "moderation_mode": "all_pending",
        "default_sorting": "latest",
        "page_size": 20,
        "image_max_bytes": 524288,
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


def _is_blank_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


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
    if getattr(config, "admin_console_auth_methods", None) is None:
        config.admin_console_auth_methods = list(default_config["admin_console_auth_methods"])
    if getattr(config, "admin_email_enabled", None) is None:
        config.admin_email_enabled = bool(default_config["admin_email_enabled"])
    if getattr(config, "admin_email_password_hash", None) is None:
        config.admin_email_password_hash = default_config["admin_email_password_hash"]
    if not config.google_client_id:
        config.google_client_id = str(default_config["google_client_id"])
    if not config.google_client_secret:
        config.google_client_secret = str(default_config["google_client_secret"])
    if not config.github_client_id:
        config.github_client_id = str(default_config["github_client_id"])
    if not config.github_client_secret:
        config.github_client_secret = str(default_config["github_client_secret"])


def _seed_subscription_config_from_settings(session: Session) -> None:
    settings = get_settings()
    config = session.scalars(
        select(ContentSubscriptionConfig).order_by(ContentSubscriptionConfig.created_at.asc())
    ).first()
    created = False
    if config is None:
        config = ContentSubscriptionConfig()
        session.add(config)
        session.flush()
        created = True

    has_secret_overrides = any(
        [
            settings.subscription_smtp_host.strip(),
            settings.subscription_smtp_username.strip(),
            settings.subscription_smtp_password.strip(),
            settings.subscription_smtp_oauth_tenant.strip(),
            settings.subscription_smtp_oauth_client_id.strip(),
            settings.subscription_smtp_oauth_client_secret.strip(),
            settings.subscription_smtp_oauth_refresh_token.strip(),
            settings.subscription_smtp_from_email.strip(),
            settings.subscription_smtp_from_name.strip(),
            settings.subscription_smtp_reply_to.strip(),
        ]
    )

    if not has_secret_overrides and not settings.dev_seed_subscription_enabled:
        return

    if created:
        config.enabled = bool(settings.dev_seed_subscription_enabled)
        config.smtp_auth_mode = (settings.subscription_smtp_auth_mode or "password").strip() or "password"
        config.smtp_host = settings.subscription_smtp_host.strip()
        config.smtp_port = int(settings.subscription_smtp_port or 587)
        config.smtp_username = settings.subscription_smtp_username.strip()
        config.smtp_password = settings.subscription_smtp_password.strip()
        config.smtp_oauth_tenant = settings.subscription_smtp_oauth_tenant.strip() or "common"
        config.smtp_oauth_client_id = settings.subscription_smtp_oauth_client_id.strip()
        config.smtp_oauth_client_secret = settings.subscription_smtp_oauth_client_secret.strip()
        config.smtp_oauth_refresh_token = settings.subscription_smtp_oauth_refresh_token.strip()
        config.smtp_from_email = settings.subscription_smtp_from_email.strip()
        config.smtp_from_name = settings.subscription_smtp_from_name.strip()
        config.smtp_reply_to = settings.subscription_smtp_reply_to.strip()
        config.smtp_use_tls = bool(settings.subscription_smtp_use_tls)
        config.smtp_use_ssl = bool(settings.subscription_smtp_use_ssl)
        config.smtp_test_passed = False
        config.smtp_tested_at = None
        return

    def _fill_if_empty(field_name: str, value: str) -> bool:
        normalized = value.strip()
        if not normalized:
            return False
        if not _is_blank_value(getattr(config, field_name)):
            return False
        setattr(config, field_name, normalized)
        return True

    changed = False
    changed = _fill_if_empty("smtp_host", settings.subscription_smtp_host) or changed
    changed = _fill_if_empty("smtp_username", settings.subscription_smtp_username) or changed
    changed = _fill_if_empty("smtp_password", settings.subscription_smtp_password) or changed
    changed = _fill_if_empty("smtp_oauth_tenant", settings.subscription_smtp_oauth_tenant) or changed
    changed = _fill_if_empty("smtp_oauth_client_id", settings.subscription_smtp_oauth_client_id) or changed
    changed = _fill_if_empty("smtp_oauth_client_secret", settings.subscription_smtp_oauth_client_secret) or changed
    changed = _fill_if_empty("smtp_oauth_refresh_token", settings.subscription_smtp_oauth_refresh_token) or changed
    changed = _fill_if_empty("smtp_from_email", settings.subscription_smtp_from_email) or changed
    changed = _fill_if_empty("smtp_from_name", settings.subscription_smtp_from_name) or changed
    changed = _fill_if_empty("smtp_reply_to", settings.subscription_smtp_reply_to) or changed

    if changed:
        config.smtp_test_passed = False
        config.smtp_tested_at = None


def _seed_agent_model_config_from_settings(session: Session) -> None:
    settings = get_settings()
    provider = (settings.dev_seed_agent_model_provider or "openai_compatible").strip() or "openai_compatible"
    base_url = settings.dev_seed_agent_model_base_url.strip()
    model_name = settings.dev_seed_agent_model.strip()
    api_key = settings.dev_seed_agent_model_api_key.strip()
    advisory_prompt = settings.dev_seed_agent_model_advisory_prompt.strip()

    should_apply = bool(settings.dev_seed_agent_model_enabled or base_url or model_name or api_key or advisory_prompt)
    if not should_apply:
        return

    site = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
    if site is None:
        return

    feature_flags = dict(site.feature_flags or {})
    current = feature_flags.get(AGENT_MODEL_CONFIG_FLAG_KEY)
    current_data = current if isinstance(current, dict) else {}
    merged = dict(DEFAULT_AGENT_MODEL_CONFIG)
    merged.update(current_data)

    if ("provider" not in current_data or _is_blank_value(current_data.get("provider"))) and provider:
        merged["provider"] = provider
    if ("base_url" not in current_data or _is_blank_value(current_data.get("base_url"))) and base_url:
        merged["base_url"] = base_url
    if ("model" not in current_data or _is_blank_value(current_data.get("model"))) and model_name:
        merged["model"] = model_name
    if ("api_key" not in current_data or _is_blank_value(current_data.get("api_key"))) and api_key:
        merged["api_key"] = api_key
    if (
        "advisory_prompt" not in current_data or _is_blank_value(current_data.get("advisory_prompt"))
    ) and advisory_prompt:
        merged["advisory_prompt"] = advisory_prompt

    if "temperature" not in current_data or current_data.get("temperature") is None:
        merged["temperature"] = float(settings.dev_seed_agent_model_temperature)
    if "timeout_seconds" not in current_data or current_data.get("timeout_seconds") in (None, 0):
        merged["timeout_seconds"] = max(int(settings.dev_seed_agent_model_timeout_seconds), 5)
    if "enabled" not in current_data or current_data.get("enabled") is None:
        merged["enabled"] = bool(settings.dev_seed_agent_model_enabled)
        if not merged["enabled"] and base_url and model_name and api_key:
            merged["enabled"] = True

    feature_flags[AGENT_MODEL_CONFIG_FLAG_KEY] = merged
    site.feature_flags = feature_flags


def _seed_webhook_subscription_from_settings(session: Session) -> None:
    settings = get_settings()
    target_url = settings.dev_seed_webhook_target_url.strip()
    if not target_url:
        return

    name = settings.dev_seed_webhook_name.strip() or "dev-webhook"
    secret = settings.dev_seed_webhook_secret.strip() or None
    status = settings.dev_seed_webhook_status.strip() or "active"
    timeout_seconds = max(int(settings.dev_seed_webhook_timeout_seconds or 10), 1)
    max_attempts = max(int(settings.dev_seed_webhook_max_attempts or 6), 1)
    event_types = [item.strip() for item in settings.dev_seed_webhook_event_types.split(",") if item.strip()]
    if not event_types:
        event_types = ["webhook.test"]

    headers: dict[str, object] = {}
    raw_headers = settings.dev_seed_webhook_headers_json.strip()
    if raw_headers:
        try:
            parsed_headers = json.loads(raw_headers)
            if isinstance(parsed_headers, dict):
                headers = {str(key): value for key, value in parsed_headers.items()}
        except json.JSONDecodeError:
            logging.getLogger("aerisun.seed").warning(
                "Ignored AERISUN_DEV_SEED_WEBHOOK_HEADERS_JSON because it is not valid JSON"
            )

    webhook = session.scalars(
        select(WebhookSubscription)
        .where(WebhookSubscription.name == name)
        .order_by(WebhookSubscription.created_at.asc())
    ).first()
    if webhook is None:
        webhook = WebhookSubscription(
            name=name,
            status=status,
            target_url=target_url,
            secret=secret,
            event_types=event_types,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            headers=headers,
        )
        session.add(webhook)
        return

    if _is_blank_value(webhook.status):
        webhook.status = status
    if _is_blank_value(webhook.target_url):
        webhook.target_url = target_url
    if secret is not None and _is_blank_value(webhook.secret):
        webhook.secret = secret
    if not webhook.event_types:
        webhook.event_types = event_types
    if not webhook.timeout_seconds:
        webhook.timeout_seconds = timeout_seconds
    if not webhook.max_attempts:
        webhook.max_attempts = max_attempts
    if headers and not webhook.headers:
        webhook.headers = headers


DEFAULT_RESUME = {
    "title": "Felix",
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
    "location": "上海 / Remote",
    "email": "felix@example.com",
    "profile_image_url": "__SEEDED_RESUME_AVATAR__",
}

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
        "key": "waline-guestbook-paper-crane",
        "url": "/guestbook",
        "nick": "纸鹤",
        "mail": None,
        "link": None,
        "comment": "在这里读到很多温柔又克制的表达，留言板也和整站气质贴得很紧。",
        "status": "approved",
        "created_at": datetime(2026, 3, 15, 10, 30, tzinfo=UTC),
        "parent_key": None,
    },
]

DEFAULT_REACTIONS = [
    {
        "content_type": "posts",
        "content_slug": "from-zero-design-system",
        "reaction_type": "like",
        "client_token": "Elena Torres",
        "created_at": datetime(2026, 3, 20, 22, 10, tzinfo=UTC),
        "updated_at": datetime(2026, 3, 20, 22, 10, tzinfo=UTC),
    },
    {
        "content_type": "posts",
        "content_slug": "from-zero-design-system",
        "reaction_type": "like",
        "client_token": "Kai Nakamura",
        "created_at": datetime(2026, 3, 21, 11, 20, tzinfo=UTC),
        "updated_at": datetime(2026, 3, 21, 11, 20, tzinfo=UTC),
    },
    {
        "content_type": "diary",
        "content_slug": "spring-equinox-and-warm-light",
        "reaction_type": "like",
        "client_token": "David Okoro",
        "created_at": datetime(2026, 3, 21, 13, 40, tzinfo=UTC),
        "updated_at": datetime(2026, 3, 21, 13, 40, tzinfo=UTC),
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
    today = beijing_today()
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


DEV_FRIENDS = [
    {
        "name": "Arthals' ink",
        "url": "https://arthals.ink/",
        "avatar_url": "https://cdn.arthals.ink/Arthals.png",
        "description": "所见高山远木，阔云流风；所幸岁月盈余，了无拘束",
        "status": "active",
        "order_index": 0,
    },
]
DEV_FRIEND_FEED_SOURCES = [
    {
        "friend_name": "Arthals' ink",
        "feed_url": "https://arthals.ink/rss.xml",
        "last_fetched_at": None,
        "is_enabled": True,
    },
]
DEV_FRIEND_FEED_ITEMS: list[dict[str, object]] = []
DEV_LEGACY_GUESTBOOK_ENTRIES = DEFAULT_LEGACY_GUESTBOOK_ENTRIES
DEV_LEGACY_COMMENTS = DEFAULT_LEGACY_COMMENTS
DEV_WALINE_COMMENTS = DEFAULT_WALINE_COMMENTS
DEV_REACTIONS = DEFAULT_REACTIONS
DEV_TRAFFIC_SNAPSHOTS = DEFAULT_TRAFFIC_SNAPSHOTS

DEV_SEED_BLOCK_META_PREFIX = "dev_seed_block_fingerprint:"
DEV_SEED_BASE_BLOCKS = ("core", "content", "admin")
DEV_SEED_DEV_ONLY_BLOCKS = ("social", "engagement", "ops", "waline")


def _active_seed_blocks(include_dev_data: bool) -> tuple[str, ...]:
    if include_dev_data:
        return (*DEV_SEED_BASE_BLOCKS, *DEV_SEED_DEV_ONLY_BLOCKS)
    return DEV_SEED_BASE_BLOCKS


def _seed_function_source(fn: object) -> str:
    try:
        return inspect.getsource(fn)  # type: ignore[arg-type]
    except (OSError, TypeError):
        return repr(fn)


def _fingerprint_seed_block(*parts: object) -> str:
    digest = hashlib.sha256()
    for part in parts:
        payload = _seed_function_source(part) if callable(part) else repr(part)
        digest.update(payload.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def _compute_seed_block_fingerprints(*, include_dev_data: bool) -> dict[str, str]:
    fingerprints = {
        "core": _fingerprint_seed_block(
            DEFAULT_SITE_PROFILE,
            DEFAULT_SOCIAL_LINKS,
            DEFAULT_POEMS,
            DEFAULT_PAGE_COPIES,
            DEFAULT_NAV_ITEMS,
            DEFAULT_RESUME,
            DEFAULT_COMMENT_AVATAR_PRESETS,
            _merge_community_surfaces,
            _normalize_community_server_url,
            _seed_community_config,
            _seed_site_auth_config,
            _seed_subscription_config_from_settings,
            _seed_agent_model_config_from_settings,
            _seed_webhook_subscription_from_settings,
            seed_missing_page_copies,
        ),
        "content": _fingerprint_seed_block(
            DEFAULT_POSTS,
            DEFAULT_DIARY_ENTRIES,
            DEFAULT_THOUGHTS,
            DEFAULT_EXCERPTS,
            seed_content_entries,
        ),
        "admin": _fingerprint_seed_block(seed_dev_admin),
    }

    if include_dev_data:
        fingerprints.update(
            {
                "social": _fingerprint_seed_block(
                    DEV_FRIENDS,
                    DEV_FRIEND_FEED_SOURCES,
                    DEV_FRIEND_FEED_ITEMS,
                    seed_social_data,
                ),
                "engagement": _fingerprint_seed_block(
                    DEV_REACTIONS,
                    DEV_LEGACY_GUESTBOOK_ENTRIES,
                    DEV_LEGACY_COMMENTS,
                    seed_engagement_data,
                    seed_legacy_guestbook_data,
                    seed_legacy_comment_data,
                ),
                "ops": _fingerprint_seed_block(
                    DEV_TRAFFIC_SNAPSHOTS,
                    seed_traffic_snapshot_data,
                    seed_visit_record_data,
                ),
                "waline": _fingerprint_seed_block(
                    DEV_WALINE_COMMENTS,
                    DEFAULT_WALINE_COUNTERS,
                    seed_waline_comment_data,
                    seed_waline_counter_data,
                ),
            }
        )
    return fingerprints


def _seed_block_meta_key(block: str) -> str:
    return f"{DEV_SEED_BLOCK_META_PREFIX}{block}"


def _load_seed_block_fingerprints(db_path: Path, *, include_dev_data: bool) -> dict[str, str]:
    if not db_path.exists():
        return {}

    connection = sqlite3.connect(str(db_path))
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "_aerisun_meta" not in tables:
            return {}

        stored: dict[str, str] = {}
        for block in _active_seed_blocks(include_dev_data):
            row = connection.execute(
                "SELECT value FROM _aerisun_meta WHERE key = ?",
                (_seed_block_meta_key(block),),
            ).fetchone()
            if row and row[0]:
                stored[block] = str(row[0])
        return stored
    finally:
        connection.close()


def _store_seed_block_fingerprints(
    db_path: Path,
    *,
    fingerprints: dict[str, str],
    include_dev_data: bool,
) -> None:
    connection = sqlite3.connect(str(db_path))
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS _aerisun_meta (key TEXT PRIMARY KEY, value TEXT)")
        for block in _active_seed_blocks(include_dev_data):
            connection.execute(
                "INSERT OR REPLACE INTO _aerisun_meta (key, value) VALUES (?, ?)",
                (_seed_block_meta_key(block), fingerprints.get(block, "")),
            )
        connection.commit()
    finally:
        connection.close()


def _determine_incremental_reseed_blocks(
    db_path: Path,
    *,
    current_fingerprints: dict[str, str],
    include_dev_data: bool,
) -> set[str]:
    active_blocks = _active_seed_blocks(include_dev_data)
    stored_fingerprints = _load_seed_block_fingerprints(db_path, include_dev_data=include_dev_data)
    if not stored_fingerprints:
        return set(active_blocks)
    return {block for block in active_blocks if stored_fingerprints.get(block) != current_fingerprints.get(block)}


def _clear_seed_models(session: Session, models: list[type], *, label: str) -> None:
    _logger = logging.getLogger("aerisun.seed")
    _logger.info("Incremental reseed: clearing block '%s'", label)
    for model in models:
        count = session.query(model).delete()
        if count:
            _logger.info("  Cleared %d rows from %s", count, model.__tablename__)
    session.flush()


def _clear_seed_block_data(session: Session, block: str) -> None:
    if block == "core":
        # Preserve sensitive/runtime tables (e.g., site_auth/subscription/workflow data).
        _clear_seed_models(
            session,
            [
                NavItem,
                PageCopy,
                CommunityConfig,
            ],
            label=block,
        )
        return

    if block == "content":
        _clear_seed_models(session, [PostEntry, DiaryEntry, ThoughtEntry, ExcerptEntry], label=block)
        return

    if block == "social":
        _clear_seed_models(session, [FriendFeedItem, FriendFeedSource, Friend], label=block)
        return

    if block == "engagement":
        _clear_seed_models(session, [Comment, GuestbookEntry, Reaction], label=block)
        return

    if block == "ops":
        _clear_seed_models(session, [TrafficDailySnapshot, VisitRecord], label=block)
        return

    if block == "admin":
        _clear_seed_models(session, [AdminUser], label=block)


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
        ResumeBasics,
        NavItem,
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


def _has_rows(session: Session, model: type) -> bool:
    return session.scalar(select(model.id).limit(1)) is not None


def _should_preserve_content_block(session: Session) -> bool:
    return any(
        _has_rows(session, model)
        for model in (
            PostEntry,
            DiaryEntry,
            ThoughtEntry,
            ExcerptEntry,
        )
    )


def _should_preserve_social_block(session: Session) -> bool:
    return any(
        _has_rows(session, model)
        for model in (
            Friend,
            FriendFeedSource,
            FriendFeedItem,
        )
    )


def _seed_core_reference_data(session: Session) -> None:
    seeded_assets = seed_core_system_asset_urls(session)

    if is_empty(session, SiteProfile):
        site_payload = {
            **DEFAULT_SITE_PROFILE,
            "og_image": seeded_assets["og_image"],
            "site_icon_url": seeded_assets["site_icon_url"],
            "hero_image_url": seeded_assets["hero_image_url"],
            "hero_poster_url": seeded_assets["hero_poster_url"],
        }
        site = SiteProfile(**site_payload)
        session.add(site)
        session.flush()

        session.add_all([SocialLink(site_profile_id=site.id, **item) for item in DEFAULT_SOCIAL_LINKS])
        session.add_all(
            [Poem(site_profile_id=site.id, order_index=index, content=text) for index, text in enumerate(DEFAULT_POEMS)]
        )
        session.add_all([PageCopy(**item) for item in DEFAULT_PAGE_COPIES])
        resume_payload = {**DEFAULT_RESUME, "profile_image_url": seeded_assets["profile_image_url"]}
        resume = ResumeBasics(**resume_payload)
        session.add(resume)
        session.flush()

    seed_missing_page_copies(session, DEFAULT_PAGE_COPIES)

    current_site = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
    current_resume = session.scalars(select(ResumeBasics).order_by(ResumeBasics.created_at.asc())).first()
    normalize_core_system_asset_references(session, site=current_site, resume=current_resume)

    if is_empty(session, NavItem):
        site = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
        if site is not None:
            label_to_id: dict[str, str] = {}
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
    _seed_subscription_config_from_settings(session)
    _seed_agent_model_config_from_settings(session)
    _seed_webhook_subscription_from_settings(session)


def _seed_reference_data(*, force: bool = False, include_dev_data: bool = True) -> None:
    settings = get_settings()
    settings.ensure_directories()
    init_db()

    # bootstrap.sh sets FORCE_RESEED=true when reseed is triggered by preflight checks.
    incremental_force = force and os.environ.get("FORCE_RESEED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    reseed_all_blocks = not incremental_force
    current_block_fingerprints = _compute_seed_block_fingerprints(include_dev_data=include_dev_data)
    blocks_to_reseed: set[str] = set()
    if incremental_force:
        blocks_to_reseed = _determine_incremental_reseed_blocks(
            settings.db_path,
            current_fingerprints=current_block_fingerprints,
            include_dev_data=include_dev_data,
        )

    session = get_session_factory()()
    try:
        if force and reseed_all_blocks:
            _clear_seed_data(session)
            clear_waline_seed_data()
        elif incremental_force:
            _logger = logging.getLogger("aerisun.seed")
            if blocks_to_reseed:
                _logger.info(
                    "Force reseed: incremental blocks -> %s",
                    ", ".join(sorted(blocks_to_reseed)),
                )
            else:
                _logger.info("Force reseed: no changed seed blocks detected, skipping reseed")

            preserved_blocks: set[str] = set()
            if "content" in blocks_to_reseed and _should_preserve_content_block(session):
                preserved_blocks.add("content")
            if "social" in blocks_to_reseed and _should_preserve_social_block(session):
                preserved_blocks.add("social")

            if preserved_blocks:
                _logger.info(
                    "Incremental reseed: preserve existing blocks -> %s",
                    ", ".join(sorted(preserved_blocks)),
                )
                blocks_to_reseed -= preserved_blocks

            for block in _active_seed_blocks(include_dev_data):
                if block == "waline":
                    continue
                if block in blocks_to_reseed:
                    _clear_seed_block_data(session, block)

            if include_dev_data and "waline" in blocks_to_reseed:
                clear_waline_seed_data()

        run_core = reseed_all_blocks or "core" in blocks_to_reseed
        run_content = reseed_all_blocks or "content" in blocks_to_reseed
        run_social = include_dev_data and (reseed_all_blocks or "social" in blocks_to_reseed)
        run_engagement = include_dev_data and (reseed_all_blocks or "engagement" in blocks_to_reseed)
        run_ops = include_dev_data and (reseed_all_blocks or "ops" in blocks_to_reseed)
        run_admin = reseed_all_blocks or "admin" in blocks_to_reseed

        if run_core:
            _seed_core_reference_data(session)

        if run_content:
            seed_content_entries(session, PostEntry, DEFAULT_POSTS)
            seed_content_entries(session, DiaryEntry, DEFAULT_DIARY_ENTRIES)
            seed_content_entries(session, ThoughtEntry, DEFAULT_THOUGHTS)
            seed_content_entries(session, ExcerptEntry, DEFAULT_EXCERPTS)

        if run_social:
            seed_social_data(
                session,
                default_friends=DEV_FRIENDS,
                default_friend_feed_sources=DEV_FRIEND_FEED_SOURCES,
                default_friend_feed_items=DEV_FRIEND_FEED_ITEMS,
            )

        if run_engagement:
            seed_engagement_data(session, default_reactions=DEV_REACTIONS)
            seed_legacy_guestbook_data(session, default_guestbook_entries=DEV_LEGACY_GUESTBOOK_ENTRIES)
            seed_legacy_comment_data(session, default_legacy_comments=DEV_LEGACY_COMMENTS)

        if run_ops:
            seed_traffic_snapshot_data(session, default_traffic_snapshots=DEV_TRAFFIC_SNAPSHOTS)
            seed_visit_record_data(session)

        if run_admin:
            seed_dev_admin(session)

        session.commit()
    finally:
        session.close()

    run_waline = include_dev_data and (reseed_all_blocks or "waline" in blocks_to_reseed)
    if run_waline:
        seed_waline_comment_data(default_waline_comments=DEV_WALINE_COMMENTS)
        seed_waline_counter_data(default_waline_counters=DEFAULT_WALINE_COUNTERS)

    _store_seed_block_fingerprints(
        settings.db_path,
        fingerprints=current_block_fingerprints,
        include_dev_data=include_dev_data,
    )


def seed_development_data(*, force: bool = False) -> None:
    _seed_reference_data(force=force, include_dev_data=True)

    settings = get_settings()
    if settings.environment != "development":
        return
    if not settings.feed_crawl_enabled:
        return
    if not DEV_FRIEND_FEED_SOURCES:
        return

    from aerisun.domain.social.monitor import run_due_rss_health_checks

    logger = logging.getLogger("aerisun.seed")
    try:
        result = run_due_rss_health_checks(settings)
        logger.info("Development friend feed crawl finished", result=result)
    except Exception:
        logger.exception("Development friend feed crawl failed")


def seed_reference_data(*, force: bool = False) -> None:
    """Backward-compatible development seed entrypoint."""
    seed_development_data(force=force)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Aerisun development sample data.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="clear existing seed data before reseeding",
    )
    args = parser.parse_args()
    seed_reference_data(force=args.force)


if __name__ == "__main__":
    main()
