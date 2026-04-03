from __future__ import annotations

import argparse
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

import aerisun.domain.automation.models
import aerisun.domain.subscription.models  # noqa: F401
from aerisun.core.db import get_session_factory, init_db
from aerisun.core.seed_steps.assets import ensure_seed_asset, ensure_system_asset_reference
from aerisun.core.seed_steps.common import is_empty
from aerisun.core.seed_steps.content import seed_missing_page_copies
from aerisun.core.seed_steps.legacy import seed_dev_admin
from aerisun.core.seed_steps.waline import clear_waline_seed_data
from aerisun.core.settings import BACKEND_ROOT, get_settings
from aerisun.domain.automation.settings import AGENT_MODEL_CONFIG_FLAG_KEY, DEFAULT_AGENT_MODEL_CONFIG
from aerisun.domain.automation.models import (
    AgentRun,
    AgentRunApproval,
    AgentRunStep,
    WebhookDeadLetter,
    WebhookDelivery,
    WebhookSubscription,
    WorkflowBuildTask,
    WorkflowBuildTaskStep,
    WorkflowGateBufferItem,
    WorkflowGateState,
)
from aerisun.domain.content.models import ContentCategory, DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.engagement.models import Comment, GuestbookEntry, Reaction
from aerisun.domain.iam.models import AdminUser, ApiKey
from aerisun.domain.media.models import Asset
from aerisun.domain.ops.config_revisions import capture_config_resource, create_config_revision
from aerisun.domain.ops.models import AuditLog, ConfigRevision, TrafficDailySnapshot, VisitRecord
from aerisun.domain.site_auth.models import SiteAdminIdentity, SiteAuthConfig, SiteUser, SiteUserOAuthAccount, SiteUserSession
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

DEFAULT_HERO_VIDEO_URL = (
    "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/"
    "hf_20260306_115329_5e00c9c5-4d69-49b7-94c3-9c31c60bb644.mp4"
)

DEFAULT_SITE_PROFILE = {
    "name": "uName",
    "title": "YourTitle",
    "bio": "你是一个什么样的灵魂呀，写到这里吧 ~",
    "role": "THIS IS · YOUR ROLE",
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
    {"name": "GitHub", "href": "https://github.com/", "icon_key": "github", "placement": "hero", "order_index": 0}
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
        "title": "站点动态",
        "subtitle": "展示朋友动态、最近活动和贡献热力图。",
        "search_placeholder": None,
        "empty_message": None,
        "max_width": None,
        "page_size": None,
        "extras": {
            "dashboardLabel": "Recently",
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
        "subtitle": "",
        "search_placeholder": None,
        "empty_message": None,
        "max_width": None,
        "page_size": None,
        "extras": {
            "metaTitle": "页面未找到",
            "metaDescription": "",
            "badgeLabel": "404",
            "homeLabel": "返回首页",
            "backLabel": "返回上页",
        },
    },
    {
        "page_key": "posts",
        "title": "文章",
        "subtitle": "让思想与经历，在文字中缓缓流淌",
        "search_placeholder": "搜索文章...",
        "empty_message": "没有找到匹配的文章",
        "max_width": "max-w-4xl",
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
            "detailEndLabel": "— END —",
        },
    },
    {
        "page_key": "diary",
        "title": "日记",
        "subtitle": "用细碎的文字，轻轻安放每一天的心情",
        "search_placeholder": None,
        "empty_message": "今天还没有新的日记",
        "max_width": "max-w-3xl",
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
        "subtitle": "拾起片语只字，珍藏那些让心灵驻足的片刻",
        "search_placeholder": None,
        "empty_message": "还没有整理好的文摘",
        "max_width": "max-w-4xl",
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
        "subtitle": "轻放心头微澜，任思绪悄然落在字里行间",
        "search_placeholder": None,
        "empty_message": "最近没有新的碎碎念",
        "max_width": "max-w-3xl",
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
        "subtitle": "有缘路过，不妨留一言片语",
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
        "subtitle": "把日子的光影，悄悄收进时光的口袋。",
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

PRODUCTION_CONFIG_HISTORY_RESOURCES = (
    "site.profile",
    "site.community",
    "site.navigation",
    "site.social_links",
    "site.poems",
    "site.pages",
    "visitors.auth",
    "subscriptions.config",
    "network.outbound_proxy",
    "integrations.mcp_public_access",
    "automation.model_config",
    "automation.workflows",
)


def build_default_community_config() -> dict[str, object]:
    settings = get_settings()

    return {
        "provider": "waline",
        "server_url": settings.waline_server_url.strip(),
        "surfaces": [
            {"key": "posts", "label": "文章评论", "path": "/posts/{slug}", "enabled": True},
            {"key": "diary", "label": "日记评论", "path": "/diary/{slug}", "enabled": True},
            {"key": "guestbook", "label": "留言板", "path": "/guestbook", "enabled": True},
            {"key": "thoughts", "label": "碎碎念评论", "path": "/thoughts/{slug}", "enabled": True},
            {"key": "excerpts", "label": "文摘评论", "path": "/excerpts/{slug}", "enabled": True},
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


def _seed_community_config(session: Session, *, force: bool = False) -> None:
    default_config = build_default_community_config()
    config = session.scalars(select(CommunityConfig).order_by(CommunityConfig.created_at.asc())).first()

    if config is None:
        session.add(CommunityConfig(**default_config))
        return

    if force:
        for key, value in default_config.items():
            setattr(config, key, value)
        return

    default_server_url = str(default_config["server_url"]).strip()
    config.server_url = _normalize_community_server_url(config.server_url, default_server_url)
    config.surfaces = _merge_community_surfaces(config.surfaces, list(default_config["surfaces"]))


def _seed_site_auth_config(session: Session, *, force: bool = False) -> None:
    from aerisun.domain.site_auth.service import build_default_site_auth_config

    default_config = build_default_site_auth_config(session)
    config = session.scalars(select(SiteAuthConfig).order_by(SiteAuthConfig.created_at.asc())).first()
    if config is None:
        session.add(SiteAuthConfig(**default_config))
        return

    if force:
        config.email_login_enabled = bool(default_config["email_login_enabled"])
        config.visitor_oauth_providers = list(default_config["visitor_oauth_providers"])
        config.admin_auth_methods = list(default_config["admin_auth_methods"])
        config.admin_console_auth_methods = list(default_config["admin_console_auth_methods"])
        config.admin_email_enabled = bool(default_config["admin_email_enabled"])
        config.admin_email_password_hash = default_config["admin_email_password_hash"]
        config.google_client_id = str(default_config["google_client_id"])
        config.google_client_secret = str(default_config["google_client_secret"])
        config.github_client_id = str(default_config["github_client_id"])
        config.github_client_secret = str(default_config["github_client_secret"])
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


def _seed_subscription_config_from_settings(session: Session, *, force: bool = False) -> None:
    settings = get_settings()
    config = session.scalars(select(ContentSubscriptionConfig).order_by(ContentSubscriptionConfig.created_at.asc())).first()
    if config is None:
        config = ContentSubscriptionConfig()
        session.add(config)
        session.flush()
        force = True

    if not force:
        return

    smtp_auth_mode = (settings.subscription_smtp_auth_mode or "password").strip().lower()
    if smtp_auth_mode not in {"password", "microsoft_oauth2"}:
        smtp_auth_mode = "password"

    config.enabled = False
    config.smtp_auth_mode = smtp_auth_mode or "password"
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
    config.allowed_content_types = ["posts", "diary", "thoughts", "excerpts"]
    config.mail_subject_template = "[{site_name}] {content_title}"
    config.mail_body_template = (
        "{site_name} 有新的{content_type_label}内容发布。\n\n"
        "{content_title}\n"
        "{content_summary}\n\n"
        "阅读链接：{content_url}\n"
        "RSS：{feed_url}"
    )


def _seed_agent_model_config(session: Session, *, force: bool = False) -> None:
    site = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
    if site is None:
        return

    feature_flags = dict(site.feature_flags or {})
    if force or AGENT_MODEL_CONFIG_FLAG_KEY not in feature_flags:
        feature_flags[AGENT_MODEL_CONFIG_FLAG_KEY] = dict(DEFAULT_AGENT_MODEL_CONFIG)
        site.feature_flags = feature_flags


def _seed_config_history_and_audit(session: Session) -> None:
    if not is_empty(session, ConfigRevision):
        return

    for resource_key in PRODUCTION_CONFIG_HISTORY_RESOURCES:
        snapshot = capture_config_resource(session, resource_key)
        create_config_revision(
            session,
            actor_id=None,
            resource_key=resource_key,
            operation="seed",
            before_snapshot=None,
            after_snapshot=snapshot,
            summary_override=f"生产种子初始化：{resource_key}",
            commit=False,
        )


DEFAULT_RESUME = {
    "title": "YourName",
    "summary": """## Profile
你的简介写在这里，介绍一下你自己吧 ~

## Experience
### what your experience
**WhatRole** · 20XX - Now

- yayaya
- ummmmm
- 👀👀👀👀👀👀

## Skills
- ... / .... / ...
- ......
- 👍 👍🏻 👍🏼 👍🏽 👍🏾 👍🏿

## Selected Projects
- ........
- 🤔🤔🤔🤔🤔🤔

~只是一个随意的模板~
""",
    "location": " your-city",
    "email": "your-email@example.com",
}


def _clear_seed_data(session: Session) -> None:
    _logger = logging.getLogger("aerisun.seed")
    _logger.info("Force reseed: clearing existing seed data...")
    for model in [
        ContentCategory,
        Comment,
        GuestbookEntry,
        Reaction,
        ApiKey,
        AgentRun,
        AgentRunStep,
        AgentRunApproval,
        WorkflowGateState,
        WorkflowGateBufferItem,
        WorkflowBuildTask,
        WorkflowBuildTaskStep,
        WebhookSubscription,
        WebhookDelivery,
        WebhookDeadLetter,
        SiteAdminIdentity,
        SiteUserSession,
        SiteUserOAuthAccount,
        SiteUser,
        SiteAuthConfig,
        ContentSubscriptionConfig,
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
        ConfigRevision,
        AuditLog,
        AdminUser,
    ]:
        count = session.query(model).delete()
        if count:
            _logger.info("  Cleared %d rows from %s", count, model.__tablename__)
    session.flush()


def _seed_nav_items(session: Session, *, site_id: str) -> None:
    if not is_empty(session, NavItem):
        return

    label_to_id: dict[str, str] = {}
    for item_data in DEFAULT_NAV_ITEMS:
        if "_parent_label" in item_data:
            continue
        nav = NavItem(
            site_profile_id=site_id,
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
        parent_label = item_data.get("_parent_label")
        if parent_label is None:
            continue
        session.add(
            NavItem(
                site_profile_id=site_id,
                parent_id=label_to_id[parent_label],
                label=item_data["label"],
                href=item_data["href"],
                page_key=item_data.get("page_key"),
                trigger=item_data.get("trigger", "none"),
                order_index=item_data["order_index"],
            )
        )


def _seed_bootstrap_reference_data(*, force: bool = False) -> None:
    get_settings().ensure_directories()
    init_db()
    session = get_session_factory()()
    try:
        if force:
            _clear_seed_data(session)
            clear_waline_seed_data()

        frontend_public_dir = BACKEND_ROOT.parent / "frontend" / "public"
        frontend_public_images = frontend_public_dir / "images"
        seeded_og_image = ensure_seed_asset(
            session,
            source_path=frontend_public_images / "hero_bg.jpeg",
            category="site-og",
            note="站点默认 OG 分享图（生产初始化）",
        )
        seeded_site_icon = ensure_seed_asset(
            session,
            source_path=frontend_public_dir / "favicon.svg",
            category="site-icon",
            note="站点默认标签页图标（生产初始化）",
        )
        seeded_hero_image = ensure_seed_asset(
            session,
            source_path=frontend_public_images / "avatar.webp",
            category="hero-image",
            note="首页 Hero 默认视觉图（生产初始化）",
        )
        seeded_hero_poster = ensure_seed_asset(
            session,
            source_path=frontend_public_images / "hero_bg.jpeg",
            category="hero-poster",
            note="首页 Hero 视频默认封面图（生产初始化）",
        )
        seeded_resume_avatar = ensure_seed_asset(
            session,
            source_path=frontend_public_images / "avatar.webp",
            category="resume-avatar",
            note="简历默认头像（生产初始化）",
        )

        if is_empty(session, SiteProfile):
            site = SiteProfile(
                **{
                    **DEFAULT_SITE_PROFILE,
                    "og_image": seeded_og_image,
                    "site_icon_url": seeded_site_icon,
                    "hero_image_url": seeded_hero_image,
                    "hero_poster_url": seeded_hero_poster,
                }
            )
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

            resume = ResumeBasics(**{**DEFAULT_RESUME, "profile_image_url": seeded_resume_avatar})
            session.add(resume)
            session.flush()

        seed_missing_page_copies(session, DEFAULT_PAGE_COPIES)

        current_site = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
        if current_site is not None:
            current_site.og_image = ensure_system_asset_reference(
                session,
                source_value=current_site.og_image,
                category="site-og",
                note="站点分享图（系统资源归拢）",
                public_root=frontend_public_dir,
            )
            current_site.site_icon_url = ensure_system_asset_reference(
                session,
                source_value=current_site.site_icon_url,
                category="site-icon",
                note="站点标签页图标（系统资源归拢）",
                public_root=frontend_public_dir,
            )
            current_site.hero_image_url = ensure_system_asset_reference(
                session,
                source_value=current_site.hero_image_url,
                category="hero-image",
                note="首页 Hero 视觉图（系统资源归拢）",
                public_root=frontend_public_dir,
            )
            current_site.hero_poster_url = ensure_system_asset_reference(
                session,
                source_value=current_site.hero_poster_url,
                category="hero-poster",
                note="首页 Hero 视频封面图（系统资源归拢）",
                public_root=frontend_public_dir,
            )
            current_site.hero_video_url = (
                ensure_system_asset_reference(
                    session,
                    source_value=current_site.hero_video_url,
                    category="hero-video",
                    note="首页 Hero 背景视频（系统资源归拢）",
                    public_root=frontend_public_dir,
                )
                or None
            )

        current_resume = session.scalars(select(ResumeBasics).order_by(ResumeBasics.created_at.asc())).first()
        if current_resume is not None:
            current_resume.profile_image_url = ensure_system_asset_reference(
                session,
                source_value=current_resume.profile_image_url,
                category="resume-avatar",
                note="简历默认头像（系统资源归拢）",
                public_root=frontend_public_dir,
            )

        current_site = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
        if current_site is not None:
            _seed_nav_items(session, site_id=current_site.id)

        _seed_community_config(session, force=force)
        _seed_site_auth_config(session, force=force)
        _seed_subscription_config_from_settings(session, force=force)
        _seed_agent_model_config(session, force=force)
        _seed_config_history_and_audit(session)
        seed_dev_admin(session)
        session.commit()
    finally:
        session.close()


def seed_bootstrap_data(*, force: bool = False) -> None:
    _seed_bootstrap_reference_data(force=force)


def seed_reference_data(*, force: bool = False) -> None:
    """Production-safe seed entrypoint."""
    seed_bootstrap_data(force=force)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Aerisun production bootstrap data.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="clear existing seed data before reseeding",
    )
    args = parser.parse_args()
    seed_bootstrap_data(force=args.force)


if __name__ == "__main__":
    main()
