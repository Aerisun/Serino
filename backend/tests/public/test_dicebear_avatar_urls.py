from aerisun.domain.activity.service import _avatar_for_name as activity_avatar_for_name
from aerisun.domain.engagement.service import DEFAULT_COMMENT_AVATAR_PRESETS, _avatar_url_for_seed
from aerisun.domain.site_auth.profile import DICEBEAR_NOTIONISTS_BASE_URL, avatar_url_for_seed

LOCAL_NOTIONISTS_AVATAR_BASE_URL = "/api/v1/avatars/10.x/notionists/svg"


def test_site_auth_avatar_urls_use_local_notionists_avatar_endpoint() -> None:
    assert DICEBEAR_NOTIONISTS_BASE_URL == LOCAL_NOTIONISTS_AVATAR_BASE_URL
    assert avatar_url_for_seed("55fc3d39") == f"{LOCAL_NOTIONISTS_AVATAR_BASE_URL}?seed=55fc3d39"


def test_engagement_avatar_urls_use_local_notionists_avatar_endpoint() -> None:
    assert _avatar_url_for_seed("name with spaces") == f"{LOCAL_NOTIONISTS_AVATAR_BASE_URL}?seed=name%20with%20spaces"
    assert all(
        preset["avatar_url"].startswith(f"{LOCAL_NOTIONISTS_AVATAR_BASE_URL}?seed=")
        for preset in DEFAULT_COMMENT_AVATAR_PRESETS
    )


def test_activity_avatar_urls_use_local_notionists_avatar_endpoint() -> None:
    assert activity_avatar_for_name("visitor") == f"{LOCAL_NOTIONISTS_AVATAR_BASE_URL}?seed=visitor"
