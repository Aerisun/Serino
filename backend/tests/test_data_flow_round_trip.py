from __future__ import annotations

from fastapi.routing import APIRoute

from aerisun.api.admin import admin_router
from aerisun.api.admin.schemas import (
    ContentCreate,
    NavItemCreate,
    PageCopyUpdate,
    ResumeBasicsUpdate,
    ResumeSkillGroupCreate,
    SiteProfileUpdate,
    SocialLinkCreate,
)
from aerisun.api.public import read_page_copy, read_post, read_posts, read_resume, read_site_config
from aerisun.domain.content.models import PostEntry
from aerisun.domain.site_config.models import PageCopy, ResumeBasics, ResumeSkillGroup, SiteProfile


def _endpoint(path: str, method: str):
    for route in admin_router.routes:
        if isinstance(route, APIRoute) and route.path == path and method.upper() in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found: {method} {path}")


CREATE_NAV = _endpoint("/api/v1/admin/site-config/nav-items/", "POST")
CREATE_SOCIAL = _endpoint("/api/v1/admin/site-config/social-links/", "POST")
UPDATE_PAGE_COPY = _endpoint("/api/v1/admin/site-config/page-copy/{item_id}", "PUT")
UPDATE_RESUME_BASICS = _endpoint("/api/v1/admin/resume/basics/{item_id}", "PUT")
CREATE_RESUME_SKILL = _endpoint("/api/v1/admin/resume/skills/", "POST")
CREATE_POST = _endpoint("/api/v1/admin/posts/", "POST")


def test_admin_profile_update_flows_to_public_site(seeded_session, admin_user) -> None:
    from aerisun.api.admin.site_config import update_profile

    update_payload = SiteProfileUpdate(
        name="Flow Test",
        title="Updated Through Admin",
        bio="Profile changes should be visible to the public site.",
        footer_text="Round-trip footer",
    )

    update_profile(update_payload, _admin=admin_user, session=seeded_session)

    payload = read_site_config(session=seeded_session)
    profile = seeded_session.query(SiteProfile).first()
    assert profile is not None
    assert payload.site.name == update_payload.name
    assert payload.site.title == update_payload.title
    assert payload.site.bio == update_payload.bio
    assert payload.site.footer_text == update_payload.footer_text
    assert profile.title == update_payload.title
    assert profile.bio == update_payload.bio


def test_admin_can_create_nav_item_without_site_profile_id_and_public_site_reads_it(seeded_session, admin_user) -> None:
    created = CREATE_NAV(
        payload=NavItemCreate(
            label="Flow Nav",
            href="/flow-nav",
            page_key="flow-nav",
            trigger="none",
            order_index=99,
            is_enabled=True,
        ),
        _admin=admin_user,
        session=seeded_session,
    )

    payload = read_site_config(session=seeded_session)
    assert created.site_profile_id
    assert created.label == "Flow Nav"
    assert any(item.label == "Flow Nav" and item.href == "/flow-nav" for item in payload.navigation)


def test_admin_can_create_social_link_without_site_profile_id_and_public_site_reads_it(
    seeded_session, admin_user
) -> None:
    created = CREATE_SOCIAL(
        payload=SocialLinkCreate(
            name="Flow Link",
            href="https://flow.example.com",
            icon_key="github",
            placement="hero",
            order_index=88,
        ),
        _admin=admin_user,
        session=seeded_session,
    )

    payload = read_site_config(session=seeded_session)
    assert created.site_profile_id
    assert created.href == "https://flow.example.com"
    assert any(link.href == "https://flow.example.com" for link in payload.social_links)


def test_admin_resume_updates_flow_to_public_resume(seeded_session, admin_user) -> None:
    basics = seeded_session.query(ResumeBasics).first()
    assert basics is not None

    updated = UPDATE_RESUME_BASICS(
        item_id=basics.id,
        payload=ResumeBasicsUpdate(
            title="Round Trip Resume",
            subtitle="Admin -> API -> DB -> Public",
            summary="This summary was updated through the admin API.",
            download_label="下载最新 PDF",
        ),
        _admin=admin_user,
        session=seeded_session,
    )

    created_skill = CREATE_RESUME_SKILL(
        payload=ResumeSkillGroupCreate(
            category="Flow Skills",
            items=["FastAPI", "SQLite"],
            order_index=99,
        ),
        _admin=admin_user,
        session=seeded_session,
    )

    payload = read_resume(session=seeded_session)
    skill = seeded_session.query(ResumeSkillGroup).filter(ResumeSkillGroup.id == created_skill.id).first()
    assert skill is not None
    assert updated.title == "Round Trip Resume"
    assert payload.title == "Round Trip Resume"
    assert payload.subtitle == "Admin -> API -> DB -> Public"
    assert payload.summary == "This summary was updated through the admin API."
    assert payload.download_label == "下载最新 PDF"
    assert created_skill.resume_basics_id
    assert any(group.category == "Flow Skills" for group in payload.skill_groups)


def test_admin_page_copy_and_published_post_flow_to_public_reads(seeded_session, admin_user) -> None:
    posts_copy = seeded_session.query(PageCopy).filter(PageCopy.page_key == "posts").first()
    assert posts_copy is not None

    updated_copy = UPDATE_PAGE_COPY(
        item_id=posts_copy.id,
        payload=PageCopyUpdate(page_size=7),
        _admin=admin_user,
        session=seeded_session,
    )

    created_post = CREATE_POST(
        payload=ContentCreate(
            slug="admin-public-round-trip",
            title="Admin/Public Round Trip",
            summary="Created in admin and read by the public API.",
            body="This published post should be visible to the public content endpoints.",
            tags=["integration", "round-trip"],
            status="published",
            visibility="public",
        ),
        _admin=admin_user,
        session=seeded_session,
    )

    pages = read_page_copy(session=seeded_session)
    detail = read_post("admin-public-round-trip", session=seeded_session)
    listing = read_posts(limit=20, offset=0, session=seeded_session)
    post_row = seeded_session.query(PostEntry).filter(PostEntry.slug == "admin-public-round-trip").first()

    assert updated_copy.page_size == 7
    assert any(item.page_key == "posts" and item.page_size == 7 for item in pages.items)
    assert created_post.status == "published"
    assert post_row is not None
    assert detail.title == "Admin/Public Round Trip"
    assert detail.summary == "Created in admin and read by the public API."
    assert any(item.slug == "admin-public-round-trip" for item in listing.items)
