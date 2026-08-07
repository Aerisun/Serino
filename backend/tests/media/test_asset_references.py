from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import text

from aerisun.domain.content.models import DiaryEntry, PostEntry
from aerisun.domain.media.references import (
    ARTICLE_CATEGORY_PRIORITY,
    build_legacy_url_variants,
    classify_asset_usages,
    collect_registered_references,
    rewrite_json_value,
    rewrite_registered_references,
    rewrite_text,
    scan_unhandled_legacy_references,
)
from aerisun.domain.ops.models import ConfigRevision, VisitRecord
from aerisun.domain.site_config.models import SiteProfile, SocialLink
from aerisun.domain.social.models import Friend
from aerisun.domain.waline.service import (
    collect_waline_asset_references,
    connect_waline_db,
    rewrite_waline_asset_references,
)


def test_rewrite_text_replaces_registered_relative_and_absolute_urls_without_touching_prefix_collisions() -> None:
    old = "/media/internal/assets/markdown-image/abc.png"
    absolute = f"https://site.example{old}"
    new = "/media/assets/asset-id.png"
    value = (
        f"![markdown]({old}?width=800#hero)\n"
        f'<img src="{absolute}" srcset="{old} 1x, {old}?dpr=2 2x">\n'
        f".cover{{background-image:url('{old}')}}\n"
        f"中文标点也应替换：{old}。\n"
        f"不应替换：{old}.backup"
    )

    result = rewrite_text(value, {absolute: new, old: new})

    assert result.replacement_count == 6
    assert f"{new}?width=800#hero" in result.value
    assert f'src="{new}"' in result.value
    assert f'srcset="{new} 1x, {new}?dpr=2 2x"' in result.value
    assert f"url('{new}')" in result.value
    assert f"{new}。" in result.value
    assert f"{old}.backup" in result.value


def test_rewrite_json_value_recurses_without_changing_non_string_values() -> None:
    old = "/media/public/assets/site/cover.webp"
    new = "/media/assets/cover-id.webp"
    value = {
        "hero": old,
        "items": [{"src": f"{old}?small=1"}, 7, True, None],
        "unrelated": "unchanged",
    }

    result = rewrite_json_value(value, {old: new})

    assert result.replacement_count == 2
    assert result.value == {
        "hero": new,
        "items": [{"src": f"{new}?small=1"}, 7, True, None],
        "unrelated": "unchanged",
    }
    assert value["hero"] == old


def test_article_classification_uses_the_first_fixed_priority_but_retains_all_usages() -> None:
    usages = {"friends", "thought", "post", "diary"}

    classification = classify_asset_usages(usages)

    assert ARTICLE_CATEGORY_PRIORITY == ("post", "diary", "thought", "excerpt", "resume", "friends")
    assert classification.scope == "article"
    assert classification.category == "post"
    assert classification.usages == tuple(sorted(usages))


def test_classification_handles_system_visitor_and_unreferenced_assets() -> None:
    assert classify_asset_usages({"system:site-icon", "post"}).scope == "system"
    assert classify_asset_usages({"system:site-icon", "post"}).category == "site-icon"
    assert classify_asset_usages({"guestbook"}).model_dump() == {
        "scope": "visitor",
        "category": "guestbook",
        "usages": ("guestbook",),
    }
    assert classify_asset_usages(set()).model_dump() == {
        "scope": "user",
        "category": "general",
        "usages": (),
    }


def test_build_legacy_url_variants_includes_both_visibility_aliases_slug_and_site_urls() -> None:
    asset = SimpleNamespace(
        resource_key="internal/assets/hero-image/abc.webp",
        public_slug="avatar.webp",
    )

    variants = build_legacy_url_variants(
        asset,
        site_urls=("https://site.example/", "https://www.site.example"),
    )

    assert "/media/internal/assets/hero-image/abc.webp" in variants
    assert "/media/public/assets/hero-image/abc.webp" in variants
    assert "/media/avatar.webp" in variants
    assert "https://site.example/media/internal/assets/hero-image/abc.webp" in variants
    assert "https://www.site.example/media/public/assets/hero-image/abc.webp" in variants
    assert len(variants) == len(set(variants))


def test_collect_registered_references_retains_every_content_usage(seeded_session) -> None:
    old = "/media/internal/assets/markdown-image/shared.png"
    post = PostEntry(slug="reference-post", title="Post", body=f"![post]({old})", tags=[], visibility="public")
    diary = DiaryEntry(slug="reference-diary", title="Diary", body=f'<img src="{old}">', tags=[], visibility="public")
    seeded_session.add_all((post, diary))
    seeded_session.commit()

    references = collect_registered_references(seeded_session, {old: "asset-shared"})

    shared = [reference for reference in references if reference.asset_id == "asset-shared"]
    assert {(reference.table, reference.column, reference.row_id) for reference in shared} == {
        ("posts", "body", post.id),
        ("diary_entries", "body", diary.id),
    }
    classification = classify_asset_usages({reference.usage for reference in shared if reference.usage})
    assert classification.scope == "article"
    assert classification.category == "post"


def test_friend_avatar_is_rewritten_without_changing_asset_to_article_scope(seeded_session) -> None:
    old = "/media/internal/assets/general/friend-avatar.jpg"
    new = "/media/assets/asset-friend-avatar.jpg"
    friend = Friend(
        name="Friend",
        url="https://friend.example",
        avatar_url=old,
        description="Friend description",
    )
    seeded_session.add(friend)
    seeded_session.commit()

    references = collect_registered_references(seeded_session, {old: "asset-friend-avatar"})

    assert [(reference.table, reference.column, reference.row_id, reference.usage) for reference in references] == [
        ("friends", "avatar_url", friend.id, None)
    ]
    classification = classify_asset_usages({reference.usage for reference in references if reference.usage})
    assert classification.model_dump() == {
        "scope": "user",
        "category": "general",
        "usages": (),
    }
    assert rewrite_registered_references(seeded_session, {old: new}) == 1
    assert friend.avatar_url == new


def test_social_link_resource_is_rewritten_without_changing_asset_scope(seeded_session) -> None:
    old = "https://site.example/media/social-qr-code"
    new = "/media/assets/asset-social-qr-code.jpg"
    profile = seeded_session.query(SiteProfile).one()
    social_link = SocialLink(
        site_profile_id=profile.id,
        name="Social QR code",
        href=old,
        icon_key="message",
        placement="both",
    )
    seeded_session.add(social_link)
    seeded_session.commit()

    references = collect_registered_references(seeded_session, {old: "asset-social-qr-code"})

    assert [(reference.table, reference.column, reference.row_id, reference.usage) for reference in references] == [
        ("social_links", "href", social_link.id, None)
    ]
    classification = classify_asset_usages({reference.usage for reference in references if reference.usage})
    assert classification.model_dump() == {
        "scope": "user",
        "category": "general",
        "usages": (),
    }
    assert rewrite_registered_references(seeded_session, {old: new}) == 1
    assert social_link.href == new


def test_rewrite_registered_references_updates_text_and_json_without_committing(seeded_session) -> None:
    old = "/media/public/assets/site/cover.webp"
    new = "/media/assets/cover-id.webp"
    post = PostEntry(slug="rewrite-post", title="Post", body=f"cover: {old}?size=2", tags=[], visibility="public")
    revision = ConfigRevision(
        resource_key="site.profile",
        resource_label="站点资料",
        operation="update",
        resource_version="1",
        changed_fields=["hero_image_url"],
        before_snapshot={"hero_image_url": old},
        after_snapshot={"hero_image_url": f"{old}#after"},
        before_preview=None,
        after_preview=None,
        sensitive_fields=[],
    )
    seeded_session.add_all((post, revision))
    seeded_session.commit()

    count = rewrite_registered_references(seeded_session, {old: new})

    assert count == 3
    assert post.body == f"cover: {new}?size=2"
    assert revision.before_snapshot == {"hero_image_url": new}
    assert revision.after_snapshot == {"hero_image_url": f"{new}#after"}


def test_scan_ignores_historical_visit_referer_without_rewriting_it(seeded_session) -> None:
    old = "/media/public/assets/hero-image/historical.webp"
    record = VisitRecord(
        visited_at=datetime.now(UTC),
        path="/posts/example",
        ip_address="127.0.0.1",
        referer=f"https://site.example{old}",
        status_code=200,
        duration_ms=12,
        is_bot=False,
    )
    seeded_session.add(record)
    seeded_session.commit()

    unhandled = scan_unhandled_legacy_references(seeded_session, {old, f"https://site.example{old}"})

    assert unhandled == []
    assert record.referer == f"https://site.example{old}"


def test_scan_unhandled_legacy_references_reports_unknown_text_columns(seeded_session) -> None:
    old = "/media/internal/assets/unknown/orphan.png"
    seeded_session.execute(text("CREATE TABLE migration_unknown (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"))
    seeded_session.execute(
        text("INSERT INTO migration_unknown (id, payload) VALUES (:id, :payload)"),
        {"id": "unknown-row", "payload": f"unknown {old}"},
    )
    seeded_session.commit()

    unhandled = scan_unhandled_legacy_references(seeded_session, {old})

    assert [(item.table, item.column, item.row_id, item.matched_url) for item in unhandled] == [
        ("migration_unknown", "payload", "unknown-row", old)
    ]


def test_waline_reference_collection_and_rewrite_distinguish_guestbook_surface(tmp_path) -> None:
    waline_path = tmp_path / "waline.db"
    old = "/media/internal/assets/comment/comment.png"
    new = "/media/assets/comment-id.png"
    with connect_waline_db(waline_path) as connection:
        connection.execute(
            "INSERT INTO wl_comment (comment, url) VALUES (?, ?)",
            (f'<img src="{old}">', "/guestbook"),
        )
        connection.execute(
            "INSERT INTO wl_users (display_name, email, password, avatar) VALUES ('User', 'user@example.com', '', ?)",
            (old,),
        )

    references = collect_waline_asset_references(waline_path, {old: "asset-comment"})

    assert len(references) == 2
    assert {(reference.asset_id, reference.usage, reference.matched_url) for reference in references} == {
        ("asset-comment", "guestbook", old),
        ("asset-comment", "user-avatar", old),
    }

    assert rewrite_waline_asset_references(waline_path, {old: new}) == 2
    with connect_waline_db(waline_path) as connection:
        row = connection.execute("SELECT comment FROM wl_comment").fetchone()
        user = connection.execute("SELECT avatar FROM wl_users").fetchone()
    assert row is not None
    assert row["comment"] == f'<img src="{new}">'
    assert user is not None
    assert user["avatar"] == new
