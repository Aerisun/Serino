from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Literal

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aerisun.domain.automation.schemas import AgentModelConfigUpdate, AgentWorkflowCreate, AgentWorkflowRunCreateWrite
from aerisun.domain.content import service as content_service
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.content.schemas import ContentAdminRead, ContentCreate, ContentUpdate, PoemGenerationRequest
from aerisun.domain.crud import service as crud_service
from aerisun.domain.engagement.service import (
    list_admin_comments,
    list_admin_guestbook,
    moderate_comment,
    moderate_guestbook_entry,
)
from aerisun.domain.exceptions import ResourceNotFound, ValidationError
from aerisun.domain.media.schemas import AssetAdminUpdate
from aerisun.domain.media.service import (
    bulk_delete_assets,
    delete_asset,
    get_asset,
    list_assets,
    update_asset,
    upload_asset,
)
from aerisun.domain.ops.schemas import BackupSyncConfigUpdate
from aerisun.domain.site_config.models import (
    NavItem,
    PageCopy,
    Poem,
    ResumeBasics,
    SocialLink,
)
from aerisun.domain.site_config.schemas import (
    CommunityConfigUpdate,
    NavItemAdminRead,
    NavItemCreate,
    NavItemUpdate,
    NavReorderItem,
    PageCopyAdminRead,
    PageCopyCreate,
    PageCopyUpdate,
    PoemAdminRead,
    PoemCreate,
    PoemUpdate,
    ResumeBasicsAdminRead,
    ResumeBasicsCreate,
    ResumeBasicsUpdate,
    SiteProfileUpdate,
    SocialLinkAdminRead,
    SocialLinkCreate,
    SocialLinkUpdate,
)
from aerisun.domain.site_config.service import (
    attach_site_profile_id,
    get_community_config_admin,
    get_site_profile_admin,
    reorder_nav_items_admin,
    site_profile_scoped_query,
    update_community_config_admin,
    update_site_profile_admin,
)
from aerisun.domain.social.models import Friend
from aerisun.domain.social.schemas import (
    FriendAdminRead,
    FriendCreate,
    FriendFeedSourceCreate,
    FriendFeedSourceUpdate,
    FriendUpdate,
)
from aerisun.domain.social.service import (
    check_friend_now,
    create_friend_feed_admin,
    delete_friend_feed_admin,
    list_friend_feeds_admin,
    trigger_single_crawl,
    update_friend_feed_admin,
)

ManagedContentType = Literal["posts", "diary", "thoughts", "excerpts"]
GenericAdminRecordResource = Literal[
    "friends",
    "social_links",
    "poems",
    "page_copy",
    "nav_items",
    "resume_basics",
]


def _encode(value: Any) -> Any:
    return jsonable_encoder(value)


CONTENT_MODELS: dict[ManagedContentType, type] = {
    "posts": PostEntry,
    "diary": DiaryEntry,
    "thoughts": ThoughtEntry,
    "excerpts": ExcerptEntry,
}


def _content_model(content_type: ManagedContentType):
    try:
        return CONTENT_MODELS[content_type]
    except KeyError as err:
        raise ValidationError(f"Unsupported content type: {content_type}") from err


def _prepare_content_create(session: Session, content_type: ManagedContentType, data: dict[str, Any]) -> dict[str, Any]:
    return content_service.normalize_content_create_state(session, {**data, "_content_type": content_type})


def _validated_model_dump(payload: Any, schema: type[BaseModel]) -> dict[str, Any]:
    model = payload if isinstance(payload, schema) else schema.model_validate(payload)
    return model.model_dump(mode="python", exclude_none=True)


def _validated_model(payload: Any, schema: type[BaseModel]) -> BaseModel:
    return payload if isinstance(payload, schema) else schema.model_validate(payload)


def _create_content_item_with_type(
    session: Session,
    *,
    content_type: ManagedContentType,
    payload: Any,
) -> dict[str, Any]:
    return create_admin_content(
        session,
        content_type=content_type,
        payload=_validated_model_dump(payload, ContentCreate),
    )


def _update_content_item_with_type(
    session: Session,
    *,
    content_type: ManagedContentType,
    item_id: str,
    payload: Any,
) -> dict[str, Any]:
    return update_admin_content(
        session,
        content_type=content_type,
        item_id=item_id,
        payload=_validated_model_dump(payload, ContentUpdate),
    )


def _create_record_item_with_resource(
    session: Session,
    *,
    resource: GenericAdminRecordResource,
    payload: Any,
    schema: type[BaseModel],
) -> dict[str, Any]:
    return create_admin_record(
        session,
        resource=resource,
        payload=_validated_model_dump(payload, schema),
    )


def _update_record_item_with_resource(
    session: Session,
    *,
    resource: GenericAdminRecordResource,
    item_id: str,
    payload: Any,
    schema: type[BaseModel],
) -> dict[str, Any]:
    return update_admin_record(
        session,
        resource=resource,
        item_id=item_id,
        payload=_validated_model_dump(payload, schema),
    )


def list_admin_content(
    session: Session,
    *,
    content_type: ManagedContentType,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    visibility: str | None = None,
    tag: str | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> dict[str, Any]:
    return _encode(
        crud_service.list_items(
            session,
            _content_model(content_type),
            page=page,
            page_size=page_size,
            read_schema=ContentAdminRead,
            status_filter=status,
            visibility_filter=visibility,
            tag_filter=tag,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    )


def get_admin_content(session: Session, *, content_type: ManagedContentType, item_id: str) -> dict[str, Any]:
    return _encode(
        crud_service.get_item(
            session,
            _content_model(content_type),
            item_id,
            read_schema=ContentAdminRead,
        )
    )


def create_admin_content(
    session: Session, *, content_type: ManagedContentType, payload: dict[str, Any]
) -> dict[str, Any]:
    return _encode(
        crud_service.create_item(
            session,
            _content_model(content_type),
            ContentCreate.model_validate(payload),
            read_schema=ContentAdminRead,
            prepare_data=lambda inner_session, data: _prepare_content_create(inner_session, content_type, data),
        )
    )


def update_admin_content(
    session: Session,
    *,
    content_type: ManagedContentType,
    item_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _encode(
        crud_service.update_item(
            session,
            _content_model(content_type),
            item_id,
            ContentUpdate.model_validate(payload),
            read_schema=ContentAdminRead,
            prepare_data=content_service.normalize_content_update_state,
        )
    )


def delete_admin_content(session: Session, *, content_type: ManagedContentType, item_id: str) -> dict[str, str]:
    crud_service.delete_item(session, _content_model(content_type), item_id)
    return {"status": "deleted", "id": item_id, "content_type": content_type}


def create_post_item(session: Session, *, payload: ContentCreate) -> dict[str, Any]:
    return _create_content_item_with_type(session, content_type="posts", payload=payload)


def update_post_item(session: Session, *, item_id: str, payload: ContentUpdate) -> dict[str, Any]:
    return _update_content_item_with_type(session, content_type="posts", item_id=item_id, payload=payload)


def delete_post_item(session: Session, *, item_id: str) -> dict[str, str]:
    return delete_admin_content(session, content_type="posts", item_id=item_id)


def create_diary_item(session: Session, *, payload: ContentCreate) -> dict[str, Any]:
    return _create_content_item_with_type(session, content_type="diary", payload=payload)


def update_diary_item(session: Session, *, item_id: str, payload: ContentUpdate) -> dict[str, Any]:
    return _update_content_item_with_type(session, content_type="diary", item_id=item_id, payload=payload)


def delete_diary_item(session: Session, *, item_id: str) -> dict[str, str]:
    return delete_admin_content(session, content_type="diary", item_id=item_id)


def create_thought_item(session: Session, *, payload: ContentCreate) -> dict[str, Any]:
    return _create_content_item_with_type(session, content_type="thoughts", payload=payload)


def update_thought_item(session: Session, *, item_id: str, payload: ContentUpdate) -> dict[str, Any]:
    return _update_content_item_with_type(session, content_type="thoughts", item_id=item_id, payload=payload)


def delete_thought_item(session: Session, *, item_id: str) -> dict[str, str]:
    return delete_admin_content(session, content_type="thoughts", item_id=item_id)


def create_excerpt_item(session: Session, *, payload: ContentCreate) -> dict[str, Any]:
    return _create_content_item_with_type(session, content_type="excerpts", payload=payload)


def update_excerpt_item(session: Session, *, item_id: str, payload: ContentUpdate) -> dict[str, Any]:
    return _update_content_item_with_type(session, content_type="excerpts", item_id=item_id, payload=payload)


def delete_excerpt_item(session: Session, *, item_id: str) -> dict[str, str]:
    return delete_admin_content(session, content_type="excerpts", item_id=item_id)


def bulk_delete_admin_content(
    session: Session,
    *,
    content_type: ManagedContentType,
    ids: list[str],
) -> dict[str, Any]:
    return _encode(crud_service.bulk_delete_items(session, _content_model(content_type), ids))


def bulk_update_admin_content_status(
    session: Session,
    *,
    content_type: ManagedContentType,
    ids: list[str],
    status: str,
) -> dict[str, Any]:
    return _encode(crud_service.bulk_update_status_items(session, _content_model(content_type), ids, status))


def list_admin_tags(session: Session) -> list[dict[str, Any]]:
    return _encode(content_service.aggregate_tags(session))


def list_admin_content_categories(session: Session, *, content_type: str | None = None) -> list[dict[str, Any]]:
    return _encode(content_service.list_managed_categories(session, content_type=content_type))


def create_admin_content_category(session: Session, *, content_type: str, name: str) -> dict[str, Any]:
    return _encode(content_service.create_managed_category(session, content_type=content_type, name=name))


def update_admin_content_category(session: Session, *, category_id: str, name: str) -> dict[str, Any]:
    return _encode(content_service.update_managed_category(session, category_id=category_id, name=name))


def delete_admin_content_category(session: Session, *, category_id: str) -> dict[str, str]:
    content_service.delete_managed_category(session, category_id=category_id)
    return {"status": "deleted", "id": category_id}


def list_comment_queue(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    path: str | None = None,
    surface: str | None = None,
    keyword: str | None = None,
    author: str | None = None,
    email: str | None = None,
    sort: str | None = None,
) -> dict[str, Any]:
    effective_status = status or "pending"
    return _encode(
        list_admin_comments(
            session=session,
            page=page,
            page_size=page_size,
            status=effective_status,
            path=path,
            surface=surface,
            keyword=keyword,
            author=author,
            email=email,
            sort=sort,
        )
    )


def moderate_comment_item(
    session: Session, *, comment_id: str, action: str, reason: str | None = None
) -> dict[str, Any]:
    try:
        waline_id = int(comment_id)
    except ValueError as err:
        raise ResourceNotFound("Comment not found") from err
    result = moderate_comment(session, waline_id, action, reason)
    if result is None:
        return {"status": "no-op", "id": comment_id}
    return _encode(result)


def list_guestbook_queue(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    path: str | None = None,
    keyword: str | None = None,
    author: str | None = None,
    email: str | None = None,
    sort: str | None = None,
) -> dict[str, Any]:
    effective_status = status or "pending"
    return _encode(
        list_admin_guestbook(
            session=session,
            page=page,
            page_size=page_size,
            status=effective_status,
            path=path,
            keyword=keyword,
            author=author,
            email=email,
            sort=sort,
        )
    )


def moderate_guestbook_item(
    session: Session, *, entry_id: str, action: str, reason: str | None = None
) -> dict[str, Any]:
    try:
        waline_id = int(entry_id)
    except ValueError as err:
        raise ResourceNotFound("Guestbook entry not found") from err
    result = moderate_guestbook_entry(session, waline_id, action, reason)
    if result is None:
        return {"status": "no-op", "id": entry_id}
    return _encode(result)


def get_admin_site_profile_config(session: Session) -> dict[str, Any]:
    return _encode(get_site_profile_admin(session))


def update_admin_site_profile_config(session: Session, *, payload: dict[str, Any]) -> dict[str, Any]:
    return _encode(update_site_profile_admin(session, SiteProfileUpdate.model_validate(payload)))


def get_admin_community_config_state(session: Session) -> dict[str, Any]:
    return _encode(get_community_config_admin(session))


def update_admin_community_config_state(session: Session, *, payload: dict[str, Any]) -> dict[str, Any]:
    return _encode(update_community_config_admin(session, CommunityConfigUpdate.model_validate(payload)))


def list_admin_assets_collection(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    query: str | None = None,
    scope: str = "user",
) -> dict[str, Any]:
    return _encode(list_assets(session, page=page, page_size=page_size, q=query, scope=scope))


def get_admin_asset_item(session: Session, *, asset_id: str) -> dict[str, Any]:
    return _encode(get_asset(session, asset_id))


def upload_admin_asset_item(
    session: Session,
    *,
    file_name: str,
    content_base64: str,
    mime_type: str | None = None,
    visibility: str = "internal",
    scope: str = "user",
    category: str = "general",
    note: str | None = None,
) -> dict[str, Any]:
    try:
        content = base64.b64decode(content_base64, validate=True)
    except Exception as err:
        raise ValidationError("Invalid base64 file content") from err
    return _encode(
        upload_asset(
            session,
            file_name=file_name,
            content=content,
            mime_type=mime_type,
            visibility=visibility,
            scope=scope,
            category=category,
            note=note,
        )
    )


def update_admin_asset_item(session: Session, *, asset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _encode(update_asset(session, asset_id, AssetAdminUpdate.model_validate(payload)))


def delete_admin_asset_item(session: Session, *, asset_id: str) -> dict[str, str]:
    delete_asset(session, asset_id)
    return {"status": "deleted", "id": asset_id}


def bulk_delete_admin_assets(session: Session, *, ids: list[str]) -> dict[str, int]:
    return {"affected": bulk_delete_assets(session, ids)}


@dataclass(frozen=True, slots=True)
class AdminCrudTarget:
    model: type
    create_schema: type[BaseModel]
    update_schema: type[BaseModel]
    read_schema: type[BaseModel]
    base_query_factory: Any = None
    prepare_create_data: Any = None
    prepare_update_data: Any = None


ADMIN_RECORD_TARGETS: dict[str, AdminCrudTarget] = {
    "friends": AdminCrudTarget(
        model=Friend,
        create_schema=FriendCreate,
        update_schema=FriendUpdate,
        read_schema=FriendAdminRead,
    ),
    "social_links": AdminCrudTarget(
        model=SocialLink,
        create_schema=SocialLinkCreate,
        update_schema=SocialLinkUpdate,
        read_schema=SocialLinkAdminRead,
        base_query_factory=lambda session: site_profile_scoped_query(session, SocialLink),
        prepare_create_data=attach_site_profile_id,
    ),
    "poems": AdminCrudTarget(
        model=Poem,
        create_schema=PoemCreate,
        update_schema=PoemUpdate,
        read_schema=PoemAdminRead,
        base_query_factory=lambda session: site_profile_scoped_query(session, Poem),
        prepare_create_data=attach_site_profile_id,
    ),
    "page_copy": AdminCrudTarget(
        model=PageCopy,
        create_schema=PageCopyCreate,
        update_schema=PageCopyUpdate,
        read_schema=PageCopyAdminRead,
    ),
    "nav_items": AdminCrudTarget(
        model=NavItem,
        create_schema=NavItemCreate,
        update_schema=NavItemUpdate,
        read_schema=NavItemAdminRead,
        base_query_factory=lambda session: site_profile_scoped_query(session, NavItem),
        prepare_create_data=attach_site_profile_id,
    ),
    "resume_basics": AdminCrudTarget(
        model=ResumeBasics,
        create_schema=ResumeBasicsCreate,
        update_schema=ResumeBasicsUpdate,
        read_schema=ResumeBasicsAdminRead,
    ),
}


def _record_target(resource: GenericAdminRecordResource) -> AdminCrudTarget:
    try:
        return ADMIN_RECORD_TARGETS[resource]
    except KeyError as err:
        raise ValidationError(f"Unsupported admin resource: {resource}") from err


def list_admin_records(
    session: Session,
    *,
    resource: GenericAdminRecordResource,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> dict[str, Any]:
    target = _record_target(resource)
    return _encode(
        crud_service.list_items(
            session,
            target.model,
            page=page,
            page_size=page_size,
            read_schema=target.read_schema,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            base_query_factory=target.base_query_factory,
        )
    )


def get_admin_record(session: Session, *, resource: GenericAdminRecordResource, item_id: str) -> dict[str, Any]:
    target = _record_target(resource)
    return _encode(
        crud_service.get_item(
            session,
            target.model,
            item_id,
            read_schema=target.read_schema,
            base_query_factory=target.base_query_factory,
        )
    )


def create_admin_record(
    session: Session,
    *,
    resource: GenericAdminRecordResource,
    payload: dict[str, Any],
) -> dict[str, Any]:
    target = _record_target(resource)
    return _encode(
        crud_service.create_item(
            session,
            target.model,
            target.create_schema.model_validate(payload),
            read_schema=target.read_schema,
            prepare_data=target.prepare_create_data,
        )
    )


def update_admin_record(
    session: Session,
    *,
    resource: GenericAdminRecordResource,
    item_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    target = _record_target(resource)
    return _encode(
        crud_service.update_item(
            session,
            target.model,
            item_id,
            target.update_schema.model_validate(payload),
            read_schema=target.read_schema,
            base_query_factory=target.base_query_factory,
            prepare_data=target.prepare_update_data,
        )
    )


def delete_admin_record(session: Session, *, resource: GenericAdminRecordResource, item_id: str) -> dict[str, str]:
    target = _record_target(resource)
    crud_service.delete_item(session, target.model, item_id, base_query_factory=target.base_query_factory)
    return {"status": "deleted", "resource": resource, "id": item_id}


def create_friend_item(session: Session, *, payload: FriendCreate) -> dict[str, Any]:
    return _create_record_item_with_resource(
        session,
        resource="friends",
        payload=payload,
        schema=FriendCreate,
    )


def update_friend_item(session: Session, *, item_id: str, payload: FriendUpdate) -> dict[str, Any]:
    return _update_record_item_with_resource(
        session,
        resource="friends",
        item_id=item_id,
        payload=payload,
        schema=FriendUpdate,
    )


def delete_friend_item(session: Session, *, item_id: str) -> dict[str, str]:
    return delete_admin_record(session, resource="friends", item_id=item_id)


def check_friend_item(session: Session, *, friend_id: str) -> dict[str, Any]:
    return _encode(check_friend_now(session, friend_id))


def create_social_link_item(session: Session, *, payload: SocialLinkCreate) -> dict[str, Any]:
    return _create_record_item_with_resource(
        session,
        resource="social_links",
        payload=payload,
        schema=SocialLinkCreate,
    )


def update_social_link_item(session: Session, *, item_id: str, payload: SocialLinkUpdate) -> dict[str, Any]:
    return _update_record_item_with_resource(
        session,
        resource="social_links",
        item_id=item_id,
        payload=payload,
        schema=SocialLinkUpdate,
    )


def delete_social_link_item(session: Session, *, item_id: str) -> dict[str, str]:
    return delete_admin_record(session, resource="social_links", item_id=item_id)


def create_poem_item(session: Session, *, payload: PoemCreate) -> dict[str, Any]:
    return _create_record_item_with_resource(
        session,
        resource="poems",
        payload=payload,
        schema=PoemCreate,
    )


def update_poem_item(session: Session, *, item_id: str, payload: PoemUpdate) -> dict[str, Any]:
    return _update_record_item_with_resource(
        session,
        resource="poems",
        item_id=item_id,
        payload=payload,
        schema=PoemUpdate,
    )


def delete_poem_item(session: Session, *, item_id: str) -> dict[str, str]:
    return delete_admin_record(session, resource="poems", item_id=item_id)


def create_page_copy_item(session: Session, *, payload: PageCopyCreate) -> dict[str, Any]:
    return _create_record_item_with_resource(
        session,
        resource="page_copy",
        payload=payload,
        schema=PageCopyCreate,
    )


def update_page_copy_item(session: Session, *, item_id: str, payload: PageCopyUpdate) -> dict[str, Any]:
    return _update_record_item_with_resource(
        session,
        resource="page_copy",
        item_id=item_id,
        payload=payload,
        schema=PageCopyUpdate,
    )


def delete_page_copy_item(session: Session, *, item_id: str) -> dict[str, str]:
    return delete_admin_record(session, resource="page_copy", item_id=item_id)


def create_nav_item(session: Session, *, payload: NavItemCreate) -> dict[str, Any]:
    return _create_record_item_with_resource(
        session,
        resource="nav_items",
        payload=payload,
        schema=NavItemCreate,
    )


def update_nav_item(session: Session, *, item_id: str, payload: NavItemUpdate) -> dict[str, Any]:
    return _update_record_item_with_resource(
        session,
        resource="nav_items",
        item_id=item_id,
        payload=payload,
        schema=NavItemUpdate,
    )


def delete_nav_item(session: Session, *, item_id: str) -> dict[str, str]:
    return delete_admin_record(session, resource="nav_items", item_id=item_id)


def reorder_nav_items(session: Session, *, items: list[NavReorderItem]) -> list[dict[str, Any]]:
    normalized = [item if isinstance(item, NavReorderItem) else NavReorderItem.model_validate(item) for item in items]
    return reorder_admin_nav_records(
        session,
        items=[item.model_dump(mode="python", exclude_none=True) for item in normalized],
    )


def create_resume_basics_item(session: Session, *, payload: ResumeBasicsCreate) -> dict[str, Any]:
    return _create_record_item_with_resource(
        session,
        resource="resume_basics",
        payload=payload,
        schema=ResumeBasicsCreate,
    )


def update_resume_basics_item(session: Session, *, item_id: str, payload: ResumeBasicsUpdate) -> dict[str, Any]:
    return _update_record_item_with_resource(
        session,
        resource="resume_basics",
        item_id=item_id,
        payload=payload,
        schema=ResumeBasicsUpdate,
    )


def delete_resume_basics_item(session: Session, *, item_id: str) -> dict[str, str]:
    return delete_admin_record(session, resource="resume_basics", item_id=item_id)


def reorder_admin_nav_records(session: Session, *, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = [NavReorderItem.model_validate(item) for item in items]
    return _encode(reorder_nav_items_admin(session, payload))


def list_friend_feed_sources(session: Session, *, friend_id: str) -> list[dict[str, Any]]:
    return _encode(list_friend_feeds_admin(session, friend_id))


def create_friend_feed_source(session: Session, *, friend_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    validated = FriendFeedSourceCreate.model_validate({**payload, "friend_id": friend_id})
    return _encode(create_friend_feed_admin(session, friend_id, validated))


def update_friend_feed_source(session: Session, *, feed_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _encode(update_friend_feed_admin(session, feed_id, FriendFeedSourceUpdate.model_validate(payload)))


def delete_friend_feed_source(session: Session, *, feed_id: str) -> dict[str, str]:
    delete_friend_feed_admin(session, feed_id)
    return {"status": "deleted", "id": feed_id}


def trigger_feed_crawl(session: Session, *, feed_id: str | None = None) -> dict[str, Any]:
    if feed_id:
        return _encode(trigger_single_crawl(session, feed_id))
    from aerisun.domain.social.crawler import crawl_all_feeds

    return _encode(crawl_all_feeds())


def get_subscription_config_state(session: Session) -> dict[str, Any]:
    from aerisun.domain.subscription.service import get_subscription_admin_config

    return _encode(get_subscription_admin_config(session))


def list_subscription_subscribers(
    session: Session,
    *,
    mode: str = "all",
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    from aerisun.domain.subscription.service import list_admin_subscribers

    items, total = list_admin_subscribers(session, mode=mode, search=search, page=page, page_size=page_size)
    return _encode({"items": items, "total": total, "page": page, "page_size": page_size})


def list_subscription_delivery_history(
    session: Session,
    *,
    email: str,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    from aerisun.domain.subscription.service import list_subscriber_delivery_history

    items, total = list_subscriber_delivery_history(session, email=email, page=page, page_size=page_size)
    return _encode({"items": items, "total": total, "page": page, "page_size": page_size})


def update_subscription_config(session: Session, *, payload: dict[str, Any]) -> dict[str, Any]:
    from aerisun.domain.subscription.schemas import ContentSubscriptionConfigAdminUpdate
    from aerisun.domain.subscription.service import update_subscription_admin_config

    return _encode(
        update_subscription_admin_config(
            session,
            ContentSubscriptionConfigAdminUpdate.model_validate(payload),
        )
    )


def test_subscription_config(
    session: Session,
    *,
    payload: dict[str, Any],
    persist_success: bool = False,
) -> dict[str, Any]:
    from aerisun.domain.subscription.schemas import ContentSubscriptionConfigAdminUpdate
    from aerisun.domain.subscription.service import send_subscription_test_email

    return _encode(
        send_subscription_test_email(
            session,
            ContentSubscriptionConfigAdminUpdate.model_validate(payload),
            persist_success=persist_success,
        )
    )


def update_subscription_subscriber(
    session: Session,
    *,
    email: str,
    is_active: bool,
) -> dict[str, Any]:
    from aerisun.domain.subscription.service import set_admin_subscriber_active

    return _encode(set_admin_subscriber_active(session, email=email, is_active=is_active))


def delete_subscription_subscriber(session: Session, *, email: str) -> dict[str, str]:
    from aerisun.domain.subscription.service import delete_admin_subscriber

    delete_admin_subscriber(session, email=email)
    return {"status": "deleted", "email": email}


def get_visitor_auth_config_state(session: Session) -> dict[str, Any]:
    from aerisun.domain.site_auth.config_service import get_site_auth_admin_config

    return _encode(get_site_auth_admin_config(session))


def list_visitor_users(
    session: Session,
    *,
    mode: str = "all",
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    from aerisun.domain.site_auth.service import list_site_users_admin

    items, total = list_site_users_admin(session, auth_mode=mode, search=search, page=page, page_size=page_size)
    return _encode({"items": items, "total": total, "page": page, "page_size": page_size})


def list_admin_identity_bindings(session: Session) -> list[dict[str, Any]]:
    from aerisun.domain.site_auth.admin_binding import list_site_admin_identities_admin

    return _encode(list_site_admin_identities_admin(session))


def update_visitor_auth_config(session: Session, *, payload: dict[str, Any]) -> dict[str, Any]:
    from aerisun.domain.site_auth.config_service import update_site_auth_admin_config
    from aerisun.domain.site_auth.schemas import SiteAuthConfigAdminUpdate

    return _encode(
        update_site_auth_admin_config(
            session,
            SiteAuthConfigAdminUpdate.model_validate(payload),
        )
    )


def bind_admin_identity_email(
    session: Session,
    *,
    admin_user_id: str,
    email: str,
) -> dict[str, Any]:
    from aerisun.domain.site_auth.admin_binding import bind_site_admin_identity_by_email
    from aerisun.domain.site_auth.schemas import SiteAdminEmailIdentityBindRequest

    return _encode(
        bind_site_admin_identity_by_email(
            session,
            SiteAdminEmailIdentityBindRequest.model_validate({"email": email}),
            admin_user_id=admin_user_id,
        )
    )


def delete_admin_identity_binding(session: Session, *, identity_id: str) -> dict[str, str]:
    from aerisun.domain.site_auth.admin_binding import delete_site_admin_identity

    delete_site_admin_identity(session, identity_id)
    return {"status": "deleted", "identity_id": identity_id}


def get_admin_login_options_state(session: Session) -> dict[str, Any]:
    from aerisun.domain.site_auth.service import get_admin_login_options

    return _encode(get_admin_login_options(session))


def get_admin_me(session: Session, *, admin_user_id: str | None = None) -> dict[str, Any]:
    from aerisun.domain.iam.models import AdminUser
    from aerisun.domain.iam.service import get_admin_profile

    resolved_admin_id = str(admin_user_id or "").strip()
    if resolved_admin_id:
        admin = session.get(AdminUser, resolved_admin_id)
        if admin is None:
            raise ResourceNotFound("Admin user not found")
        return _encode(get_admin_profile(admin))

    admins = session.query(AdminUser).order_by(AdminUser.created_at.asc()).all()
    if not admins:
        raise ResourceNotFound("Admin user not found")
    if len(admins) > 1:
        raise ValidationError(
            "admin_user_id is required because MCP API keys are not bound to a current admin session."
        )
    return _encode(get_admin_profile(admins[0]))


def list_admin_sessions(
    session: Session,
    *,
    admin_user_id: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    from datetime import UTC, datetime

    from aerisun.domain.iam.models import AdminSession, AdminUser

    resolved_admin_id = str(admin_user_id or "").strip() or None
    safe_page = max(1, int(page or 1))
    safe_page_size = max(1, min(int(page_size or 100), 200))
    now = datetime.now(UTC)

    query = session.query(AdminSession, AdminUser).join(AdminUser, AdminUser.id == AdminSession.admin_user_id)
    if resolved_admin_id:
        query = query.filter(AdminSession.admin_user_id == resolved_admin_id)
    rows = query.order_by(AdminSession.created_at.desc()).all()

    items: list[dict[str, Any]] = []
    for session_row, user in rows:
        comparison_now = now.replace(tzinfo=None) if getattr(session_row.expires_at, "tzinfo", None) is None else now
        items.append(
            {
                "id": session_row.id,
                "admin_user_id": user.id,
                "username": user.username,
                "expires_at": session_row.expires_at,
                "created_at": session_row.created_at,
                "is_active": bool(session_row.expires_at > comparison_now),
            }
        )

    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    return _encode(
        {
            "items": items[start:end],
            "total": len(items),
            "page": safe_page,
            "page_size": safe_page_size,
        }
    )


def update_admin_profile_item(
    session: Session,
    *,
    admin_user_id: str,
    username: str | None = None,
) -> dict[str, Any]:
    from aerisun.domain.iam.models import AdminUser
    from aerisun.domain.iam.service import update_admin_profile

    admin = session.get(AdminUser, admin_user_id)
    if admin is None:
        raise ResourceNotFound("Admin user not found")
    return _encode(update_admin_profile(session, admin, username))


def revoke_admin_session_item(
    session: Session,
    *,
    admin_user_id: str,
    session_id: str,
) -> dict[str, str]:
    from aerisun.domain.iam.service import revoke_admin_session

    revoke_admin_session(session, admin_user_id, session_id)
    return {"status": "revoked", "session_id": session_id}


def create_admin_api_key(
    session: Session,
    *,
    key_name: str,
    scopes: list[str],
) -> dict[str, Any]:
    from aerisun.domain.iam.service import create_api_key

    return _encode(create_api_key(session, key_name, scopes))


def update_admin_api_key(
    session: Session,
    *,
    key_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from aerisun.domain.iam.schemas import ApiKeyUpdate
    from aerisun.domain.iam.service import update_api_key

    return _encode(update_api_key(session, key_id, ApiKeyUpdate.model_validate(payload)))


def delete_admin_api_key(session: Session, *, key_id: str) -> dict[str, str]:
    from aerisun.domain.iam.service import delete_api_key

    delete_api_key(session, key_id)
    return {"status": "deleted", "key_id": key_id}


def list_admin_api_keys_state(session: Session) -> list[dict[str, Any]]:
    from aerisun.domain.iam.service import list_api_keys

    return _encode(list_api_keys(session))


def update_mcp_admin_config_item(
    session: Session,
    *,
    payload: dict[str, Any],
    api_key_id: str | None = None,
) -> dict[str, Any]:
    from aerisun.core.settings import get_settings
    from aerisun.domain.agent.schemas import McpAdminConfigUpdate
    from aerisun.domain.agent.service import save_mcp_admin_config

    settings = get_settings()
    return _encode(
        save_mcp_admin_config(
            session,
            settings.site_url,
            McpAdminConfigUpdate.model_validate(payload),
            api_key_id,
        )
    )


def update_proxy_config_item(session: Session, *, payload: dict[str, Any]) -> dict[str, Any]:
    from aerisun.domain.outbound_proxy.schemas import OutboundProxyConfigUpdate
    from aerisun.domain.outbound_proxy.service import update_outbound_proxy_config

    return _encode(
        update_outbound_proxy_config(
            session,
            OutboundProxyConfigUpdate.model_validate(payload),
        )
    )


def get_outbound_proxy_config_state(session: Session) -> dict[str, Any]:
    from aerisun.domain.outbound_proxy.service import get_outbound_proxy_config

    return _encode(get_outbound_proxy_config(session))


def test_proxy_config_item(session: Session, *, payload: dict[str, Any]) -> dict[str, Any]:
    from aerisun.domain.outbound_proxy.schemas import OutboundProxyConfigUpdate
    from aerisun.domain.outbound_proxy.service import test_outbound_proxy_config

    return _encode(
        test_outbound_proxy_config(
            session,
            OutboundProxyConfigUpdate.model_validate(payload),
        )
    )


def create_backup_snapshot_item(session: Session) -> dict[str, Any]:
    from aerisun.domain.ops.backup_sync import list_backup_snapshots, trigger_backup_sync
    from aerisun.domain.ops.schemas import BackupSnapshotRead

    run = trigger_backup_sync(session)
    snapshots = list_backup_snapshots(session)
    if snapshots:
        return _encode(snapshots[0])
    return _encode(
        BackupSnapshotRead(
            id=run.id,
            snapshot_type=run.trigger_kind or "manual",
            status=run.status,
            db_path="aerisun.db",
            replica_url=None,
            backup_path=None,
            checksum=None,
            completed_at=run.finished_at,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )
    )


def restore_backup_snapshot_item(session: Session, *, snapshot_id: str) -> dict[str, Any]:
    from aerisun.domain.ops.backup_sync import restore_backup_snapshot

    return _encode(restore_backup_snapshot(session, snapshot_id))


def update_backup_sync_config_item(session: Session, *, payload: dict[str, Any]) -> dict[str, Any]:
    from aerisun.domain.ops.backup_sync import update_backup_sync_config
    from aerisun.domain.ops.schemas import BackupSyncConfigUpdate

    return _encode(
        update_backup_sync_config(
            session,
            BackupSyncConfigUpdate.model_validate(payload),
        )
    )


def trigger_backup_sync_item(session: Session) -> dict[str, Any]:
    from aerisun.domain.ops.backup_sync import trigger_backup_sync

    return _encode(trigger_backup_sync(session))


def retry_backup_sync_run_item(session: Session, *, run_id: str) -> dict[str, Any]:
    from aerisun.domain.ops.backup_sync import retry_backup_sync_run

    return _encode(retry_backup_sync_run(session, run_id))


def pause_backup_sync_item(session: Session) -> dict[str, Any]:
    from aerisun.domain.ops.backup_sync import pause_backup_sync

    return _encode(pause_backup_sync(session))


def resume_backup_sync_item(session: Session) -> dict[str, Any]:
    from aerisun.domain.ops.backup_sync import resume_backup_sync

    return _encode(resume_backup_sync(session))


def restore_backup_commit_item(session: Session, *, commit_id: str) -> dict[str, Any]:
    from aerisun.domain.ops.backup_sync import restore_backup_commit

    return _encode(restore_backup_commit(session, commit_id))


def restore_config_revision_item(
    session: Session,
    *,
    revision_id: str,
    payload: dict[str, Any],
    actor_id: str | None = None,
) -> dict[str, Any]:
    from aerisun.domain.ops.schemas import ConfigRevisionRestoreWrite
    from aerisun.domain.ops.service import restore_config_revision

    return _encode(
        restore_config_revision(
            session,
            revision_id=revision_id,
            actor_id=actor_id,
            payload=ConfigRevisionRestoreWrite.model_validate(payload),
        )
    )


def get_system_info_state(session: Session) -> dict[str, Any]:
    from aerisun.domain.ops.service import get_system_info

    del session
    return _encode(get_system_info())


def get_dashboard_stats_state(session: Session) -> dict[str, Any]:
    from aerisun.domain.ops.service import get_dashboard_stats

    return _encode(get_dashboard_stats(session))


def list_audit_logs_state(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    action: str | None = None,
    actor_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    from aerisun.domain.ops.service import list_audit_logs

    return _encode(
        list_audit_logs(
            session,
            page=page,
            page_size=page_size,
            action=action,
            actor_id=actor_id,
            date_from=date_from,
            date_to=date_to,
        )
    )


def list_config_revisions_state(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    resource_key: str | None = None,
    actor_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    from aerisun.domain.ops.service import list_config_revisions

    return _encode(
        list_config_revisions(
            session,
            page=page,
            page_size=page_size,
            resource_key=resource_key,
            actor_id=actor_id,
            date_from=date_from,
            date_to=date_to,
        )
    )


def get_config_revision_detail_state(session: Session, *, revision_id: str) -> dict[str, Any]:
    from aerisun.domain.ops.service import get_config_revision_detail

    return _encode(get_config_revision_detail(session, revision_id))


def list_visitor_records_state(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    path: str | None = None,
    ip: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    include_bots: bool = False,
) -> dict[str, Any]:
    from aerisun.domain.ops.service import list_visitor_records

    return _encode(
        list_visitor_records(
            session,
            page=page,
            page_size=page_size,
            path=path,
            ip=ip,
            date_from=date_from,
            date_to=date_to,
            include_bots=include_bots,
        )
    )


def get_backup_sync_config_state(session: Session) -> dict[str, Any]:
    from aerisun.domain.ops.backup_sync import get_backup_sync_config

    return _encode(get_backup_sync_config(session))


def list_backup_sync_queue_state(session: Session) -> list[dict[str, Any]]:
    from aerisun.domain.ops.backup_sync import list_backup_sync_queue

    return _encode(list_backup_sync_queue(session))


def list_backup_sync_runs_state(session: Session) -> list[dict[str, Any]]:
    from aerisun.domain.ops.backup_sync import list_backup_sync_runs

    return _encode(list_backup_sync_runs(session))


def list_backup_sync_commits_state(session: Session) -> list[dict[str, Any]]:
    from aerisun.domain.ops.backup_sync import list_backup_sync_commits

    return _encode(list_backup_sync_commits(session))


def list_backup_snapshots_state(session: Session) -> list[dict[str, Any]]:
    from aerisun.domain.ops.backup_sync import list_backup_snapshots

    return _encode(list_backup_snapshots(session))


def update_agent_model_config_item(session: Session, *, payload: dict[str, Any]) -> dict[str, Any]:
    from aerisun.domain.automation.schemas import AgentModelConfigUpdate
    from aerisun.domain.automation.settings import update_agent_model_config

    return _encode(
        update_agent_model_config(
            session,
            AgentModelConfigUpdate.model_validate(payload),
        )
    )


def get_agent_model_config_state(session: Session) -> dict[str, Any]:
    from aerisun.domain.automation.settings import get_agent_model_config

    return _encode(get_agent_model_config(session))


def test_agent_model_config(session: Session, *, payload: AgentModelConfigUpdate | dict[str, Any]) -> dict[str, Any]:
    from aerisun.domain.automation.service import test_agent_model_config as _test_agent_model_config

    return _encode(_test_agent_model_config(session, _validated_model(payload, AgentModelConfigUpdate)))


def list_agent_workflows_state(session: Session) -> list[dict[str, Any]]:
    from aerisun.domain.automation.settings import list_agent_workflows

    return _encode(list_agent_workflows(session))


def get_agent_workflow_catalog_state(session: Session, *, workflow_key: str | None = None) -> dict[str, Any]:
    from aerisun.domain.automation.service import get_agent_workflow_catalog

    return _encode(get_agent_workflow_catalog(session, workflow_key=workflow_key))


def list_agent_runs_state(session: Session) -> list[dict[str, Any]]:
    from aerisun.domain.automation.service import list_runs

    return _encode(list_runs(session))


def get_agent_run_detail_state(session: Session, *, run_id: str) -> dict[str, Any]:
    from aerisun.domain.automation.service import get_run_detail

    run, steps = get_run_detail(session, run_id)
    return _encode({"run": run, "steps": steps})


def list_pending_approvals_state(session: Session) -> list[dict[str, Any]]:
    from aerisun.domain.automation.service import list_pending_approvals

    return _encode(list_pending_approvals(session))


def create_agent_workflow_item(session: Session, *, payload: dict[str, Any]) -> dict[str, Any]:
    from aerisun.domain.automation.schemas import AgentWorkflowCreate
    from aerisun.domain.automation.settings import create_agent_workflow

    return _encode(create_agent_workflow(session, AgentWorkflowCreate.model_validate(payload)))


def validate_agent_workflow(session: Session, *, payload: AgentWorkflowCreate | dict[str, Any]) -> dict[str, Any]:
    from aerisun.domain.automation.validation import compile_workflow

    workflow = _validated_model(payload, AgentWorkflowCreate)
    return _encode(compile_workflow(workflow.model_dump(mode="json"), session=session))


def update_agent_workflow_item(
    session: Session,
    *,
    workflow_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from aerisun.domain.automation.schemas import AgentWorkflowUpdate
    from aerisun.domain.automation.settings import update_agent_workflow

    return _encode(
        update_agent_workflow(
            session,
            workflow_key=workflow_key,
            payload=AgentWorkflowUpdate.model_validate(payload),
        )
    )


def delete_agent_workflow_item(session: Session, *, workflow_key: str) -> dict[str, str]:
    from aerisun.domain.automation.settings import delete_agent_workflow

    delete_agent_workflow(session, workflow_key=workflow_key)
    return {"status": "deleted", "workflow_key": workflow_key}


def trigger_workflow_run(
    session: Session,
    *,
    workflow_key: str,
    payload: AgentWorkflowRunCreateWrite | dict[str, Any],
) -> dict[str, Any]:
    from aerisun.domain.automation.runtime_registry import get_automation_runtime
    from aerisun.domain.automation.service import create_workflow_run as _create_workflow_run

    return _encode(
        _create_workflow_run(
            session,
            get_automation_runtime(),
            workflow_key=workflow_key,
            payload=_validated_model(payload, AgentWorkflowRunCreateWrite),
            trigger_kind="manual",
        )
    )


def test_workflow_run(
    session: Session,
    *,
    workflow_key: str,
    payload: AgentWorkflowRunCreateWrite | dict[str, Any],
) -> dict[str, Any]:
    from aerisun.domain.automation.runtime_registry import get_automation_runtime
    from aerisun.domain.automation.service import test_workflow_run as _test_workflow_run

    return _encode(
        _test_workflow_run(
            session,
            get_automation_runtime(),
            workflow_key=workflow_key,
            payload=_validated_model(payload, AgentWorkflowRunCreateWrite),
        )
    )


def resolve_workflow_approval_item(
    session: Session,
    *,
    approval_id: str,
    actor_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from aerisun.domain.automation.runtime_registry import get_automation_runtime
    from aerisun.domain.automation.schemas import ApprovalDecisionWrite
    from aerisun.domain.automation.service import resolve_approval

    return _encode(
        resolve_approval(
            session,
            get_automation_runtime(),
            approval_id=approval_id,
            actor_id=actor_id,
            decision_payload=ApprovalDecisionWrite.model_validate(payload),
        )
    )


def create_webhook_subscription_item(session: Session, *, payload: dict[str, Any]) -> dict[str, Any]:
    from aerisun.domain.automation.schemas import WebhookSubscriptionCreate
    from aerisun.domain.automation.service import create_webhook_subscription

    return _encode(
        create_webhook_subscription(
            session,
            WebhookSubscriptionCreate.model_validate(payload),
        )
    )


def test_webhook_subscription_item(
    session: Session,
    *,
    payload: dict[str, Any],
    subscription_id: str | None = None,
) -> dict[str, Any]:
    from aerisun.domain.automation.schemas import WebhookSubscriptionCreate
    from aerisun.domain.automation.service import test_webhook_subscription

    return _encode(
        test_webhook_subscription(
            session,
            WebhookSubscriptionCreate.model_validate(payload),
            subscription_id=subscription_id,
        )
    )


def connect_telegram_webhook_item(
    session: Session,
    *,
    bot_token: str,
    send_test_message: bool = True,
) -> dict[str, Any]:
    from aerisun.domain.automation.service import connect_telegram_webhook

    return _encode(
        connect_telegram_webhook(
            session,
            bot_token=bot_token,
            send_test_message=send_test_message,
        )
    )


def update_webhook_subscription_item(
    session: Session,
    *,
    subscription_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from aerisun.domain.automation.schemas import WebhookSubscriptionUpdate
    from aerisun.domain.automation.service import update_webhook_subscription

    return _encode(
        update_webhook_subscription(
            session,
            subscription_id=subscription_id,
            payload=WebhookSubscriptionUpdate.model_validate(payload),
        )
    )


def delete_webhook_subscription_item(session: Session, *, subscription_id: str) -> dict[str, str]:
    from aerisun.domain.automation.service import delete_webhook_subscription

    delete_webhook_subscription(session, subscription_id=subscription_id)
    return {"status": "deleted", "subscription_id": subscription_id}


def list_webhook_subscriptions_state(session: Session) -> list[dict[str, Any]]:
    from aerisun.domain.automation.service import list_webhook_subscriptions

    return _encode(list_webhook_subscriptions(session))


def list_webhook_deliveries_state(session: Session) -> list[dict[str, Any]]:
    from aerisun.domain.automation.service import list_webhook_deliveries

    return _encode(list_webhook_deliveries(session))


def list_webhook_dead_letters_state(session: Session) -> list[dict[str, Any]]:
    from aerisun.domain.automation.service import list_webhook_dead_letters

    return _encode(list_webhook_dead_letters(session))


def retry_webhook_delivery_item(session: Session, *, delivery_id: str) -> dict[str, Any]:
    from aerisun.domain.automation.service import trigger_delivery_retry

    return _encode(trigger_delivery_retry(session, delivery_id=delivery_id))


def replay_webhook_dead_letter_item(session: Session, *, dead_letter_id: str) -> dict[str, Any]:
    from aerisun.domain.automation.service import replay_dead_letter

    return _encode(replay_dead_letter(session, dead_letter_id=dead_letter_id))


def export_content(session: Session, *, content_type: str) -> dict[str, Any]:
    from aerisun.domain.content.import_export_service import export_content_json

    items = export_content_json(session, content_type)
    return {"content_type": content_type, "count": len(items), "items": _encode(items)}


def import_content(session: Session, *, content_type: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    from aerisun.domain.content.import_export_service import import_content_json

    return _encode(import_content_json(session, content_type, items))


def generate_diary_poem(session: Session, *, payload: PoemGenerationRequest | dict[str, Any]) -> dict[str, Any]:
    from aerisun.domain.content.poem_generation import generate_diary_poem as _generate_diary_poem

    return _encode(_generate_diary_poem(session, _validated_model(payload, PoemGenerationRequest)))


def test_backup_sync_config(session: Session, *, payload: BackupSyncConfigUpdate | dict[str, Any]) -> dict[str, Any]:
    from aerisun.domain.ops.backup_sync import test_backup_sync_config as _test_backup_sync_config

    return _encode(_test_backup_sync_config(session, _validated_model(payload, BackupSyncConfigUpdate)))
