from __future__ import annotations

import inspect
import types
from dataclasses import dataclass, field
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel
from sqlalchemy.orm import Session

from aerisun.api.admin.scopes import (
    MCP_ASSETS_READ,
    MCP_ASSETS_WRITE,
    MCP_CONFIG_READ,
    MCP_CONFIG_WRITE,
    MCP_CONTENT_READ,
    MCP_CONTENT_WRITE,
    MCP_MODERATION_READ,
    MCP_MODERATION_WRITE,
)
from aerisun.domain.agent.capability_ids import build_capability_id
from aerisun.domain.agent.mcp_admin_tools import (
    bulk_delete_admin_assets,
    bulk_delete_admin_content,
    bulk_update_admin_content_status,
    create_admin_content,
    create_admin_content_category,
    create_admin_record,
    create_friend_feed_source,
    delete_admin_asset_item,
    delete_admin_content,
    delete_admin_content_category,
    delete_admin_record,
    delete_friend_feed_source,
    get_admin_asset_item,
    get_admin_community_config_state,
    get_admin_content,
    get_admin_record,
    get_admin_site_profile_config,
    list_admin_assets_collection,
    list_admin_content,
    list_admin_content_categories,
    list_admin_records,
    list_admin_tags,
    list_comment_queue,
    list_friend_feed_sources,
    list_guestbook_queue,
    moderate_comment_item,
    moderate_guestbook_item,
    reorder_admin_nav_records,
    trigger_feed_crawl,
    update_admin_asset_item,
    update_admin_community_config_state,
    update_admin_content,
    update_admin_content_category,
    update_admin_record,
    update_admin_site_profile_config,
    update_friend_feed_source,
    upload_admin_asset_item,
)
from aerisun.domain.agent.schemas import AgentUsageCapabilityRead
from aerisun.domain.content.feed_service import build_posts_rss_xml
from aerisun.domain.content.search_service import search_public_content
from aerisun.domain.content.service import (
    get_public_diary_entry,
    get_public_post,
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
        return {"enum": list(args)}
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
    input_schema: dict[str, Any] = field(init=False)
    output_schema: dict[str, Any] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_schema", _build_input_schema(self.handler))
        object.__setattr__(self, "output_schema", _build_output_schema(self.handler))

    @property
    def id(self) -> str:
        return build_capability_id(self.kind, self.name)

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
) -> AgentCapabilityDefinition:
    return AgentCapabilityDefinition(
        kind="tool",
        name=name,
        description=description,
        required_scopes=tuple(required_scopes),
        handler=handler,
        invocation={"transport": "mcp", "tool": name},
        examples=tuple(examples or ()),
    )


def _resource(
    name: str,
    description: str,
    required_scopes: list[str],
    handler: Any,
    *,
    response_kind: CapabilityResponseKind = "json",
    examples: list[dict[str, Any]] | None = None,
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
    )


def _get_site_config_tool(session: Session) -> dict[str, Any]:
    return get_site_config(session).model_dump()


def _list_posts_tool(session: Session, limit: int = 20, offset: int = 0) -> dict[str, Any]:
    return list_public_posts(session, limit=limit, offset=offset).model_dump()


def _get_post_tool(session: Session, slug: str) -> dict[str, Any]:
    return get_public_post(session, slug).model_dump()


def _search_content_tool(session: Session, query: str, limit: int = 10) -> dict[str, Any]:
    return search_public_content(session, query, limit).model_dump()


def _list_diary_entries_tool(session: Session, limit: int = 20, offset: int = 0) -> dict[str, Any]:
    return list_public_diary_entries(session, limit=limit, offset=offset).model_dump()


def _get_diary_entry_tool(session: Session, slug: str) -> dict[str, Any]:
    return get_public_diary_entry(session, slug).model_dump()


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
    _resource("aerisun://site-config", "Return site config as JSON.", [MCP_CONFIG_READ], get_site_config),
    _resource("aerisun://posts", "Return latest posts list as JSON.", [MCP_CONTENT_READ], _posts_resource),
    _resource("aerisun://posts/{slug}", "Return a single post by slug as JSON.", [MCP_CONTENT_READ], get_public_post),
    _resource("aerisun://diary", "Return latest diary entries as JSON.", [MCP_CONTENT_READ], _diary_resource),
    _resource(
        "aerisun://diary/{slug}",
        "Return a single diary entry by slug as JSON.",
        [MCP_CONTENT_READ],
        get_public_diary_entry,
    ),
    _resource("aerisun://thoughts", "Return latest thoughts as JSON.", [MCP_CONTENT_READ], _thoughts_resource),
    _resource("aerisun://excerpts", "Return latest excerpts as JSON.", [MCP_CONTENT_READ], _excerpts_resource),
    _resource(
        "aerisun://feeds/posts",
        "Return the posts RSS XML.",
        [MCP_CONTENT_READ],
        _posts_feed_resource,
        response_kind="text",
    ),
    _tool(
        "get_site_config",
        "Get current site config.",
        [MCP_CONFIG_READ],
        _get_site_config_tool,
        examples=[{"arguments": {}, "scenario": "读取站点基础配置用于判断功能入口。"}],
    ),
    _tool(
        "list_posts",
        "List published posts.",
        [MCP_CONTENT_READ],
        _list_posts_tool,
        examples=[{"arguments": {"limit": 10, "offset": 0}, "scenario": "列出最近文章。"}],
    ),
    _tool(
        "get_post",
        "Get a published post by slug.",
        [MCP_CONTENT_READ],
        _get_post_tool,
        examples=[{"arguments": {"slug": "hello-world"}, "scenario": "读取单篇文章正文。"}],
    ),
    _tool(
        "search_content",
        "Search public content.",
        [MCP_CONTENT_READ],
        _search_content_tool,
        examples=[{"arguments": {"query": "诗", "limit": 5}, "scenario": "按关键词搜索公开内容。"}],
    ),
    _tool("list_diary_entries", "List published diary entries.", [MCP_CONTENT_READ], _list_diary_entries_tool),
    _tool("get_diary_entry", "Get a published diary entry by slug.", [MCP_CONTENT_READ], _get_diary_entry_tool),
    _tool("list_thoughts", "List published thoughts.", [MCP_CONTENT_READ], _list_thoughts_tool),
    _tool("list_excerpts", "List published excerpts.", [MCP_CONTENT_READ], _list_excerpts_tool),
    _tool(
        "list_admin_content",
        "List admin content for posts, diary, thoughts, or excerpts.",
        [MCP_CONTENT_READ],
        list_admin_content,
        examples=[{"arguments": {"content_type": "posts", "status": "draft"}, "scenario": "查看草稿文章列表。"}],
    ),
    _tool("get_admin_content", "Get one admin content item by ID.", [MCP_CONTENT_READ], get_admin_content),
    _tool(
        "create_admin_content",
        "Create admin content and set initial status or visibility.",
        [MCP_CONTENT_WRITE],
        create_admin_content,
        examples=[
            {
                "arguments": {
                    "content_type": "posts",
                    "payload": {"slug": "new-post", "title": "新文章", "body": "正文", "status": "draft"},
                },
                "scenario": "创建一篇草稿文章。",
            }
        ],
    ),
    _tool(
        "update_admin_content",
        "Update admin content, including publish state and visibility.",
        [MCP_CONTENT_WRITE],
        update_admin_content,
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
    ),
    _tool("delete_admin_content", "Delete one admin content item.", [MCP_CONTENT_WRITE], delete_admin_content),
    _tool(
        "bulk_delete_admin_content",
        "Bulk-delete admin content items.",
        [MCP_CONTENT_WRITE],
        bulk_delete_admin_content,
    ),
    _tool(
        "bulk_update_admin_content_status",
        "Bulk update content status for publishing or archiving.",
        [MCP_CONTENT_WRITE],
        bulk_update_admin_content_status,
    ),
    _tool("list_admin_tags", "List aggregated admin content tags.", [MCP_CONTENT_READ], _list_admin_tags_tool),
    _tool(
        "list_admin_content_categories",
        "List managed content categories.",
        [MCP_CONTENT_READ],
        _list_admin_content_categories_tool,
    ),
    _tool(
        "create_admin_content_category",
        "Create a managed content category.",
        [MCP_CONTENT_WRITE],
        create_admin_content_category,
    ),
    _tool(
        "update_admin_content_category",
        "Rename a managed content category.",
        [MCP_CONTENT_WRITE],
        update_admin_content_category,
    ),
    _tool(
        "delete_admin_content_category",
        "Delete a managed content category.",
        [MCP_CONTENT_WRITE],
        delete_admin_content_category,
    ),
    _tool(
        "list_comment_moderation_queue",
        "List comments awaiting moderation.",
        [MCP_MODERATION_READ],
        list_comment_queue,
    ),
    _tool(
        "moderate_comment",
        "Approve, reject, or delete one comment.",
        [MCP_MODERATION_WRITE],
        moderate_comment_item,
        examples=[{"arguments": {"comment_id": "123", "action": "approve"}, "scenario": "通过一条评论。"}],
    ),
    _tool(
        "list_guestbook_moderation_queue",
        "List guestbook entries awaiting moderation.",
        [MCP_MODERATION_READ],
        list_guestbook_queue,
    ),
    _tool(
        "moderate_guestbook_entry",
        "Approve, reject, or delete one guestbook entry.",
        [MCP_MODERATION_WRITE],
        moderate_guestbook_item,
    ),
    _tool(
        "get_admin_site_profile",
        "Get the admin site profile settings.",
        [MCP_CONFIG_READ],
        get_admin_site_profile_config,
    ),
    _tool(
        "update_admin_site_profile",
        "Update site profile settings.",
        [MCP_CONFIG_WRITE],
        update_admin_site_profile_config,
    ),
    _tool(
        "get_admin_community_config",
        "Get comment and community settings.",
        [MCP_CONFIG_READ],
        get_admin_community_config_state,
    ),
    _tool(
        "update_admin_community_config",
        "Update comment and community settings.",
        [MCP_CONFIG_WRITE],
        update_admin_community_config_state,
    ),
    _tool(
        "list_admin_assets",
        "List uploaded assets from the admin library.",
        [MCP_ASSETS_READ],
        list_admin_assets_collection,
    ),
    _tool("get_admin_asset", "Get one admin asset by ID.", [MCP_ASSETS_READ], get_admin_asset_item),
    _tool(
        "upload_admin_asset",
        "Upload an asset using base64-encoded file content.",
        [MCP_ASSETS_WRITE],
        upload_admin_asset_item,
    ),
    _tool(
        "update_admin_asset",
        "Update asset metadata like visibility or category.",
        [MCP_ASSETS_WRITE],
        update_admin_asset_item,
    ),
    _tool("delete_admin_asset", "Delete one admin asset.", [MCP_ASSETS_WRITE], delete_admin_asset_item),
    _tool("bulk_delete_admin_assets", "Bulk-delete admin assets.", [MCP_ASSETS_WRITE], bulk_delete_admin_assets),
    _tool(
        "list_admin_records",
        "List admin records for friends, social_links, poems, page_copy, display_options, nav_items, "
        "resume_basics, resume_skills, or resume_experiences.",
        [MCP_CONFIG_READ],
        list_admin_records,
    ),
    _tool(
        "get_admin_record",
        "Get one admin record from generic config collections.",
        [MCP_CONFIG_READ],
        get_admin_record,
    ),
    _tool(
        "create_admin_record",
        "Create one admin record in generic config collections.",
        [MCP_CONFIG_WRITE],
        create_admin_record,
    ),
    _tool(
        "update_admin_record",
        "Update one admin record in generic config collections.",
        [MCP_CONFIG_WRITE],
        update_admin_record,
    ),
    _tool(
        "delete_admin_record",
        "Delete one admin record in generic config collections.",
        [MCP_CONFIG_WRITE],
        delete_admin_record,
    ),
    _tool("reorder_admin_nav_items", "Reorder navigation items.", [MCP_CONFIG_WRITE], _reorder_admin_nav_items_tool),
    _tool(
        "list_friend_feed_sources",
        "List feed sources for a friend site.",
        [MCP_CONFIG_READ],
        _list_friend_feed_sources_tool,
    ),
    _tool(
        "create_friend_feed_source",
        "Create a new friend feed source.",
        [MCP_CONFIG_WRITE],
        create_friend_feed_source,
    ),
    _tool(
        "update_friend_feed_source",
        "Update one friend feed source.",
        [MCP_CONFIG_WRITE],
        update_friend_feed_source,
    ),
    _tool(
        "delete_friend_feed_source",
        "Delete one friend feed source.",
        [MCP_CONFIG_WRITE],
        delete_friend_feed_source,
    ),
    _tool(
        "trigger_feed_crawl",
        "Trigger a feed crawl. When feed_id is omitted, crawl all feeds.",
        [MCP_CONFIG_WRITE],
        trigger_feed_crawl,
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
