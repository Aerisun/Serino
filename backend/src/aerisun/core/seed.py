from __future__ import annotations

import argparse
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

import aerisun.domain.automation.models
import aerisun.domain.subscription.models  # noqa: F401
from aerisun.core.data_migrations.state import clear_migration_journal
from aerisun.core.seed_steps.common import is_empty
from aerisun.core.seed_steps.content import seed_missing_page_copies
from aerisun.core.seed_steps.system_assets import normalize_core_system_asset_references
from aerisun.core.settings import get_settings
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
from aerisun.domain.automation.settings import AGENT_MODEL_CONFIG_FLAG_KEY, DEFAULT_AGENT_MODEL_CONFIG
from aerisun.domain.content.models import ContentCategory, DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.engagement.models import Comment, GuestbookEntry, Reaction
from aerisun.domain.iam.models import AdminUser, ApiKey
from aerisun.domain.media.models import Asset
from aerisun.domain.ops.config_revisions import capture_config_resource, create_config_revision
from aerisun.domain.ops.models import AuditLog, ConfigRevision, TrafficDailySnapshot, VisitRecord
from aerisun.domain.site_auth.config_service import build_default_site_auth_config
from aerisun.domain.site_auth.models import (
    SiteAdminIdentity,
    SiteAuthConfig,
    SiteUser,
    SiteUserOAuthAccount,
    SiteUserSession,
)
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
            "applicationMarkdown": (
                "## 友链申请\n\n"
                "站点链接：:copy[https://your_site.com]\n\n"
                "站长昵称：:copy[uName]\n\n"
                "站长头像：:copy[资源里面上传存放公开的资源链接]\n\n"
                "站点描述：:copy[your bio]\n\n"
                "RSS 链接（可选）：:copy[https://your_site.com/rss]\n\n"
                "申请时还请按照上述模板留言，同时注意：\n\n"
                "- 申请友链前请务必确保贵站有我站的友链\n\n"
                "- 确保您的网站合法合规，不侵犯读者权益\n\n"
                "- 请确保您的站点可以被稳定访问"
            ),
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
            {"key": "friends", "label": "友链申请", "path": "/friends", "enabled": True},
            {"key": "thoughts", "label": "碎碎念评论", "path": "/thoughts/{slug}", "enabled": True},
            {"key": "excerpts", "label": "文摘评论", "path": "/excerpts/{slug}", "enabled": True},
        ],
        "meta": ["nick", "mail"],
        "required_meta": ["nick"],
        "emoji_presets": ["weibo", "qq", "tieba", "bilibili", "twemoji", "alus", "bmoji"],
        "image_uploader": True,
        "anonymous_enabled": True,
        "moderation_mode": "no_review",
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


def backfill_community_config_defaults(session: Session) -> None:
    default_config = build_default_community_config()
    config = session.scalars(select(CommunityConfig).order_by(CommunityConfig.created_at.asc())).first()

    if config is None:
        session.add(CommunityConfig(**default_config))
        return

    default_server_url = str(default_config["server_url"]).strip()
    config.server_url = _normalize_community_server_url(config.server_url, default_server_url)
    config.surfaces = _merge_community_surfaces(config.surfaces, list(default_config["surfaces"]))


def _seed_site_auth_config(session: Session, *, force: bool = False) -> None:
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


def backfill_site_auth_config_defaults(session: Session) -> None:
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


def _seed_subscription_config_from_settings(session: Session, *, force: bool = False) -> None:
    settings = get_settings()
    config = session.scalars(
        select(ContentSubscriptionConfig).order_by(ContentSubscriptionConfig.created_at.asc())
    ).first()
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


def backfill_subscription_config_defaults(session: Session) -> None:
    settings = get_settings()
    config = session.scalars(
        select(ContentSubscriptionConfig).order_by(ContentSubscriptionConfig.created_at.asc())
    ).first()
    if config is None:
        _seed_subscription_config_from_settings(session, force=True)
        return

    smtp_auth_mode = (settings.subscription_smtp_auth_mode or "password").strip().lower()
    if smtp_auth_mode not in {"password", "microsoft_oauth2"}:
        smtp_auth_mode = "password"

    if not (config.smtp_auth_mode or "").strip():
        config.smtp_auth_mode = smtp_auth_mode or "password"
    if not config.smtp_port:
        config.smtp_port = int(settings.subscription_smtp_port or 587)
    if not (config.smtp_oauth_tenant or "").strip():
        config.smtp_oauth_tenant = settings.subscription_smtp_oauth_tenant.strip() or "common"
    if not config.allowed_content_types:
        config.allowed_content_types = ["posts", "diary", "thoughts", "excerpts"]
    if not (config.mail_subject_template or "").strip():
        config.mail_subject_template = "[{site_name}] {content_title}"
    if not (config.mail_body_template or "").strip():
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


def backfill_agent_model_config_defaults(session: Session) -> None:
    _seed_agent_model_config(session, force=False)


def backfill_runtime_config_defaults(session: Session) -> None:
    backfill_site_auth_config_defaults(session)
    backfill_subscription_config_defaults(session)
    backfill_agent_model_config_defaults(session)


def _seed_config_history_and_audit(
    session: Session,
    *,
    resources: tuple[str, ...] = PRODUCTION_CONFIG_HISTORY_RESOURCES,
    operation: str = "baseline",
    summary_prefix: str = "生产 baseline 初始化",
) -> None:
    if not is_empty(session, ConfigRevision):
        return

    for resource_key in resources:
        snapshot = capture_config_resource(session, resource_key)
        create_config_revision(
            session,
            actor_id=None,
            resource_key=resource_key,
            operation=operation,
            before_snapshot=None,
            after_snapshot=snapshot,
            summary_override=f"{summary_prefix}：{resource_key}",
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
    clear_migration_journal(session)
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


def backfill_page_copy_defaults(session: Session) -> None:
    seed_missing_page_copies(session, DEFAULT_PAGE_COPIES)


def backfill_system_asset_references(session: Session) -> None:
    current_site = session.scalars(select(SiteProfile).order_by(SiteProfile.created_at.asc())).first()
    current_resume = session.scalars(select(ResumeBasics).order_by(ResumeBasics.created_at.asc())).first()
    normalize_core_system_asset_references(session, site=current_site, resume=current_resume)


def _seed_bootstrap_reference_data(*, force: bool = False) -> None:
    from aerisun.core.production_baseline import apply_production_baseline

    apply_production_baseline(force=force)


def seed_bootstrap_data(*, force: bool = False) -> None:
    _seed_bootstrap_reference_data(force=force)


def seed_reference_data(*, force: bool = False) -> None:
    """Reference-data compatibility wrapper used by development tooling."""
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
