from __future__ import annotations

import inspect
import types
from dataclasses import dataclass, field
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel
from sqlalchemy.orm import Session

from aerisun.api.admin.scopes import (
    ASSETS_READ,
    ASSETS_WRITE,
    AUTH_READ,
    AUTH_WRITE,
    AUTOMATION_READ,
    AUTOMATION_WRITE,
    CONFIG_READ,
    CONFIG_WRITE,
    CONTENT_READ,
    CONTENT_WRITE,
    MODERATION_READ,
    MODERATION_WRITE,
    NETWORK_READ,
    NETWORK_WRITE,
    SUBSCRIPTIONS_READ,
    SUBSCRIPTIONS_WRITE,
    SYSTEM_READ,
    SYSTEM_WRITE,
    VISITORS_READ,
    VISITORS_WRITE,
)
from aerisun.domain.agent.capability_ids import build_capability_id
from aerisun.domain.agent.mcp_admin_tools import (
    bind_admin_identity_email,
    bulk_delete_admin_assets,
    bulk_delete_admin_content,
    bulk_update_admin_content_status,
    check_friend_item,
    connect_telegram_webhook_item,
    create_admin_api_key,
    create_admin_content,
    create_admin_content_category,
    create_admin_record,
    create_agent_workflow_item,
    create_backup_snapshot_item,
    create_friend_feed_source,
    create_webhook_subscription_item,
    delete_admin_api_key,
    delete_admin_asset_item,
    delete_admin_content,
    delete_admin_content_category,
    delete_admin_identity_binding,
    delete_admin_record,
    delete_agent_workflow_item,
    delete_friend_feed_source,
    delete_subscription_subscriber,
    delete_webhook_subscription_item,
    export_content,
    generate_diary_poem,
    get_admin_asset_item,
    get_admin_community_config_state,
    get_admin_content,
    get_admin_login_options_state,
    get_admin_me,
    get_admin_record,
    get_admin_site_profile_config,
    get_agent_model_config_state,
    get_agent_run_detail_state,
    get_agent_workflow_catalog_state,
    get_backup_sync_config_state,
    get_config_revision_detail_state,
    get_dashboard_stats_state,
    get_outbound_proxy_config_state,
    get_subscription_config_state,
    get_system_info_state,
    get_visitor_auth_config_state,
    import_content,
    list_admin_api_keys_state,
    list_admin_assets_collection,
    list_admin_content,
    list_admin_content_categories,
    list_admin_identity_bindings,
    list_admin_records,
    list_admin_sessions,
    list_admin_tags,
    list_agent_runs_state,
    list_agent_workflows_state,
    list_audit_logs_state,
    list_backup_snapshots_state,
    list_backup_sync_commits_state,
    list_backup_sync_queue_state,
    list_backup_sync_runs_state,
    list_comment_queue,
    list_config_revisions_state,
    list_friend_feed_sources,
    list_guestbook_queue,
    list_pending_approvals_state,
    list_subscription_delivery_history,
    list_subscription_subscribers,
    list_visitor_records_state,
    list_visitor_users,
    list_webhook_dead_letters_state,
    list_webhook_deliveries_state,
    list_webhook_subscriptions_state,
    moderate_comment_item,
    moderate_guestbook_item,
    pause_backup_sync_item,
    reorder_admin_nav_records,
    replay_webhook_dead_letter_item,
    resolve_workflow_approval_item,
    restore_backup_commit_item,
    restore_backup_snapshot_item,
    restore_config_revision_item,
    resume_backup_sync_item,
    retry_backup_sync_run_item,
    retry_webhook_delivery_item,
    revoke_admin_session_item,
    test_agent_model_config,
    test_backup_sync_config,
    test_proxy_config_item,
    test_subscription_config,
    test_webhook_subscription_item,
    test_workflow_run,
    trigger_backup_sync_item,
    trigger_feed_crawl,
    trigger_workflow_run,
    update_admin_api_key,
    update_admin_asset_item,
    update_admin_community_config_state,
    update_admin_content,
    update_admin_content_category,
    update_admin_profile_item,
    update_admin_record,
    update_admin_site_profile_config,
    update_agent_model_config_item,
    update_agent_workflow_item,
    update_backup_sync_config_item,
    update_friend_feed_source,
    update_mcp_admin_config_item,
    update_proxy_config_item,
    update_subscription_config,
    update_subscription_subscriber,
    update_visitor_auth_config,
    update_webhook_subscription_item,
    upload_admin_asset_item,
    validate_agent_workflow,
)
from aerisun.domain.agent.schemas import AgentUsageCapabilityRead
from aerisun.domain.content.feed_service import build_posts_rss_xml
from aerisun.domain.content.search_service import search_public_content
from aerisun.domain.content.service import (
    list_public_diary_entries,
    list_public_excerpts,
    list_public_posts,
    list_public_thoughts,
)
from aerisun.domain.site_config.service import get_site_config

CapabilityKind = Literal["tool", "resource"]
CapabilityResponseKind = Literal["json", "text"]


def _json_schema_for_annotation(annotation: Any) -> dict[str, Any]:
    if annotation in (inspect.Signature.empty, Any, object):
        return {"type": "object"}
    if annotation is str:
        return {"type": "string"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation is type(None):
        return {"type": "null"}

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (list, tuple, set):
        item_schema = _json_schema_for_annotation(args[0]) if args else {"type": "object"}
        return {"type": "array", "items": item_schema}
    if origin is dict:
        return {"type": "object"}
    if origin is Literal:
        enum_values = list(args)
        literal_types = {type(item) for item in enum_values}
        if literal_types == {str}:
            return {"type": "string", "enum": enum_values}
        if literal_types == {int}:
            return {"type": "integer", "enum": enum_values}
        if literal_types == {float}:
            return {"type": "number", "enum": enum_values}
        if literal_types == {bool}:
            return {"type": "boolean", "enum": enum_values}
        return {"enum": enum_values}
    if origin in (types.UnionType, None) and isinstance(annotation, types.UnionType):
        args = annotation.__args__
        origin = types.UnionType
    if origin in (types.UnionType, Union):
        non_none = [item for item in args if item is not type(None)]
        if len(non_none) == 1 and len(non_none) != len(args):
            schema = dict(_json_schema_for_annotation(non_none[0]))
            schema["nullable"] = True
            return schema
        return {"anyOf": [_json_schema_for_annotation(item) for item in args]}

    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return annotation.model_json_schema()

    return {"type": "object"}


def _build_input_schema(handler: Any) -> dict[str, Any]:
    signature = inspect.signature(handler)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for index, parameter in enumerate(signature.parameters.values()):
        if index == 0 and parameter.name == "session":
            continue
        if parameter.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        properties[parameter.name] = _json_schema_for_annotation(parameter.annotation)
        if parameter.default is inspect.Signature.empty:
            required.append(parameter.name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _build_output_schema(handler: Any) -> dict[str, Any]:
    signature = inspect.signature(handler)
    return _json_schema_for_annotation(signature.return_annotation)


@dataclass(frozen=True, slots=True)
class AgentCapabilityDefinition:
    kind: CapabilityKind
    name: str
    description: str
    required_scopes: tuple[str, ...]
    handler: Any
    invocation: dict[str, Any]
    response_kind: CapabilityResponseKind = "json"
    examples: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    # ── 统一元数据 ──
    intent: str = "read"
    label: str = ""
    label_en: str = ""
    help_text: str = ""
    help_text_en: str = ""
    ai_usage_hint: str = ""
    domain: str = ""
    group_label: str = ""
    risk_level: str = "low"
    approval_policy: str = "risk_based"
    # ── 自动推导 ──
    input_schema: dict[str, Any] = field(init=False)
    output_schema: dict[str, Any] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_schema", _build_input_schema(self.handler))
        object.__setattr__(self, "output_schema", _build_output_schema(self.handler))

    @property
    def id(self) -> str:
        return build_capability_id(self.kind, self.name)

    @property
    def requires_approval(self) -> bool:
        if self.approval_policy in ("always", "manual"):
            return True
        return self.approval_policy == "risk_based" and self.risk_level in ("high", "critical")

    @property
    def resolved_label(self) -> str:
        return self.label or self.name.replace("_", " ").title()

    @property
    def resolved_label_en(self) -> str:
        return self.label_en or self.name.replace("_", " ").title()

    def to_usage_model(self) -> AgentUsageCapabilityRead:
        return AgentUsageCapabilityRead(
            id=self.id,
            name=self.name,
            kind=self.kind,
            description=self.description,
            required_scopes=list(self.required_scopes),
            invocation={
                **self.invocation,
                "input_schema": self.input_schema,
                "output_schema": self.output_schema,
            },
            examples=list(self.examples),
        )


def _tool(
    name: str,
    description: str,
    required_scopes: list[str],
    handler: Any,
    *,
    examples: list[dict[str, Any]] | None = None,
    intent: str = "read",
    label: str = "",
    label_en: str = "",
    help_text: str = "",
    help_text_en: str = "",
    ai_usage_hint: str = "",
    domain: str = "",
    group_label: str = "",
    risk_level: str = "low",
    approval_policy: str = "risk_based",
) -> AgentCapabilityDefinition:
    return AgentCapabilityDefinition(
        kind="tool",
        name=name,
        description=description,
        required_scopes=tuple(required_scopes),
        handler=handler,
        invocation={"transport": "mcp", "tool": name},
        examples=tuple(examples or ()),
        intent=intent,
        label=label,
        label_en=label_en,
        help_text=help_text,
        help_text_en=help_text_en,
        ai_usage_hint=ai_usage_hint,
        domain=domain,
        group_label=group_label,
        risk_level=risk_level,
        approval_policy=approval_policy,
    )


def _resource(
    name: str,
    description: str,
    required_scopes: list[str],
    handler: Any,
    *,
    response_kind: CapabilityResponseKind = "json",
    examples: list[dict[str, Any]] | None = None,
    intent: str = "read",
    label: str = "",
    label_en: str = "",
    help_text: str = "",
    help_text_en: str = "",
    domain: str = "",
    group_label: str = "",
) -> AgentCapabilityDefinition:
    return AgentCapabilityDefinition(
        kind="resource",
        name=name,
        description=description,
        required_scopes=tuple(required_scopes),
        handler=handler,
        invocation={"transport": "mcp", "resource": name},
        response_kind=response_kind,
        examples=tuple(examples or ()),
        intent=intent,
        label=label,
        label_en=label_en,
        help_text=help_text,
        help_text_en=help_text_en,
        domain=domain,
        group_label=group_label,
    )


def _get_site_config_tool(session: Session) -> dict[str, Any]:
    return get_site_config(session).model_dump()


def _list_posts_tool(session: Session, limit: int = 20, offset: int = 0) -> dict[str, Any]:
    return list_public_posts(session, limit=limit, offset=offset).model_dump()


def _search_content_tool(session: Session, query: str, limit: int = 10) -> dict[str, Any]:
    return search_public_content(session, query, limit).model_dump()


def _list_diary_entries_tool(session: Session, limit: int = 20, offset: int = 0) -> dict[str, Any]:
    return list_public_diary_entries(session, limit=limit, offset=offset).model_dump()


def _list_thoughts_tool(session: Session, limit: int = 40, offset: int = 0) -> dict[str, Any]:
    return list_public_thoughts(session, limit=limit, offset=offset).model_dump()


def _list_excerpts_tool(session: Session, limit: int = 40, offset: int = 0) -> dict[str, Any]:
    return list_public_excerpts(session, limit=limit, offset=offset).model_dump()


def _list_admin_tags_tool(session: Session) -> dict[str, Any]:
    return {"items": list_admin_tags(session)}


def _list_admin_content_categories_tool(session: Session, content_type: str | None = None) -> dict[str, Any]:
    return {"items": list_admin_content_categories(session, content_type=content_type)}


def _reorder_admin_nav_items_tool(session: Session, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"items": reorder_admin_nav_records(session, items=items)}


def _list_friend_feed_sources_tool(session: Session, friend_id: str) -> dict[str, Any]:
    return {"items": list_friend_feed_sources(session, friend_id=friend_id)}


def _posts_feed_resource(session: Session) -> str:
    return build_posts_rss_xml(session, "http://localhost")


def _posts_resource(session: Session) -> Any:
    return list_public_posts(session, limit=20, offset=0)


def _diary_resource(session: Session) -> Any:
    return list_public_diary_entries(session, limit=20, offset=0)


def _thoughts_resource(session: Session) -> Any:
    return list_public_thoughts(session, limit=40, offset=0)


def _excerpts_resource(session: Session) -> Any:
    return list_public_excerpts(session, limit=40, offset=0)


_CAPABILITIES: tuple[AgentCapabilityDefinition, ...] = (
    # ═══════════════════════════════════════════════════════════════════════════
    # MCP Resources
    # ═══════════════════════════════════════════════════════════════════════════
    _resource(
        "aerisun://site-config",
        "Return site config as JSON.",
        [CONFIG_READ],
        get_site_config,
        label="站点配置",
        label_en="Site config",
        help_text="以 JSON 格式返回站点全局配置，包含名称、描述、功能开关等。",
        help_text_en="Return site configuration as JSON including name, description, and feature flags.",
        domain="site",
        group_label="站点",
    ),
    _resource(
        "aerisun://posts",
        "Return latest posts list as JSON.",
        [CONTENT_READ],
        _posts_resource,
        label="最新文章",
        label_en="Latest posts",
        help_text="以 JSON 格式返回最新已发布文章列表。",
        help_text_en="Return latest published posts as a JSON list.",
        domain="content",
        group_label="内容",
    ),
    _resource(
        "aerisun://diary",
        "Return latest diary entries as JSON.",
        [CONTENT_READ],
        _diary_resource,
        label="最新日记",
        label_en="Latest diary",
        help_text="以 JSON 格式返回最新已发布日记条目。",
        help_text_en="Return latest published diary entries as a JSON list.",
        domain="content",
        group_label="内容",
    ),
    _resource(
        "aerisun://thoughts",
        "Return latest thoughts as JSON.",
        [CONTENT_READ],
        _thoughts_resource,
        label="最新想法",
        label_en="Latest thoughts",
        help_text="以 JSON 格式返回最新已发布的想法。",
        help_text_en="Return latest published thoughts as a JSON list.",
        domain="content",
        group_label="内容",
    ),
    _resource(
        "aerisun://excerpts",
        "Return latest excerpts as JSON.",
        [CONTENT_READ],
        _excerpts_resource,
        label="最新摘录",
        label_en="Latest excerpts",
        help_text="以 JSON 格式返回最新已发布的摘录。",
        help_text_en="Return latest published excerpts as a JSON list.",
        domain="content",
        group_label="内容",
    ),
    _resource(
        "aerisun://feeds/posts",
        "Return the posts RSS XML.",
        [CONTENT_READ],
        _posts_feed_resource,
        response_kind="text",
        label="文章 RSS",
        label_en="Posts RSS feed",
        help_text="以 RSS XML 格式返回文章订阅源。",
        help_text_en="Return the posts feed as RSS XML.",
        domain="content",
        group_label="内容",
    ),
    # ═══════════════════════════════════════════════════════════════════════════
    # CONTENT — 内容
    # ═══════════════════════════════════════════════════════════════════════════
    _tool(
        "get_site_config",
        "Get current site config including name, description, and feature flags.",
        [CONFIG_READ],
        _get_site_config_tool,
        label="站点配置",
        label_en="Site config",
        help_text="获取站点基础配置，包含站点名称、描述、功能开关等。",
        help_text_en="Get site config including name, description, and feature flags.",
        ai_usage_hint="获取站点全局配置。返回站点名、描述、语言、功能开关等。不需要参数。",
        examples=[{"arguments": {}, "scenario": "读取站点基础配置用于判断功能入口。"}],
        domain="site",
        group_label="站点",
    ),
    _tool(
        "list_posts",
        "List published posts with pagination.",
        [CONTENT_READ],
        _list_posts_tool,
        label="公开文章列表",
        label_en="List posts",
        help_text="获取已发布的文章列表，支持分页。",
        help_text_en="List published posts with pagination support.",
        ai_usage_hint="列出已发布的公开文章。limit 默认 20，offset 默认 0。返回公开可见的文章摘要列表。",
        examples=[{"arguments": {"limit": 10, "offset": 0}, "scenario": "列出最近文章。"}],
        domain="content",
        group_label="内容",
    ),
    _tool(
        "search_content",
        "Full-text search across all public content types.",
        [CONTENT_READ],
        _search_content_tool,
        label="搜索内容",
        label_en="Search content",
        help_text="全文搜索所有公开内容（文章、日记、想法、摘录）。",
        help_text_en="Full-text search across all public content types.",
        ai_usage_hint="全文检索公开内容。query 必传（关键词），limit 默认 10。搜索范围涵盖文章、日记、想法、摘录。",
        examples=[{"arguments": {"query": "诗", "limit": 5}, "scenario": "按关键词搜索公开内容。"}],
        domain="content",
        group_label="内容",
    ),
    _tool(
        "list_diary_entries",
        "List published diary entries with pagination.",
        [CONTENT_READ],
        _list_diary_entries_tool,
        label="公开日记列表",
        label_en="List diary",
        help_text="获取已发布的日记列表，支持分页。",
        help_text_en="List published diary entries with pagination.",
        ai_usage_hint="列出已发布的公开日记。limit 默认 20，offset 默认 0。",
        examples=[{"arguments": {"limit": 10, "offset": 0}, "scenario": "列出最近 10 篇公开日记。"}],
        domain="content",
        group_label="内容",
    ),
    _tool(
        "list_thoughts",
        "List published thoughts with pagination.",
        [CONTENT_READ],
        _list_thoughts_tool,
        label="公开想法列表",
        label_en="List thoughts",
        help_text="获取已发布的想法列表，支持分页。",
        help_text_en="List published thoughts (short-form notes) with pagination.",
        ai_usage_hint="列出已发布的公开想法。limit 默认 40，offset 默认 0。",
        examples=[{"arguments": {"limit": 20, "offset": 0}, "scenario": "列出最近 20 条公开想法。"}],
        domain="content",
        group_label="内容",
    ),
    _tool(
        "list_excerpts",
        "List published excerpts with pagination.",
        [CONTENT_READ],
        _list_excerpts_tool,
        label="公开摘录列表",
        label_en="List excerpts",
        help_text="获取已发布的摘录列表，支持分页。",
        help_text_en="List published excerpts (quotes/clips) with pagination.",
        ai_usage_hint="列出已发布的公开摘录。limit 默认 40，offset 默认 0。",
        examples=[{"arguments": {"limit": 20, "offset": 0}, "scenario": "列出最近 20 条公开摘录。"}],
        domain="content",
        group_label="内容",
    ),
    _tool(
        "list_admin_content",
        "List admin content items with filtering and sorting.",
        [CONTENT_READ],
        list_admin_content,
        label="后台内容列表",
        label_en="List content (admin)",
        help_text="查看后台所有内容项（文章、日记、想法、摘录），支持按状态、可见性、标签筛选和排序。",
        help_text_en="Browse admin content (posts, diary, thoughts, excerpts) with filters.",
        ai_usage_hint=(
            "查询后台内容列表。content_type 必传，值为 posts/diary/thoughts/excerpts 之一。"
            "可选参数：status(draft/published/archived), visibility(public/private), "
            "tag(标签名), search(关键词), sort_by(created_at/updated_at/published_at), "
            "sort_order(asc/desc), page(页码,默认1), page_size(每页条数,默认20)。"
        ),
        examples=[{"arguments": {"content_type": "posts", "status": "draft"}, "scenario": "查看草稿文章列表。"}],
        domain="content",
        group_label="内容",
    ),
    _tool(
        "get_admin_content",
        "Get one admin content item by ID with full body and metadata.",
        [CONTENT_READ],
        get_admin_content,
        label="后台内容详情",
        label_en="Get content (admin)",
        help_text="按 ID 获取单个后台内容项的完整信息，包含正文、元数据。",
        help_text_en="Get a single admin content item by ID with full body and metadata.",
        ai_usage_hint="获取单条后台内容详情。content_type 必传 (posts/diary/thoughts/excerpts)，item_id 必传。",
        examples=[
            {"arguments": {"content_type": "posts", "item_id": "abc-123"}, "scenario": "获取指定文章的完整内容。"}
        ],
        domain="content",
        group_label="内容",
    ),
    _tool(
        "create_admin_content",
        "Create an admin content item with initial status and visibility.",
        [CONTENT_WRITE],
        create_admin_content,
        intent="write",
        label="创建内容",
        label_en="Create content",
        help_text="创建一条后台内容（文章、日记、想法或摘录），可设置初始状态和可见性。slug 自动生成。",
        help_text_en="Create a content item with initial status and visibility. Slug is auto-generated.",
        ai_usage_hint=(
            "创建后台内容。content_type 必传 (posts/diary/thoughts/excerpts)。"
            "payload 字典，可选字段：title(标题,日记和想法可省略), body(正文,必传), "
            "summary(摘要), tags(标签列表), status(draft/published/archived,默认draft), "
            "visibility(public/private,默认public), category(分类名), "
            "mood(心情,仅diary/thoughts), weather(天气,仅diary)。"
            "slug 自动生成，不要传入。"
        ),
        examples=[
            {
                "arguments": {
                    "content_type": "posts",
                    "payload": {"title": "新文章", "body": "正文", "status": "draft"},
                },
                "scenario": "创建一篇草稿文章。",
            }
        ],
        domain="content",
        group_label="内容",
        risk_level="medium",
        approval_policy="manual",
    ),
    _tool(
        "update_admin_content",
        "Update an admin content item including body, status, and visibility.",
        [CONTENT_WRITE],
        update_admin_content,
        intent="write",
        label="更新内容",
        label_en="Update content",
        help_text="更新后台内容项，包括正文、状态和可见性。",
        help_text_en="Update a content item including body, status, and visibility.",
        ai_usage_hint=(
            "更新后台内容。content_type 必传 (posts/diary/thoughts/excerpts)，item_id 必传。"
            "payload 字典，可选字段与创建相同。只传需要修改的字段即可，未传字段保持不变。"
            '切换状态：payload={"status": "published"}。切换可见性：payload={"visibility": "private"}。'
        ),
        examples=[
            {
                "arguments": {"content_type": "posts", "item_id": "content-id", "payload": {"status": "published"}},
                "scenario": "发布一篇文章。",
            },
            {
                "arguments": {"content_type": "posts", "item_id": "content-id", "payload": {"visibility": "private"}},
                "scenario": "把内容改成私有。",
            },
        ],
        domain="content",
        group_label="内容",
        risk_level="high",
    ),
    _tool(
        "delete_admin_content",
        "Delete one admin content item permanently.",
        [CONTENT_WRITE],
        delete_admin_content,
        intent="write",
        label="删除内容",
        label_en="Delete content",
        help_text="永久删除单个后台内容项，不可恢复。",
        help_text_en="Permanently delete one admin content item.",
        ai_usage_hint="删除单条后台内容。content_type 必传，item_id 必传。操作不可恢复。",
        examples=[{"arguments": {"content_type": "diary", "item_id": "abc-123"}, "scenario": "删除一篇日记。"}],
        domain="content",
        group_label="内容",
        risk_level="high",
    ),
    _tool(
        "bulk_delete_admin_content",
        "Bulk-delete multiple admin content items.",
        [CONTENT_WRITE],
        bulk_delete_admin_content,
        intent="write",
        label="批量删除内容",
        label_en="Bulk delete content",
        help_text="批量删除后台内容项，不可恢复。",
        help_text_en="Bulk-delete multiple admin content items permanently.",
        ai_usage_hint="批量删除后台内容。content_type 必传，ids 必传（ID 列表）。操作不可恢复。",
        examples=[{"arguments": {"content_type": "posts", "ids": ["id-1", "id-2"]}, "scenario": "批量删除两篇文章。"}],
        domain="content",
        group_label="内容",
        risk_level="critical",
    ),
    _tool(
        "bulk_update_admin_content_status",
        "Bulk update content status for publishing, archiving, or drafting.",
        [CONTENT_WRITE],
        bulk_update_admin_content_status,
        intent="write",
        label="批量修改状态",
        label_en="Bulk update status",
        help_text="批量切换内容状态，例如发布、归档或改回草稿。",
        help_text_en="Bulk update content status (publish, archive, or revert to draft).",
        ai_usage_hint=(
            "批量修改内容状态。content_type 必传，ids 必传（ID 列表），status 必传 (draft/published/archived)。"
        ),
        examples=[
            {
                "arguments": {"content_type": "posts", "ids": ["id-1", "id-2"], "status": "published"},
                "scenario": "批量发布两篇文章。",
            }
        ],
        domain="content",
        group_label="内容",
        risk_level="high",
    ),
    _tool(
        "list_admin_tags",
        "List all tags aggregated across admin content.",
        [CONTENT_READ],
        _list_admin_tags_tool,
        label="标签列表",
        label_en="List tags",
        help_text="列出所有后台内容中使用的标签（聚合去重）。",
        help_text_en="List all tags aggregated across admin content items.",
        ai_usage_hint="获取后台内容使用的所有标签（聚合去重）。不需要参数。返回 {items: [...]} 格式。",
        examples=[{"arguments": {}, "scenario": "获取所有后台标签用于内容筛选。"}],
        domain="content",
        group_label="内容",
    ),
    _tool(
        "list_admin_content_categories",
        "List managed content categories, optionally filtered by content type.",
        [CONTENT_READ],
        _list_admin_content_categories_tool,
        label="分类列表",
        label_en="List categories",
        help_text="列出后台内容分类，可按内容类型筛选。",
        help_text_en="List managed content categories, optionally filtered by content type.",
        ai_usage_hint="获取内容分类列表。可选参数 content_type (posts/diary/thoughts/excerpts) 用于过滤。",
        examples=[{"arguments": {"content_type": "posts"}, "scenario": "获取文章的分类列表。"}],
        domain="content",
        group_label="内容",
    ),
    _tool(
        "create_admin_content_category",
        "Create a content category for organizing posts, diary, etc.",
        [CONTENT_WRITE],
        create_admin_content_category,
        intent="write",
        label="创建分类",
        label_en="Create category",
        help_text="创建后台内容分类。",
        help_text_en="Create a content category for organizing admin content.",
        ai_usage_hint="创建内容分类。content_type 必传 (posts/diary/thoughts/excerpts)，name 必传（分类名）。",
        examples=[
            {"arguments": {"content_type": "posts", "name": "技术笔记"}, "scenario": "为文章创建一个「技术笔记」分类。"}
        ],
        domain="content",
        group_label="内容",
        risk_level="medium",
    ),
    _tool(
        "update_admin_content_category",
        "Rename or update a content category.",
        [CONTENT_WRITE],
        update_admin_content_category,
        intent="write",
        label="更新分类",
        label_en="Update category",
        help_text="更新后台内容分类名称。",
        help_text_en="Rename or update a content category.",
        ai_usage_hint="更新内容分类名称。category_id 必传，name 必传（新名称）。",
        examples=[
            {"arguments": {"category_id": "cat-123", "name": "开发日志"}, "scenario": "将分类重命名为「开发日志」。"}
        ],
        domain="content",
        group_label="内容",
        risk_level="medium",
    ),
    _tool(
        "delete_admin_content_category",
        "Delete a content category. Items in this category will become uncategorized.",
        [CONTENT_WRITE],
        delete_admin_content_category,
        intent="write",
        label="删除分类",
        label_en="Delete category",
        help_text="删除后台内容分类，已归类的内容将变为无分类。",
        help_text_en="Delete a content category. Items become uncategorized.",
        ai_usage_hint="删除内容分类。category_id 必传。已归类的内容会变成无分类，不会被删除。",
        examples=[{"arguments": {"category_id": "cat-123"}, "scenario": "删除一个内容分类。"}],
        domain="content",
        group_label="内容",
        risk_level="high",
    ),
    _tool(
        "export_content",
        "Export content items as JSON for backup or migration.",
        [CONTENT_READ],
        export_content,
        label="导出内容",
        label_en="Export content",
        help_text="将内容导出为 JSON 格式，可用于备份或迁移。",
        help_text_en="Export content items as JSON for backup or migration.",
        ai_usage_hint="导出后台内容为 JSON。content_type 必传 (posts/diary/thoughts/excerpts)。",
        examples=[{"arguments": {"content_type": "posts"}, "scenario": "导出所有文章为 JSON。"}],
        domain="content",
        group_label="内容",
    ),
    _tool(
        "import_content",
        "Import content from JSON data. Existing items with same slug will be updated.",
        [CONTENT_WRITE],
        import_content,
        intent="write",
        label="导入内容",
        label_en="Import content",
        help_text="从 JSON 数据导入内容，已有相同 slug 的条目会被更新。",
        help_text_en="Import content from JSON. Existing items with same slug will be updated.",
        ai_usage_hint=(
            "从 JSON 导入后台内容。content_type 必传，items 必传（内容列表）。"
            "已有相同 slug 的条目执行更新，无则创建。操作不可撤销，建议先导出备份。"
        ),
        examples=[
            {
                "arguments": {
                    "content_type": "posts",
                    "items": [{"title": "导入文章", "body": "正文内容", "status": "draft"}],
                },
                "scenario": "导入一篇草稿文章。",
            }
        ],
        domain="content",
        group_label="内容",
        risk_level="critical",
        approval_policy="always",
    ),
    _tool(
        "generate_diary_poem",
        "Generate a classical Chinese poem line matching the diary draft mood.",
        [CONTENT_WRITE],
        generate_diary_poem,
        intent="action",
        label="生成诗句",
        label_en="Generate poem",
        help_text="根据当前日记草稿内容和心情，AI 生成一句匹配的中文古典诗句。",
        help_text_en="AI-generate a classical Chinese poem line matching the diary draft mood.",
        ai_usage_hint="为日记草稿生成诗句。payload 必传（PoemGenerationRequest 或字典，含日记内容信息）。不会直接保存到日记，只返回生成的诗句供确认。",
        examples=[{"arguments": {"payload": {"diary_id": "abc-123"}}, "scenario": "为日记草稿生成一句古诗。"}],
        domain="content",
        group_label="内容",
        risk_level="medium",
        approval_policy="never",
    ),
    # ═══════════════════════════════════════════════════════════════════════════
    # MODERATION — 审核
    # ═══════════════════════════════════════════════════════════════════════════
    _tool(
        "list_comment_moderation_queue",
        "List comments awaiting moderation with pagination.",
        [MODERATION_READ],
        list_comment_queue,
        label="待审评论列表",
        label_en="Comment queue",
        help_text="列出等待审核的评论，支持按状态、路径、关键词等筛选和分页。",
        help_text_en="List comments awaiting moderation with filtering and pagination.",
        ai_usage_hint=(
            "获取评论审核队列。可选参数：page(页码,默认1), page_size(每页条数,默认20), "
            "status(状态筛选), path(页面路径筛选), surface(评论区筛选), "
            "keyword(关键词搜索), author(作者筛选), email(邮箱筛选), sort(排序方式)。"
        ),
        examples=[{"arguments": {"status": "pending", "page": 1, "page_size": 10}, "scenario": "查看待审核评论首页。"}],
        domain="moderation",
        group_label="审核",
    ),
    _tool(
        "moderate_comment",
        "Approve, reject, or delete one comment.",
        [MODERATION_WRITE],
        moderate_comment_item,
        intent="write",
        label="审核评论",
        label_en="Moderate comment",
        help_text="对单条评论执行通过、拒绝或删除操作。",
        help_text_en="Approve, reject, or delete one comment.",
        ai_usage_hint="审核一条评论。comment_id 必传，action 必传 (approve/reject/delete)。可选 reason（审核理由）。",
        examples=[{"arguments": {"comment_id": "123", "action": "approve"}, "scenario": "通过一条评论。"}],
        domain="moderation",
        group_label="审核",
        risk_level="medium",
    ),
    _tool(
        "list_guestbook_moderation_queue",
        "List guestbook entries awaiting moderation with pagination.",
        [MODERATION_READ],
        list_guestbook_queue,
        label="待审留言列表",
        label_en="Guestbook queue",
        help_text="列出等待审核的留言板条目，支持按状态、路径、关键词等筛选和分页。",
        help_text_en="List guestbook entries awaiting moderation with filtering and pagination.",
        ai_usage_hint=(
            "获取留言审核队列。可选参数：page(页码,默认1), page_size(每页条数,默认20), "
            "status(状态筛选), path(页面路径筛选), "
            "keyword(关键词搜索), author(作者筛选), email(邮箱筛选), sort(排序方式)。"
        ),
        examples=[{"arguments": {"status": "pending", "page": 1}, "scenario": "查看待审核留言首页。"}],
        domain="moderation",
        group_label="审核",
    ),
    _tool(
        "moderate_guestbook_entry",
        "Approve, reject, or delete one guestbook entry.",
        [MODERATION_WRITE],
        moderate_guestbook_item,
        intent="write",
        label="审核留言",
        label_en="Moderate guestbook",
        help_text="对单条留言执行通过、拒绝或删除操作。",
        help_text_en="Approve, reject, or delete one guestbook entry.",
        ai_usage_hint="审核一条留言。entry_id 必传，action 必传 (approve/reject/delete)。可选 reason。",
        examples=[{"arguments": {"entry_id": "entry-123", "action": "approve"}, "scenario": "通过一条留言。"}],
        domain="moderation",
        group_label="审核",
        risk_level="medium",
    ),
    # ═══════════════════════════════════════════════════════════════════════════
    # SITE — 站点配置
    # ═══════════════════════════════════════════════════════════════════════════
    _tool(
        "get_admin_site_profile",
        "Get admin site profile including name, avatar, SEO, and filing info.",
        [CONFIG_READ],
        get_admin_site_profile_config,
        label="站点资料",
        label_en="Site profile",
        help_text="获取站点资料设置，包含站点名、头像、SEO 和备案信息。",
        help_text_en="Get admin site profile including name, avatar, SEO, and filing info.",
        ai_usage_hint="获取站点资料配置详情。不需要参数。返回站点名、头像URL、SEO配置、备案号等。",
        examples=[{"arguments": {}, "scenario": "获取站点资料配置。"}],
        domain="site",
        group_label="站点",
    ),
    _tool(
        "update_admin_site_profile",
        "Update site profile settings like name, avatar, SEO, and filing info.",
        [CONFIG_WRITE],
        update_admin_site_profile_config,
        intent="write",
        label="更新站点资料",
        label_en="Update profile",
        help_text="更新站点资料设置，包含站点名、头像、SEO 和备案信息。",
        help_text_en="Update site profile settings like name, avatar, SEO, and filing info.",
        ai_usage_hint="更新站点资料。传入 payload 字典，可选字段：site_name, tagline, avatar_url, seo_title, seo_description, filing_info 等。只传需要修改的字段。",
        examples=[
            {
                "arguments": {"payload": {"site_name": "我的博客", "tagline": "记录生活"}},
                "scenario": "更新站点名称和标语。",
            }
        ],
        domain="site",
        group_label="站点",
        risk_level="high",
        approval_policy="manual",
    ),
    _tool(
        "get_admin_community_config",
        "Get comment and community interaction settings.",
        [CONFIG_READ],
        get_admin_community_config_state,
        label="社区配置",
        label_en="Community config",
        help_text="获取评论区和社区互动配置，包含评论开关、审核策略等。",
        help_text_en="Get comment and community interaction settings.",
        ai_usage_hint="获取社区互动配置。不需要参数。返回评论开关、审核策略、留言板开关等。",
        examples=[{"arguments": {}, "scenario": "获取社区互动配置。"}],
        domain="site",
        group_label="站点",
    ),
    _tool(
        "update_admin_community_config",
        "Update comment and community interaction settings.",
        [CONFIG_WRITE],
        update_admin_community_config_state,
        intent="write",
        label="更新社区配置",
        label_en="Update community",
        help_text="更新评论区和社区互动配置。",
        help_text_en="Update comment and community interaction settings.",
        ai_usage_hint="更新社区配置。传入 payload 字典，可选字段：comments_enabled, moderation_policy, guestbook_enabled 等。",
        examples=[{"arguments": {"payload": {"comments_enabled": True}}, "scenario": "开启评论功能。"}],
        domain="site",
        group_label="站点",
        risk_level="high",
        approval_policy="manual",
    ),
    _tool(
        "list_admin_records",
        "List generic admin records: friends, social_links, poems, page_copy, display_options, "
        "nav_items, resume_basics, resume_skills, or resume_experiences.",
        [CONFIG_READ],
        list_admin_records,
        label="通用记录列表",
        label_en="List records",
        help_text=(
            "列出通用后台记录。支持的 resource 类型：friends(友链), social_links(社交链接), "
            "poems(诗句), page_copy(页面文案), display_options(显示选项), nav_items(导航项), "
            "resume_basics(简历基础), resume_skills(技能组), resume_experiences(经历)。"
        ),
        help_text_en="List generic admin records by resource type (friends, social_links, poems, etc.).",
        ai_usage_hint=(
            "列出通用后台记录。resource 必传，可选值：friends, social_links, poems, page_copy, "
            "display_options, nav_items, resume_basics, resume_skills, resume_experiences。"
            "可选参数：page(页码,默认1), page_size(每页条数,默认20), "
            "search(关键词搜索), sort_by(排序字段,默认created_at), sort_order(asc/desc,默认desc)。"
        ),
        examples=[{"arguments": {"resource": "friends", "page": 1, "page_size": 20}, "scenario": "列出友链列表。"}],
        domain="site",
        group_label="站点",
    ),
    _tool(
        "get_admin_record",
        "Get one generic admin record by resource type and ID.",
        [CONFIG_READ],
        get_admin_record,
        label="通用记录详情",
        label_en="Get record",
        help_text="按 resource 类型和 ID 获取单条通用后台记录详情。",
        help_text_en="Get one generic admin record by resource type and ID.",
        ai_usage_hint="获取单条通用记录。resource 必传，item_id 必传。",
        examples=[{"arguments": {"resource": "friends", "item_id": "friend-123"}, "scenario": "获取单条友链详情。"}],
        domain="site",
        group_label="站点",
    ),
    _tool(
        "create_admin_record",
        "Create one generic admin record (friend, social link, poem, nav item, etc.).",
        [CONFIG_WRITE],
        create_admin_record,
        intent="write",
        label="创建记录",
        label_en="Create record",
        help_text="创建通用后台记录，覆盖友链、社交链接、诗句、页面文案、导航项、简历等。",
        help_text_en="Create one generic admin record (friend, social link, poem, nav item, resume, etc.).",
        ai_usage_hint=(
            "创建通用后台记录。resource 必传（friends/social_links/poems/page_copy/"
            "display_options/nav_items/resume_basics/resume_skills/resume_experiences），"
            "payload 必传（字段因 resource 类型而异）。"
        ),
        examples=[
            {
                "arguments": {
                    "resource": "friends",
                    "payload": {
                        "name": "示例博客",
                        "url": "https://example.com",
                        "avatar": "https://example.com/avatar.png",
                    },
                },
                "scenario": "创建一条友链。",
            }
        ],
        domain="site",
        group_label="站点",
        risk_level="medium",
    ),
    _tool(
        "update_admin_record",
        "Update one generic admin record by resource type and ID.",
        [CONFIG_WRITE],
        update_admin_record,
        intent="write",
        label="更新记录",
        label_en="Update record",
        help_text="更新通用后台记录。",
        help_text_en="Update one generic admin record by resource type and ID.",
        ai_usage_hint="更新通用记录。resource 必传，item_id 必传，payload 必传（只传需要修改的字段）。",
        examples=[
            {
                "arguments": {"resource": "friends", "item_id": "friend-123", "payload": {"name": "新名称"}},
                "scenario": "更新友链名称。",
            }
        ],
        domain="site",
        group_label="站点",
        risk_level="medium",
    ),
    _tool(
        "delete_admin_record",
        "Delete one generic admin record by resource type and ID.",
        [CONFIG_WRITE],
        delete_admin_record,
        intent="write",
        label="删除记录",
        label_en="Delete record",
        help_text="删除通用后台记录，操作不可恢复。",
        help_text_en="Delete one generic admin record permanently.",
        ai_usage_hint="删除通用记录。resource 必传，item_id 必传。操作不可恢复。",
        examples=[{"arguments": {"resource": "friends", "item_id": "friend-123"}, "scenario": "删除一条友链。"}],
        domain="site",
        group_label="站点",
        risk_level="high",
    ),
    _tool(
        "reorder_admin_nav_items",
        "Reorder navigation items by providing a new ordered list.",
        [CONFIG_WRITE],
        _reorder_admin_nav_items_tool,
        intent="action",
        label="重排导航项",
        label_en="Reorder nav",
        help_text="调整站点导航项的显示顺序。",
        help_text_en="Reorder navigation items by providing a new ordered list.",
        ai_usage_hint="重排导航项。items 必传，为包含 {id, order_index} 的列表，按目标顺序排列。",
        examples=[
            {
                "arguments": {"items": [{"id": "nav-1", "order_index": 0}, {"id": "nav-2", "order_index": 1}]},
                "scenario": "调整导航项顺序。",
            }
        ],
        domain="site",
        group_label="站点",
        risk_level="high",
    ),
    # ═══════════════════════════════════════════════════════════════════════════
    # ASSETS — 资源
    # ═══════════════════════════════════════════════════════════════════════════
    _tool(
        "list_admin_assets",
        "List uploaded assets from the admin library with pagination.",
        [ASSETS_READ],
        list_admin_assets_collection,
        label="资源列表",
        label_en="List assets",
        help_text="列出后台资源库中已上传的文件，支持分页。",
        help_text_en="List uploaded assets from the admin library with pagination.",
        ai_usage_hint=(
            "获取后台资源列表。可选参数：page(页码,默认1), page_size(每页条数,默认20), "
            "query(搜索关键词), scope(范围,默认user)。"
        ),
        examples=[{"arguments": {"page": 1, "page_size": 20}, "scenario": "浏览后台资源库首页。"}],
        domain="assets",
        group_label="资源",
    ),
    _tool(
        "get_admin_asset",
        "Get one admin asset by ID with full metadata.",
        [ASSETS_READ],
        get_admin_asset_item,
        label="资源详情",
        label_en="Get asset",
        help_text="按 ID 获取单个后台资源的完整元信息。",
        help_text_en="Get one admin asset by ID with full metadata.",
        ai_usage_hint="获取单个资源详情。asset_id 必传。",
        examples=[{"arguments": {"asset_id": "asset-123"}, "scenario": "获取单个资源详情。"}],
        domain="assets",
        group_label="资源",
    ),
    _tool(
        "upload_admin_asset",
        "Upload an asset to the admin library using base64-encoded file content.",
        [ASSETS_WRITE],
        upload_admin_asset_item,
        intent="write",
        label="上传资源",
        label_en="Upload asset",
        help_text="上传文件到后台资源库，使用 base64 编码的文件内容。",
        help_text_en="Upload an asset using base64-encoded file content.",
        ai_usage_hint=(
            "上传资源文件。file_name 必传（含扩展名），content_base64 必传（base64 编码的文件内容），"
            "可选：mime_type(MIME 类型), visibility(默认internal), "
            "scope(默认user), category(默认general), note(备注说明)。"
        ),
        examples=[
            {
                "arguments": {"file_name": "logo.png", "content_base64": "iVBORw0KGgo=", "mime_type": "image/png"},
                "scenario": "上传一张 PNG 图片。",
            }
        ],
        domain="assets",
        group_label="资源",
        risk_level="high",
        approval_policy="manual",
    ),
    _tool(
        "update_admin_asset",
        "Update asset metadata like description, visibility, or category.",
        [ASSETS_WRITE],
        update_admin_asset_item,
        intent="write",
        label="更新资源",
        label_en="Update asset",
        help_text="更新资源元信息，例如说明、可见性或分类。",
        help_text_en="Update asset metadata like description, visibility, or category.",
        ai_usage_hint="更新资源元信息。asset_id 必传，payload 必传（可含字段：description, visibility, category, note）。",
        examples=[
            {
                "arguments": {"asset_id": "asset-123", "payload": {"note": "站点 Logo", "visibility": "public"}},
                "scenario": "更新资源备注和可见性。",
            }
        ],
        domain="assets",
        group_label="资源",
        risk_level="medium",
    ),
    _tool(
        "delete_admin_asset",
        "Delete one admin asset permanently.",
        [ASSETS_WRITE],
        delete_admin_asset_item,
        intent="write",
        label="删除资源",
        label_en="Delete asset",
        help_text="永久删除单个后台资源文件。",
        help_text_en="Delete one admin asset permanently.",
        ai_usage_hint="删除单个资源。asset_id 必传。操作不可恢复。",
        examples=[{"arguments": {"asset_id": "asset-123"}, "scenario": "删除一个资源文件。"}],
        domain="assets",
        group_label="资源",
        risk_level="high",
    ),
    _tool(
        "bulk_delete_admin_assets",
        "Bulk-delete multiple admin assets permanently.",
        [ASSETS_WRITE],
        bulk_delete_admin_assets,
        intent="write",
        label="批量删除资源",
        label_en="Bulk delete assets",
        help_text="批量删除后台资源文件，不可恢复。",
        help_text_en="Bulk-delete multiple admin assets permanently.",
        ai_usage_hint="批量删除资源。ids 必传（ID 列表）。操作不可恢复。",
        examples=[{"arguments": {"ids": ["asset-1", "asset-2"]}, "scenario": "批量删除两个资源。"}],
        domain="assets",
        group_label="资源",
        risk_level="critical",
    ),
    # ═══════════════════════════════════════════════════════════════════════════
    # SOCIAL — 社交 / 友链
    # ═══════════════════════════════════════════════════════════════════════════
    _tool(
        "list_friend_feed_sources",
        "List RSS feed sources configured for a friend site.",
        [CONFIG_READ],
        _list_friend_feed_sources_tool,
        label="友链订阅源",
        label_en="Friend feeds",
        help_text="按 friend_id 读取友链站点配置的 RSS 订阅源列表。",
        help_text_en="List RSS feed sources configured for a friend site.",
        ai_usage_hint="获取指定友链的订阅源列表。friend_id 必传。",
        examples=[{"arguments": {"friend_id": "friend-123"}, "scenario": "查看某个友链的 RSS 源。"}],
        domain="social",
        group_label="社交",
    ),
    _tool(
        "create_friend_feed_source",
        "Add a new RSS feed source to a friend site.",
        [CONFIG_WRITE],
        create_friend_feed_source,
        intent="write",
        label="创建友链源",
        label_en="Create feed source",
        help_text="为友链站点添加一个新的 RSS 订阅源。",
        help_text_en="Add a new RSS feed source to a friend site.",
        ai_usage_hint="创建友链 RSS 源。friend_id 必传，payload 必传（含 url 等字段）。",
        examples=[
            {
                "arguments": {"friend_id": "friend-123", "payload": {"url": "https://example.com/feed.xml"}},
                "scenario": "为友链添加一个 RSS 源。",
            }
        ],
        domain="social",
        group_label="社交",
        risk_level="medium",
    ),
    _tool(
        "update_friend_feed_source",
        "Update an existing friend feed source.",
        [CONFIG_WRITE],
        update_friend_feed_source,
        intent="write",
        label="更新友链源",
        label_en="Update feed source",
        help_text="更新友链 RSS 订阅源配置。",
        help_text_en="Update an existing friend feed source.",
        ai_usage_hint="更新友链源。feed_id 必传，payload 必传。",
        examples=[
            {
                "arguments": {"feed_id": "feed-123", "payload": {"url": "https://example.com/rss.xml"}},
                "scenario": "修改友链源地址。",
            }
        ],
        domain="social",
        group_label="社交",
        risk_level="medium",
    ),
    _tool(
        "delete_friend_feed_source",
        "Delete one friend feed source.",
        [CONFIG_WRITE],
        delete_friend_feed_source,
        intent="write",
        label="删除友链源",
        label_en="Delete feed source",
        help_text="删除友链 RSS 订阅源。",
        help_text_en="Delete one friend feed source.",
        ai_usage_hint="删除友链源。feed_id 必传。",
        examples=[{"arguments": {"feed_id": "feed-123"}, "scenario": "删除一个友链 RSS 源。"}],
        domain="social",
        group_label="社交",
        risk_level="high",
    ),
    _tool(
        "trigger_feed_crawl",
        "Trigger a feed crawl. Omit feed_id to crawl all configured feeds.",
        [CONFIG_WRITE],
        trigger_feed_crawl,
        intent="action",
        label="触发友链抓取",
        label_en="Crawl feeds",
        help_text="立即触发一次友链源抓取任务。不传 feed_id 则抓取全部。",
        help_text_en="Trigger a feed crawl. Omit feed_id to crawl all feeds.",
        ai_usage_hint="触发友链抓取。feed_id 可选（不传则抓取所有源）。异步执行，返回任务状态。",
        examples=[{"arguments": {}, "scenario": "立即抓取所有友链源。"}],
        domain="social",
        group_label="社交",
        risk_level="medium",
        approval_policy="never",
    ),
    _tool(
        "check_friend_item",
        "Check a friend site's health and feed availability.",
        [CONFIG_WRITE],
        check_friend_item,
        intent="action",
        label="检查友链",
        label_en="Check friend",
        help_text="检查友链站点和订阅源是否可正常访问。",
        help_text_en="Check a friend site's health and feed availability.",
        ai_usage_hint="检查友链可用性。friend_id 必传。返回站点和订阅源的连通性状态。",
        examples=[{"arguments": {"friend_id": "friend-123"}, "scenario": "检查友链站点是否可达。"}],
        domain="social",
        group_label="社交",
        risk_level="medium",
        approval_policy="never",
    ),
    # ═══════════════════════════════════════════════════════════════════════════
    # SUBSCRIPTIONS — 订阅
    # ═══════════════════════════════════════════════════════════════════════════
    _tool(
        "get_subscription_config",
        "Get email subscription and SMTP configuration.",
        [SUBSCRIPTIONS_READ],
        get_subscription_config_state,
        label="订阅配置",
        label_en="Subscription config",
        help_text="获取内容订阅和 SMTP 发信配置（密码等敏感字段已脱敏）。",
        help_text_en="Get email subscription and SMTP config (credentials masked).",
        ai_usage_hint="获取订阅配置。不需要参数。敏感字段（SMTP 密码等）已脱敏。",
        examples=[{"arguments": {}, "scenario": "获取邮件订阅 SMTP 配置。"}],
        domain="subscriptions",
        group_label="订阅",
    ),
    _tool(
        "list_subscription_subscribers",
        "List email subscribers with pagination.",
        [SUBSCRIPTIONS_READ],
        list_subscription_subscribers,
        label="订阅者列表",
        label_en="List subscribers",
        help_text="列出邮件订阅者（邮箱已脱敏），支持分页。",
        help_text_en="List email subscribers with pagination (emails masked).",
        ai_usage_hint=(
            "获取订阅者列表。可选参数：mode(筛选模式,默认all), search(搜索关键词), "
            "page(页码,默认1), page_size(每页条数,默认20)。邮箱已脱敏显示。"
        ),
        examples=[{"arguments": {"page": 1, "page_size": 20}, "scenario": "查看订阅者列表首页。"}],
        domain="subscriptions",
        group_label="订阅",
    ),
    _tool(
        "list_subscription_delivery_history",
        "List subscription email delivery history with pagination.",
        [SUBSCRIPTIONS_READ],
        list_subscription_delivery_history,
        label="投递历史",
        label_en="Delivery history",
        help_text="按订阅者邮箱查看投递记录，支持分页。",
        help_text_en="List delivery history for a subscriber email with pagination.",
        ai_usage_hint="获取订阅投递记录。email 必传（订阅者邮箱），可选：page(页码,默认1), page_size(每页条数,默认20)。",
        examples=[{"arguments": {"email": "user@example.com", "page": 1}, "scenario": "查看某订阅者的投递记录。"}],
        domain="subscriptions",
        group_label="订阅",
    ),
    _tool(
        "update_subscription_config",
        "Update email subscription and SMTP configuration.",
        [SUBSCRIPTIONS_WRITE],
        update_subscription_config,
        intent="write",
        label="更新订阅配置",
        label_en="Update sub config",
        help_text="更新内容订阅和 SMTP 发信配置。",
        help_text_en="Update email subscription and SMTP configuration.",
        ai_usage_hint="更新订阅配置。传入 payload 字典，可选字段：smtp_host, smtp_port, smtp_user, smtp_password, from_email 等。",
        examples=[
            {
                "arguments": {"payload": {"smtp_host": "smtp.example.com", "smtp_port": 465}},
                "scenario": "更新 SMTP 发信服务器。",
            }
        ],
        domain="subscriptions",
        group_label="订阅",
        risk_level="high",
        approval_policy="always",
    ),
    _tool(
        "test_subscription_config",
        "Send a test email to verify SMTP configuration.",
        [SUBSCRIPTIONS_WRITE],
        test_subscription_config,
        intent="action",
        label="测试发信",
        label_en="Test SMTP",
        help_text="发送一封测试邮件以验证 SMTP 配置是否正确。",
        help_text_en="Send a test email to verify SMTP configuration.",
        ai_usage_hint="测试 SMTP 发信。payload 必传（含收件人等配置），persist_success 可选(默认false,为true时测试成功后保存配置)。",
        examples=[{"arguments": {"payload": {"to_email": "test@example.com"}}, "scenario": "发送一封 SMTP 测试邮件。"}],
        domain="subscriptions",
        group_label="订阅",
        risk_level="medium",
        approval_policy="never",
    ),
    _tool(
        "update_subscription_subscriber",
        "Enable or disable an email subscriber.",
        [SUBSCRIPTIONS_WRITE],
        update_subscription_subscriber,
        intent="write",
        label="更新订阅者",
        label_en="Update subscriber",
        help_text="启用或停用一个邮件订阅者。",
        help_text_en="Enable or disable an email subscriber.",
        ai_usage_hint="更新订阅者状态。email 必传（订阅者邮箱），is_active 必传 (true/false)。",
        examples=[{"arguments": {"email": "user@example.com", "is_active": False}, "scenario": "停用一个订阅者。"}],
        domain="subscriptions",
        group_label="订阅",
        risk_level="medium",
    ),
    _tool(
        "delete_subscription_subscriber",
        "Delete an email subscriber permanently.",
        [SUBSCRIPTIONS_WRITE],
        delete_subscription_subscriber,
        intent="write",
        label="删除订阅者",
        label_en="Delete subscriber",
        help_text="永久删除一个邮件订阅者。",
        help_text_en="Delete an email subscriber permanently.",
        ai_usage_hint="删除订阅者。email 必传（订阅者邮箱）。操作不可恢复。",
        examples=[{"arguments": {"email": "user@example.com"}, "scenario": "删除一个订阅者。"}],
        domain="subscriptions",
        group_label="订阅",
        risk_level="high",
    ),
    # ═══════════════════════════════════════════════════════════════════════════
    # VISITORS — 访客
    # ═══════════════════════════════════════════════════════════════════════════
    _tool(
        "get_visitor_auth_config",
        "Get visitor authentication and OAuth configuration.",
        [VISITORS_READ],
        get_visitor_auth_config_state,
        label="访客认证配置",
        label_en="Visitor auth config",
        help_text="获取访客认证和 OAuth 配置（密钥已脱敏）。",
        help_text_en="Get visitor authentication and OAuth config (secrets masked).",
        ai_usage_hint="获取访客认证配置。不需要参数。OAuth 密钥等敏感字段已脱敏。",
        examples=[{"arguments": {}, "scenario": "获取访客 OAuth 认证配置。"}],
        domain="visitors",
        group_label="访客",
    ),
    _tool(
        "list_visitor_users",
        "List registered visitor users with pagination.",
        [VISITORS_READ],
        list_visitor_users,
        label="访客用户列表",
        label_en="List visitors",
        help_text="列出已注册的访客用户（邮箱已脱敏），支持分页。",
        help_text_en="List registered visitor users with pagination (emails masked).",
        ai_usage_hint=(
            "获取访客用户列表。可选参数：mode(筛选模式,默认all), search(搜索关键词), "
            "page(页码,默认1), page_size(每页条数,默认20)。邮箱已脱敏。"
        ),
        examples=[{"arguments": {"page": 1, "page_size": 20}, "scenario": "查看访客用户列表首页。"}],
        domain="visitors",
        group_label="访客",
    ),
    _tool(
        "list_visitor_records",
        "List visitor access records with pagination.",
        [SYSTEM_READ],
        list_visitor_records_state,
        label="访客记录",
        label_en="Visit records",
        help_text="列出访客访问记录（IP 已脱敏），支持按路径、IP、日期筛选。",
        help_text_en="List visitor access records with filtering and pagination (IPs masked).",
        ai_usage_hint=(
            "获取访客访问记录。可选参数：page(页码,默认1), page_size(每页条数,默认20), "
            "path(页面路径筛选), ip(IP 筛选), date_from(开始日期), date_to(结束日期), "
            "include_bots(是否包含爬虫,默认false)。IP 地址已脱敏。"
        ),
        examples=[
            {
                "arguments": {"page": 1, "page_size": 20, "include_bots": False},
                "scenario": "查看访客访问记录（排除爬虫）。",
            }
        ],
        domain="visitors",
        group_label="访客",
    ),
    _tool(
        "list_admin_identity_bindings",
        "List admin identity bindings for front-end visitor accounts.",
        [VISITORS_READ],
        list_admin_identity_bindings,
        label="身份绑定列表",
        label_en="Identity bindings",
        help_text="列出管理员在前台的身份绑定记录。",
        help_text_en="List admin identity bindings for front-end visitor accounts.",
        ai_usage_hint="获取管理员身份绑定列表。不需要参数。",
        examples=[{"arguments": {}, "scenario": "获取管理员身份绑定列表。"}],
        domain="visitors",
        group_label="访客",
    ),
    _tool(
        "update_visitor_auth_config",
        "Update visitor authentication and OAuth configuration.",
        [VISITORS_WRITE],
        update_visitor_auth_config,
        intent="write",
        label="更新访客认证",
        label_en="Update visitor auth",
        help_text="更新访客认证和 OAuth 配置。",
        help_text_en="Update visitor authentication and OAuth configuration.",
        ai_usage_hint="更新访客认证配置。传入 payload 字典，字段因 OAuth 提供商而异。",
        examples=[{"arguments": {"payload": {"github_enabled": True}}, "scenario": "开启 GitHub OAuth 登录。"}],
        domain="visitors",
        group_label="访客",
        risk_level="high",
        approval_policy="always",
    ),
    _tool(
        "bind_admin_identity_email",
        "Bind an admin account to a front-end visitor identity by email.",
        [VISITORS_WRITE],
        bind_admin_identity_email,
        intent="write",
        label="绑定管理员身份",
        label_en="Bind admin identity",
        help_text="通过邮箱将管理员账号绑定到前台访客身份。",
        help_text_en="Bind an admin account to a front-end visitor identity by email.",
        ai_usage_hint="绑定管理员身份。admin_user_id 必传，email 必传。绑定后管理员在前台以该访客身份显示。",
        examples=[
            {
                "arguments": {"admin_user_id": "admin-1", "email": "admin@example.com"},
                "scenario": "将管理员绑定到前台邮箱身份。",
            }
        ],
        domain="visitors",
        group_label="访客",
        risk_level="medium",
    ),
    _tool(
        "delete_admin_identity_binding",
        "Delete an admin identity binding.",
        [VISITORS_WRITE],
        delete_admin_identity_binding,
        intent="write",
        label="解绑管理员身份",
        label_en="Unbind identity",
        help_text="删除管理员的前台身份绑定。",
        help_text_en="Delete an admin identity binding.",
        ai_usage_hint="解绑管理员身份。identity_id 必传。",
        examples=[{"arguments": {"identity_id": "identity-123"}, "scenario": "解除一个管理员身份绑定。"}],
        domain="visitors",
        group_label="访客",
        risk_level="high",
    ),
    # ═══════════════════════════════════════════════════════════════════════════
    # AUTH — 认证
    # ═══════════════════════════════════════════════════════════════════════════
    _tool(
        "get_admin_login_options",
        "Get supported admin login methods.",
        [AUTH_READ],
        get_admin_login_options_state,
        label="登录方式",
        label_en="Login options",
        help_text="获取管理员可用的登录方式列表。",
        help_text_en="Get supported admin login methods.",
        ai_usage_hint="获取登录方式。不需要参数。",
        examples=[{"arguments": {}, "scenario": "查看可用的管理员登录方式。"}],
        domain="auth",
        group_label="认证",
    ),
    _tool(
        "get_admin_me",
        "Get the current admin user's profile and permissions.",
        [AUTH_READ],
        get_admin_me,
        label="当前管理员",
        label_en="Current admin",
        help_text="获取当前登录管理员的个人信息和权限。",
        help_text_en="Get the current admin user's profile and permissions.",
        ai_usage_hint="获取管理员信息。可选参数：admin_user_id(不传则返回当前管理员)。返回管理员名、角色和权限列表。",
        examples=[{"arguments": {}, "scenario": "获取当前管理员信息。"}],
        domain="auth",
        group_label="认证",
    ),
    _tool(
        "list_admin_sessions",
        "List active admin sessions with pagination.",
        [AUTH_READ],
        list_admin_sessions,
        label="会话列表",
        label_en="Admin sessions",
        help_text="列出活跃的管理员会话，支持分页。",
        help_text_en="List active admin sessions with pagination.",
        ai_usage_hint="获取管理员会话列表。可选参数：admin_user_id(按管理员筛选), page(页码,默认1), page_size(每页条数,默认100)。",
        examples=[{"arguments": {"page": 1}, "scenario": "列出当前活跃的管理员会话。"}],
        domain="auth",
        group_label="认证",
    ),
    _tool(
        "update_admin_profile_item",
        "Update the current admin user's profile.",
        [AUTH_WRITE],
        update_admin_profile_item,
        intent="write",
        label="更新管理员资料",
        label_en="Update admin profile",
        help_text="更新当前管理员的个人资料。",
        help_text_en="Update the current admin user's profile.",
        ai_usage_hint="更新管理员资料。admin_user_id 必传，username 可选（新用户名）。",
        examples=[
            {"arguments": {"admin_user_id": "admin-1", "username": "新用户名"}, "scenario": "修改管理员用户名。"}
        ],
        domain="auth",
        group_label="认证",
        risk_level="medium",
    ),
    _tool(
        "revoke_admin_session_item",
        "Revoke (terminate) an admin session.",
        [AUTH_WRITE],
        revoke_admin_session_item,
        intent="action",
        label="撤销会话",
        label_en="Revoke session",
        help_text="强制终止一个管理员会话。",
        help_text_en="Revoke (terminate) an admin session.",
        ai_usage_hint="撤销管理员会话。admin_user_id 必传，session_id 必传。被撤销的会话将立即失效。",
        examples=[
            {
                "arguments": {"admin_user_id": "admin-1", "session_id": "sess-123"},
                "scenario": "强制下线一个管理员会话。",
            }
        ],
        domain="auth",
        group_label="认证",
        risk_level="medium",
    ),
    _tool(
        "list_admin_api_keys",
        "List admin API keys (raw key values are never exposed).",
        [SYSTEM_READ],
        list_admin_api_keys_state,
        label="API Key 列表",
        label_en="List API keys",
        help_text="列出管理员 API Key 元信息（不暴露密钥原文）。",
        help_text_en="List admin API keys. Raw key values are never exposed.",
        ai_usage_hint="获取 API Key 列表。不需要参数。只返回元信息（名称、创建时间、过期时间），不返回密钥原文。",
        examples=[{"arguments": {}, "scenario": "查看已创建的 API Key 列表。"}],
        domain="auth",
        group_label="认证",
    ),
    _tool(
        "create_admin_api_key",
        "Create a new admin API key. The raw key is only returned once.",
        [SYSTEM_WRITE],
        create_admin_api_key,
        intent="write",
        label="创建 API Key",
        label_en="Create API key",
        help_text="创建管理员 API Key，密钥原文仅在创建时返回一次。",
        help_text_en="Create a new admin API key. The raw key is only returned once.",
        ai_usage_hint="创建 API Key。key_name 必传（Key 名称），scopes 必传（权限范围列表）。密钥原文仅在创建响应中返回一次。",
        examples=[
            {
                "arguments": {"key_name": "MCP 集成", "scopes": ["content:read", "content:write"]},
                "scenario": "创建一个用于 MCP 的 API Key。",
            }
        ],
        domain="auth",
        group_label="认证",
        risk_level="critical",
        approval_policy="always",
    ),
    _tool(
        "update_admin_api_key",
        "Update an admin API key's name or expiration.",
        [SYSTEM_WRITE],
        update_admin_api_key,
        intent="write",
        label="更新 API Key",
        label_en="Update API key",
        help_text="更新 API Key 名称或过期时间。",
        help_text_en="Update an admin API key's name or expiration.",
        ai_usage_hint="更新 API Key。key_id 必传，payload 必传（可含字段：key_name, scopes, is_active 等）。",
        examples=[
            {"arguments": {"key_id": "key-123", "payload": {"key_name": "新名称"}}, "scenario": "重命名一个 API Key。"}
        ],
        domain="auth",
        group_label="认证",
        risk_level="high",
        approval_policy="always",
    ),
    _tool(
        "delete_admin_api_key",
        "Delete an admin API key permanently.",
        [SYSTEM_WRITE],
        delete_admin_api_key,
        intent="write",
        label="删除 API Key",
        label_en="Delete API key",
        help_text="永久删除管理员 API Key。",
        help_text_en="Delete an admin API key permanently.",
        ai_usage_hint="删除 API Key。key_id 必传。操作不可恢复，使用该 Key 的集成将立即失效。",
        examples=[{"arguments": {"key_id": "key-123"}, "scenario": "删除一个 API Key。"}],
        domain="auth",
        group_label="认证",
        risk_level="critical",
        approval_policy="always",
    ),
    # ═══════════════════════════════════════════════════════════════════════════
    # NETWORK — 网络
    # ═══════════════════════════════════════════════════════════════════════════
    _tool(
        "get_outbound_proxy_config",
        "Get outbound HTTP/HTTPS proxy configuration.",
        [NETWORK_READ],
        get_outbound_proxy_config_state,
        label="出站代理配置",
        label_en="Proxy config",
        help_text="获取出站 HTTP/HTTPS 代理配置。",
        help_text_en="Get outbound HTTP/HTTPS proxy configuration.",
        ai_usage_hint="获取出站代理配置。不需要参数。",
        examples=[{"arguments": {}, "scenario": "查看出站代理配置。"}],
        domain="network",
        group_label="网络",
    ),
    _tool(
        "update_proxy_config_item",
        "Update outbound HTTP/HTTPS proxy configuration.",
        [NETWORK_WRITE],
        update_proxy_config_item,
        intent="write",
        label="更新代理配置",
        label_en="Update proxy",
        help_text="更新出站 HTTP/HTTPS 代理配置。",
        help_text_en="Update outbound HTTP/HTTPS proxy configuration.",
        ai_usage_hint="更新代理配置。传入 payload 字典，字段：proxy_url(代理地址), enabled(是否启用)等。",
        examples=[
            {
                "arguments": {"payload": {"proxy_url": "http://proxy:8080", "enabled": True}},
                "scenario": "配置出站代理。",
            }
        ],
        domain="network",
        group_label="网络",
        risk_level="high",
        approval_policy="always",
    ),
    _tool(
        "test_proxy_config_item",
        "Test outbound proxy connectivity.",
        [NETWORK_WRITE],
        test_proxy_config_item,
        intent="action",
        label="测试代理",
        label_en="Test proxy",
        help_text="测试出站代理是否能正常连通。",
        help_text_en="Test outbound proxy connectivity.",
        ai_usage_hint="测试出站代理连通性。payload 必传（代理配置字典）。",
        examples=[{"arguments": {"payload": {"proxy_url": "http://proxy:8080"}}, "scenario": "测试代理是否可连通。"}],
        domain="network",
        group_label="网络",
        risk_level="medium",
        approval_policy="never",
    ),
    # ═══════════════════════════════════════════════════════════════════════════
    # SYSTEM — 系统
    # ═══════════════════════════════════════════════════════════════════════════
    _tool(
        "get_system_info",
        "Get system information summary (version, uptime, resource usage).",
        [SYSTEM_READ],
        get_system_info_state,
        label="系统信息",
        label_en="System info",
        help_text="获取系统信息摘要，包含版本、运行时间、资源使用情况。",
        help_text_en="Get system info summary (version, uptime, resource usage).",
        ai_usage_hint="获取系统信息。不需要参数。返回版本号、运行时长、内存和磁盘使用等。",
        examples=[{"arguments": {}, "scenario": "查看系统版本和运行状态。"}],
        domain="system",
        group_label="系统",
    ),
    _tool(
        "get_dashboard_stats",
        "Get dashboard statistics (content counts, recent activity).",
        [SYSTEM_READ],
        get_dashboard_stats_state,
        label="仪表盘统计",
        label_en="Dashboard stats",
        help_text="获取仪表盘统计数据，包含各类内容计数和近期活动。",
        help_text_en="Get dashboard statistics (content counts, recent activity).",
        ai_usage_hint="获取仪表盘统计。不需要参数。返回文章/日记/想法/摘录数量、最近发布等。",
        examples=[{"arguments": {}, "scenario": "获取仪表盘各项统计数据。"}],
        domain="system",
        group_label="系统",
    ),
    _tool(
        "list_audit_logs",
        "List audit logs with filtering and pagination.",
        [SYSTEM_READ],
        list_audit_logs_state,
        label="审计日志",
        label_en="Audit logs",
        help_text="查看系统审计日志，支持按操作类型、时间范围筛选。",
        help_text_en="List audit logs with filtering and pagination.",
        ai_usage_hint=(
            "获取审计日志。可选参数：page(页码,默认1), page_size(每页条数,默认20), "
            "action(操作类型筛选), actor_id(操作者筛选), date_from(开始日期), date_to(结束日期)。"
        ),
        examples=[
            {
                "arguments": {"page": 1, "page_size": 20, "action": "content.create"},
                "scenario": "查看内容创建相关的审计日志。",
            }
        ],
        domain="system",
        group_label="系统",
    ),
    _tool(
        "list_config_revisions",
        "List configuration change history with pagination.",
        [SYSTEM_READ],
        list_config_revisions_state,
        label="配置历史",
        label_en="Config revisions",
        help_text="查看配置变更历史记录，支持按资源类型、操作者、日期范围筛选。",
        help_text_en="List configuration change history with filtering and pagination.",
        ai_usage_hint=(
            "获取配置变更历史。可选参数：page(页码,默认1), page_size(每页条数,默认20), "
            "resource_key(资源类型筛选), actor_id(操作者筛选), date_from(开始日期), date_to(结束日期)。"
        ),
        examples=[{"arguments": {"page": 1, "page_size": 10}, "scenario": "查看最近的配置变更记录。"}],
        domain="system",
        group_label="系统",
    ),
    _tool(
        "get_config_revision_detail",
        "Get detailed diff for one configuration revision.",
        [SYSTEM_READ],
        get_config_revision_detail_state,
        label="配置变更详情",
        label_en="Config revision detail",
        help_text="查看某次配置变更的详细 diff。",
        help_text_en="Get detailed diff for one configuration revision.",
        ai_usage_hint="获取配置变更详情。revision_id 必传。返回变更前后的 diff。",
        examples=[{"arguments": {"revision_id": "rev-123"}, "scenario": "查看某次配置变更的 diff。"}],
        domain="system",
        group_label="系统",
    ),
    _tool(
        "restore_config_revision_item",
        "Restore site configuration to a previous revision.",
        [SYSTEM_WRITE],
        restore_config_revision_item,
        intent="action",
        label="恢复配置版本",
        label_en="Restore config",
        help_text="将站点配置回滚到指定的历史版本。",
        help_text_en="Restore site configuration to a previous revision.",
        ai_usage_hint="恢复配置到历史版本。revision_id 必传，payload 必传（恢复选项），actor_id 可选。操作会覆盖当前配置。",
        examples=[{"arguments": {"revision_id": "rev-123", "payload": {}}, "scenario": "将配置回滚到某个历史版本。"}],
        domain="system",
        group_label="系统",
        risk_level="critical",
        approval_policy="always",
    ),
    # ═══════════════════════════════════════════════════════════════════════════
    # BACKUP — 备份
    # ═══════════════════════════════════════════════════════════════════════════
    _tool(
        "get_backup_sync_config",
        "Get backup sync configuration (Git remote, schedule, etc.).",
        [SYSTEM_READ],
        get_backup_sync_config_state,
        label="备份同步配置",
        label_en="Backup config",
        help_text="获取备份同步配置，包含 Git 远程仓库、同步计划等。",
        help_text_en="Get backup sync configuration (Git remote, schedule, etc.).",
        ai_usage_hint="获取备份同步配置。不需要参数。",
        examples=[{"arguments": {}, "scenario": "查看备份同步配置。"}],
        domain="backup",
        group_label="备份",
    ),
    _tool(
        "list_backup_sync_queue",
        "List pending items in the backup sync queue.",
        [SYSTEM_READ],
        list_backup_sync_queue_state,
        label="备份队列",
        label_en="Backup queue",
        help_text="查看待同步的备份队列。",
        help_text_en="List pending items in the backup sync queue.",
        ai_usage_hint="获取备份同步队列。不需要参数。",
        examples=[{"arguments": {}, "scenario": "查看待同步的备份队列。"}],
        domain="backup",
        group_label="备份",
    ),
    _tool(
        "list_backup_sync_runs",
        "List backup sync execution history.",
        [SYSTEM_READ],
        list_backup_sync_runs_state,
        label="备份运行记录",
        label_en="Backup runs",
        help_text="查看备份同步执行记录。",
        help_text_en="List backup sync execution history.",
        ai_usage_hint="获取备份同步运行记录。不需要参数。",
        examples=[{"arguments": {}, "scenario": "查看备份同步运行记录。"}],
        domain="backup",
        group_label="备份",
    ),
    _tool(
        "list_backup_sync_commits",
        "List backup sync Git commits.",
        [SYSTEM_READ],
        list_backup_sync_commits_state,
        label="备份提交记录",
        label_en="Backup commits",
        help_text="查看备份同步的 Git 提交记录。",
        help_text_en="List backup sync Git commits.",
        ai_usage_hint="获取备份 Git 提交列表。不需要参数。",
        examples=[{"arguments": {}, "scenario": "查看备份仓库提交记录。"}],
        domain="backup",
        group_label="备份",
    ),
    _tool(
        "list_backup_snapshots",
        "List available backup snapshots.",
        [SYSTEM_READ],
        list_backup_snapshots_state,
        label="备份快照",
        label_en="Backup snapshots",
        help_text="列出可用的备份快照。",
        help_text_en="List available backup snapshots.",
        ai_usage_hint="获取备份快照列表。不需要参数。",
        examples=[{"arguments": {}, "scenario": "查看可用的备份快照。"}],
        domain="backup",
        group_label="备份",
    ),
    _tool(
        "create_backup_snapshot_item",
        "Create a backup snapshot of the current state.",
        [SYSTEM_WRITE],
        create_backup_snapshot_item,
        intent="action",
        label="创建快照",
        label_en="Create snapshot",
        help_text="创建当前状态的备份快照。",
        help_text_en="Create a backup snapshot of the current state.",
        ai_usage_hint="创建备份快照。不需要参数。",
        examples=[{"arguments": {}, "scenario": "创建当前状态的备份快照。"}],
        domain="backup",
        group_label="备份",
        risk_level="high",
        approval_policy="always",
    ),
    _tool(
        "restore_backup_snapshot_item",
        "Restore the system from a backup snapshot.",
        [SYSTEM_WRITE],
        restore_backup_snapshot_item,
        intent="action",
        label="恢复快照",
        label_en="Restore snapshot",
        help_text="从备份快照恢复系统状态。操作会覆盖当前数据。",
        help_text_en="Restore the system from a backup snapshot. Overwrites current data.",
        ai_usage_hint="从快照恢复。snapshot_id 必传。操作会覆盖当前数据，建议先创建新快照备份当前状态。",
        examples=[{"arguments": {"snapshot_id": "snap-123"}, "scenario": "从快照恢复系统状态。"}],
        domain="backup",
        group_label="备份",
        risk_level="critical",
        approval_policy="always",
    ),
    _tool(
        "update_backup_sync_config_item",
        "Update backup sync configuration (Git remote, schedule, etc.).",
        [SYSTEM_WRITE],
        update_backup_sync_config_item,
        intent="write",
        label="更新备份配置",
        label_en="Update backup config",
        help_text="更新备份同步配置。",
        help_text_en="Update backup sync configuration.",
        ai_usage_hint="更新备份同步配置。传入 payload 字典，字段：git_remote, schedule, enabled 等。",
        examples=[{"arguments": {"payload": {"enabled": True}}, "scenario": "启用自动备份同步。"}],
        domain="backup",
        group_label="备份",
        risk_level="high",
        approval_policy="always",
    ),
    _tool(
        "trigger_backup_sync_item",
        "Trigger an immediate backup sync.",
        [SYSTEM_WRITE],
        trigger_backup_sync_item,
        intent="action",
        label="触发备份同步",
        label_en="Trigger sync",
        help_text="立即触发一次备份同步。",
        help_text_en="Trigger an immediate backup sync.",
        ai_usage_hint="立即触发备份同步。不需要参数。异步执行。",
        examples=[{"arguments": {}, "scenario": "立即触发一次备份同步。"}],
        domain="backup",
        group_label="备份",
        risk_level="medium",
        approval_policy="never",
    ),
    _tool(
        "retry_backup_sync_run_item",
        "Retry a failed backup sync run.",
        [SYSTEM_WRITE],
        retry_backup_sync_run_item,
        intent="action",
        label="重试备份同步",
        label_en="Retry sync run",
        help_text="重试一次失败的备份同步。",
        help_text_en="Retry a failed backup sync run.",
        ai_usage_hint="重试备份同步。run_id 必传。",
        examples=[{"arguments": {"run_id": "run-123"}, "scenario": "重试一次失败的备份同步。"}],
        domain="backup",
        group_label="备份",
        risk_level="medium",
        approval_policy="never",
    ),
    _tool(
        "pause_backup_sync_item",
        "Pause automatic backup sync.",
        [SYSTEM_WRITE],
        pause_backup_sync_item,
        intent="action",
        label="暂停备份同步",
        label_en="Pause sync",
        help_text="暂停自动备份同步。",
        help_text_en="Pause automatic backup sync.",
        ai_usage_hint="暂停备份同步。不需要参数。",
        examples=[{"arguments": {}, "scenario": "暂停自动备份同步。"}],
        domain="backup",
        group_label="备份",
        risk_level="high",
        approval_policy="always",
    ),
    _tool(
        "resume_backup_sync_item",
        "Resume automatic backup sync.",
        [SYSTEM_WRITE],
        resume_backup_sync_item,
        intent="action",
        label="恢复备份同步",
        label_en="Resume sync",
        help_text="恢复已暂停的自动备份同步。",
        help_text_en="Resume automatic backup sync.",
        ai_usage_hint="恢复备份同步。不需要参数。",
        examples=[{"arguments": {}, "scenario": "恢复自动备份同步。"}],
        domain="backup",
        group_label="备份",
        risk_level="high",
        approval_policy="always",
    ),
    _tool(
        "restore_backup_commit_item",
        "Restore the system from a specific backup Git commit.",
        [SYSTEM_WRITE],
        restore_backup_commit_item,
        intent="action",
        label="恢复备份提交",
        label_en="Restore commit",
        help_text="从备份仓库的某个 Git 提交恢复系统状态。操作会覆盖当前数据。",
        help_text_en="Restore from a backup Git commit. Overwrites current data.",
        ai_usage_hint="从 Git 提交恢复。commit_id 必传。操作覆盖当前数据，建议先备份。",
        examples=[{"arguments": {"commit_id": "abc1234"}, "scenario": "从备份仓库的某个提交恢复。"}],
        domain="backup",
        group_label="备份",
        risk_level="critical",
        approval_policy="always",
    ),
    _tool(
        "test_backup_sync_config",
        "Test backup sync configuration connectivity.",
        [SYSTEM_WRITE],
        test_backup_sync_config,
        intent="action",
        label="测试备份配置",
        label_en="Test backup config",
        help_text="测试备份同步配置的连通性（Git 远程是否可达）。",
        help_text_en="Test backup sync config connectivity.",
        ai_usage_hint="测试备份配置连通性。payload 必传（备份同步配置字典，或用当前已保存的配置）。",
        examples=[{"arguments": {"payload": {}}, "scenario": "测试备份同步配置的连通性。"}],
        domain="backup",
        group_label="备份",
        risk_level="medium",
        approval_policy="never",
    ),
    # ═══════════════════════════════════════════════════════════════════════════
    # AUTOMATION — 自动化
    # ═══════════════════════════════════════════════════════════════════════════
    _tool(
        "get_agent_model_config",
        "Get AI agent model configuration (provider, model, parameters).",
        [AUTOMATION_READ],
        get_agent_model_config_state,
        label="模型配置",
        label_en="Model config",
        help_text="获取 AI 代理的模型配置，包含提供商、模型名、参数等。",
        help_text_en="Get AI agent model configuration (provider, model, parameters).",
        ai_usage_hint="获取 AI 模型配置。不需要参数。",
        examples=[{"arguments": {}, "scenario": "查看 AI 模型配置。"}],
        domain="automation",
        group_label="自动化",
    ),
    _tool(
        "update_agent_model_config_item",
        "Update AI agent model configuration.",
        [AUTOMATION_WRITE],
        update_agent_model_config_item,
        intent="write",
        label="更新模型配置",
        label_en="Update model config",
        help_text="更新 AI 代理的模型配置。",
        help_text_en="Update AI agent model configuration.",
        ai_usage_hint="更新模型配置。传入 payload 字典，字段：provider, model, temperature, max_tokens 等。",
        examples=[
            {"arguments": {"payload": {"provider": "openai", "model": "gpt-4o"}}, "scenario": "切换 AI 模型到 GPT-4o。"}
        ],
        domain="automation",
        group_label="自动化",
        risk_level="high",
        approval_policy="always",
    ),
    _tool(
        "test_agent_model_config",
        "Test AI model configuration connectivity and availability.",
        [AUTOMATION_WRITE],
        test_agent_model_config,
        intent="action",
        label="测试模型配置",
        label_en="Test model config",
        help_text="测试 AI 模型配置是否可连通。",
        help_text_en="Test AI model config connectivity and availability.",
        ai_usage_hint="测试 AI 模型连通性。payload 必传（模型配置字典，或用当前已保存的配置）。",
        examples=[
            {
                "arguments": {"payload": {"provider": "openai", "model": "gpt-4o"}},
                "scenario": "测试模型配置是否可连通。",
            }
        ],
        domain="automation",
        group_label="自动化",
        risk_level="medium",
        approval_policy="never",
    ),
    _tool(
        "list_agent_workflows",
        "List configured agent workflows.",
        [AUTOMATION_READ],
        list_agent_workflows_state,
        label="工作流列表",
        label_en="List workflows",
        help_text="列出已配置的代理工作流。",
        help_text_en="List configured agent workflows.",
        ai_usage_hint="获取工作流列表。不需要参数。",
        examples=[{"arguments": {}, "scenario": "查看已配置的工作流列表。"}],
        domain="automation",
        group_label="自动化",
    ),
    _tool(
        "get_agent_workflow_catalog",
        "Get the workflow template catalog with available node types.",
        [AUTOMATION_READ],
        get_agent_workflow_catalog_state,
        label="工作流模板目录",
        label_en="Workflow catalog",
        help_text="获取工作流模板目录，包含可用的节点类型和配置选项。",
        help_text_en="Get workflow template catalog with available node types.",
        ai_usage_hint="获取工作流模板目录。可选参数：workflow_key(指定工作流时返回其可用节点)。返回可用节点类型、触发器类型等。",
        examples=[{"arguments": {}, "scenario": "获取工作流模板和可用节点类型。"}],
        domain="automation",
        group_label="自动化",
    ),
    _tool(
        "create_agent_workflow_item",
        "Create a new agent workflow definition.",
        [AUTOMATION_WRITE],
        create_agent_workflow_item,
        intent="write",
        label="创建工作流",
        label_en="Create workflow",
        help_text="创建新的代理工作流定义。",
        help_text_en="Create a new agent workflow definition.",
        ai_usage_hint="创建工作流。payload 必传，含 name(名称), nodes(节点列表), edges(边列表) 等。",
        examples=[
            {
                "arguments": {"payload": {"name": "内容审核流", "nodes": [], "edges": []}},
                "scenario": "创建一个新的工作流。",
            }
        ],
        domain="automation",
        group_label="自动化",
        risk_level="high",
        approval_policy="always",
    ),
    _tool(
        "update_agent_workflow_item",
        "Update an existing agent workflow definition.",
        [AUTOMATION_WRITE],
        update_agent_workflow_item,
        intent="write",
        label="更新工作流",
        label_en="Update workflow",
        help_text="更新已有的代理工作流定义。",
        help_text_en="Update an existing agent workflow definition.",
        ai_usage_hint="更新工作流。workflow_key 必传，payload 必传（含修改后的工作流定义）。",
        examples=[
            {
                "arguments": {"workflow_key": "content-review", "payload": {"name": "内容审核流 v2"}},
                "scenario": "更新工作流名称。",
            }
        ],
        domain="automation",
        group_label="自动化",
        risk_level="high",
        approval_policy="always",
    ),
    _tool(
        "delete_agent_workflow_item",
        "Delete an agent workflow definition permanently.",
        [AUTOMATION_WRITE],
        delete_agent_workflow_item,
        intent="write",
        label="删除工作流",
        label_en="Delete workflow",
        help_text="永久删除代理工作流定义。",
        help_text_en="Delete an agent workflow definition permanently.",
        ai_usage_hint="删除工作流。workflow_key 必传。操作不可恢复。",
        examples=[{"arguments": {"workflow_key": "content-review"}, "scenario": "删除一个工作流。"}],
        domain="automation",
        group_label="自动化",
        risk_level="critical",
        approval_policy="always",
    ),
    _tool(
        "validate_agent_workflow",
        "Validate a workflow definition without saving.",
        [AUTOMATION_READ],
        validate_agent_workflow,
        intent="action",
        label="校验工作流",
        label_en="Validate workflow",
        help_text="校验工作流定义是否合法，不会保存。",
        help_text_en="Validate a workflow definition without saving.",
        ai_usage_hint="校验工作流定义。payload 必传（工作流定义 JSON）。只做校验不保存，返回校验结果。",
        examples=[
            {
                "arguments": {"payload": {"name": "测试流", "nodes": [], "edges": []}},
                "scenario": "校验工作流定义是否合法。",
            }
        ],
        domain="automation",
        group_label="自动化",
        risk_level="medium",
        approval_policy="never",
    ),
    _tool(
        "trigger_workflow_run",
        "Trigger a workflow execution.",
        [AUTOMATION_WRITE],
        trigger_workflow_run,
        intent="action",
        label="触发工作流",
        label_en="Trigger workflow",
        help_text="触发一次工作流执行。",
        help_text_en="Trigger a workflow execution.",
        ai_usage_hint="触发工作流执行。workflow_key 必传，payload 必传（运行参数，含 inputs 等）。",
        examples=[
            {
                "arguments": {"workflow_key": "content-review", "payload": {"inputs": {"target_id": "post-123"}}},
                "scenario": "触发内容审核工作流。",
            }
        ],
        domain="automation",
        group_label="自动化",
        risk_level="high",
        approval_policy="risk_based",
    ),
    _tool(
        "test_workflow_run",
        "Test-run a workflow in dry-run mode.",
        [AUTOMATION_WRITE],
        test_workflow_run,
        intent="action",
        label="测试工作流",
        label_en="Test workflow",
        help_text="以测试模式运行工作流（不产生实际副作用）。",
        help_text_en="Test-run a workflow in dry-run mode.",
        ai_usage_hint="测试运行工作流。workflow_key 必传，payload 必传（运行参数）。不会产生实际副作用。",
        examples=[
            {
                "arguments": {"workflow_key": "content-review", "payload": {"inputs": {}}},
                "scenario": "测试运行工作流（不产生副作用）。",
            }
        ],
        domain="automation",
        group_label="自动化",
        risk_level="medium",
        approval_policy="never",
    ),
    _tool(
        "list_agent_runs",
        "List agent workflow execution records with pagination.",
        [AUTOMATION_READ],
        list_agent_runs_state,
        label="运行记录",
        label_en="List runs",
        help_text="列出代理工作流的执行记录。",
        help_text_en="List agent workflow execution records.",
        ai_usage_hint="获取工作流运行记录。不需要参数。",
        examples=[{"arguments": {}, "scenario": "查看工作流运行记录。"}],
        domain="automation",
        group_label="自动化",
    ),
    _tool(
        "get_agent_run_detail",
        "Get detailed info for one workflow run including steps.",
        [AUTOMATION_READ],
        get_agent_run_detail_state,
        label="运行详情",
        label_en="Run detail",
        help_text="获取单次工作流运行的详细信息，包含各步骤执行情况。",
        help_text_en="Get detailed info for one workflow run including steps.",
        ai_usage_hint="获取运行详情。run_id 必传。返回运行状态、各步骤输入输出和耗时。",
        examples=[{"arguments": {"run_id": "run-123"}, "scenario": "查看某次运行的详细步骤。"}],
        domain="automation",
        group_label="自动化",
    ),
    _tool(
        "list_pending_approvals",
        "List workflow actions pending human approval.",
        [AUTOMATION_READ],
        list_pending_approvals_state,
        label="待审批列表",
        label_en="Pending approvals",
        help_text="列出等待人工审批的工作流动作。",
        help_text_en="List workflow actions pending human approval.",
        ai_usage_hint="获取待审批列表。不需要参数。",
        examples=[{"arguments": {}, "scenario": "查看等待审批的工作流动作。"}],
        domain="automation",
        group_label="自动化",
    ),
    _tool(
        "resolve_workflow_approval_item",
        "Approve or reject a pending workflow approval.",
        [AUTOMATION_WRITE],
        resolve_workflow_approval_item,
        intent="action",
        label="处理审批",
        label_en="Resolve approval",
        help_text="批准或拒绝一个待处理的工作流审批。",
        help_text_en="Approve or reject a pending workflow approval.",
        ai_usage_hint="处理审批。approval_id 必传，actor_id 必传，payload 必传（含 action: approve/reject，可选 reason）。",
        examples=[
            {
                "arguments": {
                    "approval_id": "appr-123",
                    "actor_id": "admin-1",
                    "payload": {"action": "approve", "reason": "内容符合规范"},
                },
                "scenario": "批准一个待审批动作。",
            }
        ],
        domain="automation",
        group_label="自动化",
        risk_level="high",
        approval_policy="always",
    ),
    _tool(
        "update_mcp_admin_config_item",
        "Update MCP server configuration.",
        [AUTOMATION_WRITE],
        update_mcp_admin_config_item,
        intent="write",
        label="更新 MCP 配置",
        label_en="Update MCP config",
        help_text="更新 MCP 服务器配置。",
        help_text_en="Update MCP server configuration.",
        ai_usage_hint="更新 MCP 配置。payload 必传（配置字典），api_key_id 可选（关联的 API Key）。",
        examples=[{"arguments": {"payload": {"enabled": True}}, "scenario": "更新 MCP 配置。"}],
        domain="automation",
        group_label="自动化",
        risk_level="high",
        approval_policy="always",
    ),
    _tool(
        "list_webhook_subscriptions",
        "List configured webhook subscriptions.",
        [AUTOMATION_READ],
        list_webhook_subscriptions_state,
        label="Webhook 列表",
        label_en="List webhooks",
        help_text="列出已配置的 Webhook 订阅。",
        help_text_en="List configured webhook subscriptions.",
        ai_usage_hint="获取 Webhook 订阅列表。不需要参数。",
        examples=[{"arguments": {}, "scenario": "查看 Webhook 订阅列表。"}],
        domain="automation",
        group_label="自动化",
    ),
    _tool(
        "list_webhook_deliveries",
        "List recent webhook delivery attempts.",
        [AUTOMATION_READ],
        list_webhook_deliveries_state,
        label="Webhook 投递记录",
        label_en="Webhook deliveries",
        help_text="查看 Webhook 的投递尝试记录。",
        help_text_en="List recent webhook delivery attempts.",
        ai_usage_hint="获取 Webhook 投递记录。不需要参数。",
        examples=[{"arguments": {}, "scenario": "查看 Webhook 投递记录。"}],
        domain="automation",
        group_label="自动化",
    ),
    _tool(
        "list_webhook_dead_letters",
        "List webhook dead letters (permanently failed deliveries).",
        [AUTOMATION_READ],
        list_webhook_dead_letters_state,
        label="Webhook 死信",
        label_en="Dead letters",
        help_text="查看投递永久失败的 Webhook 死信。",
        help_text_en="List webhook dead letters (permanently failed deliveries).",
        ai_usage_hint="获取 Webhook 死信列表。不需要参数。",
        examples=[{"arguments": {}, "scenario": "查看 Webhook 死信列表。"}],
        domain="automation",
        group_label="自动化",
    ),
    _tool(
        "create_webhook_subscription_item",
        "Create a new webhook subscription.",
        [AUTOMATION_WRITE],
        create_webhook_subscription_item,
        intent="write",
        label="创建 Webhook",
        label_en="Create webhook",
        help_text="创建新的 Webhook 订阅。",
        help_text_en="Create a new webhook subscription.",
        ai_usage_hint="创建 Webhook 订阅。payload 必传，含 url(目标地址), events(监听事件列表), secret(可选签名密钥)。",
        examples=[
            {
                "arguments": {
                    "payload": {
                        "url": "https://example.com/webhook",
                        "events": ["content.published"],
                        "secret": "my-secret",
                    }
                },
                "scenario": "创建一个内容发布 Webhook。",
            }
        ],
        domain="automation",
        group_label="自动化",
        risk_level="medium",
    ),
    _tool(
        "test_webhook_subscription_item",
        "Send a test payload to a webhook endpoint.",
        [AUTOMATION_WRITE],
        test_webhook_subscription_item,
        intent="action",
        label="测试 Webhook",
        label_en="Test webhook",
        help_text="向 Webhook 端点发送测试载荷以验证连通性。",
        help_text_en="Send a test payload to a webhook endpoint.",
        ai_usage_hint="测试 Webhook。payload 必传（测试载荷），subscription_id 可选（指定要测试的订阅）。",
        examples=[
            {
                "arguments": {"payload": {"url": "https://example.com/webhook"}, "subscription_id": "sub-123"},
                "scenario": "向指定 Webhook 发送测试载荷。",
            }
        ],
        domain="automation",
        group_label="自动化",
        risk_level="medium",
        approval_policy="never",
    ),
    _tool(
        "connect_telegram_webhook_item",
        "Connect a Telegram bot webhook for notifications.",
        [AUTOMATION_WRITE],
        connect_telegram_webhook_item,
        intent="action",
        label="连接 Telegram",
        label_en="Connect Telegram",
        help_text="连接 Telegram Bot Webhook 用于接收通知。",
        help_text_en="Connect a Telegram bot webhook for notifications.",
        ai_usage_hint="连接 Telegram Webhook。bot_token 必传（Telegram Bot Token），send_test_message 可选(默认true,发送测试消息)。",
        examples=[{"arguments": {"bot_token": "123456:ABC-DEF"}, "scenario": "连接 Telegram Bot 用于接收通知。"}],
        domain="automation",
        group_label="自动化",
        risk_level="medium",
        approval_policy="never",
    ),
    _tool(
        "update_webhook_subscription_item",
        "Update an existing webhook subscription.",
        [AUTOMATION_WRITE],
        update_webhook_subscription_item,
        intent="write",
        label="更新 Webhook",
        label_en="Update webhook",
        help_text="更新已有的 Webhook 订阅配置。",
        help_text_en="Update an existing webhook subscription.",
        ai_usage_hint="更新 Webhook 订阅。subscription_id 必传，payload 必传。",
        examples=[
            {
                "arguments": {
                    "subscription_id": "sub-123",
                    "payload": {"events": ["content.published", "content.updated"]},
                },
                "scenario": "更新 Webhook 监听事件。",
            }
        ],
        domain="automation",
        group_label="自动化",
        risk_level="medium",
    ),
    _tool(
        "delete_webhook_subscription_item",
        "Delete a webhook subscription permanently.",
        [AUTOMATION_WRITE],
        delete_webhook_subscription_item,
        intent="write",
        label="删除 Webhook",
        label_en="Delete webhook",
        help_text="永久删除 Webhook 订阅。",
        help_text_en="Delete a webhook subscription permanently.",
        ai_usage_hint="删除 Webhook 订阅。subscription_id 必传。操作不可恢复。",
        examples=[{"arguments": {"subscription_id": "sub-123"}, "scenario": "删除一个 Webhook 订阅。"}],
        domain="automation",
        group_label="自动化",
        risk_level="high",
        approval_policy="always",
    ),
    _tool(
        "retry_webhook_delivery_item",
        "Retry a failed webhook delivery.",
        [AUTOMATION_WRITE],
        retry_webhook_delivery_item,
        intent="action",
        label="重试投递",
        label_en="Retry delivery",
        help_text="重试一次失败的 Webhook 投递。",
        help_text_en="Retry a failed webhook delivery.",
        ai_usage_hint="重试 Webhook 投递。delivery_id 必传。",
        examples=[{"arguments": {"delivery_id": "dlv-123"}, "scenario": "重试一次失败的投递。"}],
        domain="automation",
        group_label="自动化",
        risk_level="medium",
        approval_policy="never",
    ),
    _tool(
        "replay_webhook_dead_letter_item",
        "Replay a dead letter by re-enqueuing it for delivery.",
        [AUTOMATION_WRITE],
        replay_webhook_dead_letter_item,
        intent="action",
        label="回放死信",
        label_en="Replay dead letter",
        help_text="重新入队一条死信进行投递。",
        help_text_en="Replay a dead letter by re-enqueuing it for delivery.",
        ai_usage_hint="回放 Webhook 死信。dead_letter_id 必传。将死信重新加入投递队列。",
        examples=[{"arguments": {"dead_letter_id": "dl-123"}, "scenario": "回放一条死信。"}],
        domain="automation",
        group_label="自动化",
        risk_level="medium",
        approval_policy="never",
    ),
)


_CAPABILITY_INDEX: dict[tuple[CapabilityKind, str], AgentCapabilityDefinition] = {
    (item.kind, item.name): item for item in _CAPABILITIES
}


def list_capability_definitions(*, kind: CapabilityKind | None = None) -> list[AgentCapabilityDefinition]:
    if kind is None:
        return list(_CAPABILITIES)
    return [item for item in _CAPABILITIES if item.kind == kind]


def list_capability_models(*, kind: CapabilityKind | None = None) -> list[AgentUsageCapabilityRead]:
    return [item.to_usage_model() for item in list_capability_definitions(kind=kind)]


def get_capability_definition(*, kind: CapabilityKind, name: str) -> AgentCapabilityDefinition:
    try:
        return _CAPABILITY_INDEX[(kind, name)]
    except KeyError as err:
        raise KeyError(f"Unknown capability: {kind}:{name}") from err


def execute_capability(session: Session, *, kind: CapabilityKind, name: str, **kwargs: Any) -> Any:
    capability = get_capability_definition(kind=kind, name=name)
    return capability.handler(session, **kwargs)
