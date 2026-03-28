from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Literal

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aerisun.domain.content import service as content_service
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.content.schemas import ContentAdminRead, ContentCreate, ContentUpdate
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
from aerisun.domain.site_config.models import (
    NavItem,
    PageCopy,
    PageDisplayOption,
    Poem,
    ResumeBasics,
    ResumeExperience,
    ResumeSkillGroup,
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
    PageDisplayOptionAdminRead,
    PageDisplayOptionCreate,
    PageDisplayOptionUpdate,
    PoemAdminRead,
    PoemCreate,
    PoemUpdate,
    ResumeBasicsAdminRead,
    ResumeBasicsCreate,
    ResumeBasicsUpdate,
    ResumeExperienceAdminRead,
    ResumeExperienceCreate,
    ResumeExperienceUpdate,
    ResumeSkillGroupAdminRead,
    ResumeSkillGroupCreate,
    ResumeSkillGroupUpdate,
    SiteProfileUpdate,
    SocialLinkAdminRead,
    SocialLinkCreate,
    SocialLinkUpdate,
)
from aerisun.domain.site_config.service import (
    attach_resume_basics_id,
    attach_site_profile_id,
    get_community_config_admin,
    get_site_profile_admin,
    reorder_nav_items_admin,
    resume_scoped_query,
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
    "display_options",
    "nav_items",
    "resume_basics",
    "resume_skills",
    "resume_experiences",
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
    return _encode(
        list_admin_comments(
            session=session,
            page=page,
            page_size=page_size,
            status=status,
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
    return _encode(
        list_admin_guestbook(
            session=session,
            page=page,
            page_size=page_size,
            status=status,
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
    "display_options": AdminCrudTarget(
        model=PageDisplayOption,
        create_schema=PageDisplayOptionCreate,
        update_schema=PageDisplayOptionUpdate,
        read_schema=PageDisplayOptionAdminRead,
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
    "resume_skills": AdminCrudTarget(
        model=ResumeSkillGroup,
        create_schema=ResumeSkillGroupCreate,
        update_schema=ResumeSkillGroupUpdate,
        read_schema=ResumeSkillGroupAdminRead,
        base_query_factory=lambda session: resume_scoped_query(session, ResumeSkillGroup),
        prepare_create_data=attach_resume_basics_id,
    ),
    "resume_experiences": AdminCrudTarget(
        model=ResumeExperience,
        create_schema=ResumeExperienceCreate,
        update_schema=ResumeExperienceUpdate,
        read_schema=ResumeExperienceAdminRead,
        base_query_factory=lambda session: resume_scoped_query(session, ResumeExperience),
        prepare_create_data=attach_resume_basics_id,
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
