from __future__ import annotations


def test_read_pages_returns_seeded_page_copy(client) -> None:
    response = client.get("/api/v1/public/pages")

    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload["items"], list)

    items = {item["page_key"]: item for item in payload["items"]}
    assert items["activity"]["title"] == "友邻与最近动态"
    assert items["activity"]["extras"]["dashboardLabel"] == "Dashboard"
    assert items["notFound"]["title"] == "这个页面没有留下来"
    assert items["notFound"]["extras"]["metaTitle"] == "页面未找到"
    assert items["posts"]["title"] == "Posts"
    assert items["friends"]["page_size"] == 10
    assert items["friends"]["extras"]["statusLabel"] == "状态"
    assert items["guestbook"]["extras"]["namePlaceholder"] == "你的名字"
    assert items["guestbook"]["extras"]["submitLabel"] == "提交留言"
    assert items["friends"]["extras"]["loadingLabel"] == "正在加载..."
    assert items["friends"]["extras"]["loadMoreLabel"] == "加载更多"
    assert items["friends"]["extras"]["retryLabel"] == "重试加载"
    assert items["guestbook"]["extras"]["submittingLabel"] == "提交留言"
    assert items["calendar"]["extras"]["weekdayLabels"][0] == "周一"
    assert items["calendar"]["extras"]["loadingLabel"] == "正在加载日历"
    assert items["excerpts"]["extras"]["modalCloseLabel"] == "关闭"
    assert items["resume"]["download_label"] == "下载 PDF"
    assert "enabled" in items["posts"]


def test_public_content_includes_presentation_fields(client) -> None:
    posts = client.get("/api/v1/public/posts").json()["items"]
    diary = client.get("/api/v1/public/diary").json()["items"]
    thoughts = client.get("/api/v1/public/thoughts").json()["items"]
    excerpts = client.get("/api/v1/public/excerpts").json()["items"]

    posts_by_slug = {item["slug"]: item for item in posts}
    diary_by_slug = {item["slug"]: item for item in diary}
    thoughts_by_slug = {item["slug"]: item for item in thoughts}
    excerpts_by_slug = {item["slug"]: item for item in excerpts}

    assert posts_by_slug["from-zero-design-system"]["category"] == "设计"
    assert posts_by_slug["from-zero-design-system"]["read_time"] == "1 分钟"
    assert (
        posts_by_slug["from-zero-design-system"]["display_date"] == "2026 年 3 月 21 日"
    )
    assert posts_by_slug["from-zero-design-system"]["relative_date"]
    assert posts_by_slug["from-zero-design-system"]["view_count"] == 1247
    assert posts_by_slug["from-zero-design-system"]["comment_count"] == 2
    assert posts_by_slug["from-zero-design-system"]["like_count"] >= 1
    assert posts_by_slug["liquid-glass-css-notes"]["comment_count"] == 1

    assert diary_by_slug["spring-equinox-and-warm-light"]["weather"] == "sunny"
    assert diary_by_slug["spring-equinox-and-warm-light"]["mood"] == "☀️"
    assert "春风如贵客" in diary_by_slug["spring-equinox-and-warm-light"]["poem"]
    assert diary_by_slug["spring-equinox-and-warm-light"]["comment_count"] == 1

    assert thoughts_by_slug["spacing-rhythm-note"]["mood"] == "🎨"
    assert thoughts_by_slug["spacing-rhythm-note"]["repost_count"] == 0
    assert (
        thoughts_by_slug["spacing-rhythm-note"]["display_date"] == "2026 年 3 月 21 日"
    )

    assert excerpts_by_slug["good-design-note"]["author"] == "Dieter Rams"
    assert excerpts_by_slug["good-design-note"]["source"] == "Less but Better"
    assert len(posts) >= 8
    assert len(diary) >= 7
    assert len(thoughts) >= 8
    assert len(excerpts) >= 7
