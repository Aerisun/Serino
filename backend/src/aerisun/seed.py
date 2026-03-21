from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aerisun.db import get_session_factory, init_db
from aerisun.models import (
    PageCopy,
    PageDisplayOption,
    Poem,
    ResumeBasics,
    ResumeExperience,
    ResumeSkillGroup,
    SiteProfile,
    SocialLink,
)


DEFAULT_SITE_PROFILE = {
    "name": "Felix",
    "title": "Aerisun",
    "bio": "我做网页设计，也写前端，把视觉、节奏、内容和交互整理成一个自然流动的个人空间。",
    "role": "UI/UX Designer · Frontend Developer",
    "footer_text": "Aerisun · Built with care and a small stack.",
}

DEFAULT_SOCIAL_LINKS = [
    {"name": "GitHub", "href": "https://github.com/", "icon_key": "github", "placement": "hero", "order_index": 0},
    {"name": "Telegram", "href": "https://t.me/", "icon_key": "telegram", "placement": "hero", "order_index": 1},
    {"name": "X", "href": "https://x.com/", "icon_key": "x", "placement": "hero", "order_index": 2},
    {"name": "网易云", "href": "https://music.163.com/", "icon_key": "netease", "placement": "footer", "order_index": 3},
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
    {"page_key": "posts", "label": "Blog", "title": "Posts", "subtitle": "整理过的想法与实践记录。", "description": "文章列表与文章详情页文案。", "search_placeholder": "搜索文章...", "empty_message": "没有找到匹配的文章", "max_width": "max-w-3xl", "page_size": None, "download_label": None, "extras": {"category_all_label": "全部"}},
    {"page_key": "diary", "label": None, "title": "日记", "subtitle": "每天一点点，记录生活的温度。", "description": "日记页文案。", "search_placeholder": None, "empty_message": "今天还没有新的日记", "max_width": "max-w-2xl", "page_size": None, "download_label": None, "extras": {}},
    {"page_key": "friends", "label": None, "title": "朋友们", "subtitle": "海内存知己，天涯若比邻。", "description": "友链与 Friend Circle 页面文案。", "search_placeholder": None, "empty_message": "暂时没有友链内容", "max_width": "max-w-4xl", "page_size": 10, "download_label": None, "extras": {"circle_title": "Friend Circle"}},
    {"page_key": "excerpts", "label": None, "title": "文摘", "subtitle": "摘录那些让我停下来想一想的文字。", "description": "文摘页文案。", "search_placeholder": None, "empty_message": "还没有整理好的文摘", "max_width": "max-w-3xl", "page_size": None, "download_label": None, "extras": {}},
    {"page_key": "thoughts", "label": None, "title": "碎碎念", "subtitle": "一些不成文的想法，随手记下的片段。", "description": "碎碎念页文案。", "search_placeholder": None, "empty_message": "最近没有新的碎碎念", "max_width": "max-w-2xl", "page_size": None, "download_label": None, "extras": {}},
    {"page_key": "guestbook", "label": None, "title": "留言板", "subtitle": "留下你的足迹，说点什么吧。", "description": "留言板页文案。", "search_placeholder": None, "empty_message": "还没有人留言", "max_width": "max-w-2xl", "page_size": None, "download_label": None, "extras": {}},
    {"page_key": "resume", "label": None, "title": "Felix", "subtitle": "UI/UX Designer · Frontend Developer", "description": "简历页配置。", "search_placeholder": None, "empty_message": None, "max_width": "max-w-3xl", "page_size": None, "download_label": "下载 PDF", "extras": {}},
    {"page_key": "calendar", "label": None, "title": "日历", "subtitle": "记录每一天的痕迹。", "description": "日历与活动投影页面文案。", "search_placeholder": None, "empty_message": "日历里还没有内容", "max_width": "max-w-4xl", "page_size": None, "download_label": None, "extras": {}},
]

DEFAULT_PAGE_OPTIONS = [
    {"page_key": "posts", "is_enabled": True, "settings": {"show_search": True}},
    {"page_key": "diary", "is_enabled": True, "settings": {}},
    {"page_key": "friends", "is_enabled": True, "settings": {"circle_page_size": 10}},
    {"page_key": "excerpts", "is_enabled": True, "settings": {}},
    {"page_key": "thoughts", "is_enabled": True, "settings": {}},
    {"page_key": "guestbook", "is_enabled": True, "settings": {}},
    {"page_key": "resume", "is_enabled": True, "settings": {"show_download": True}},
    {"page_key": "calendar", "is_enabled": True, "settings": {}},
]

DEFAULT_RESUME = {
    "title": "Felix",
    "subtitle": "UI/UX Designer · Frontend Developer",
    "summary": "专注把视觉、节奏和交互组织成清晰、克制、可维护的产品体验。",
    "download_label": "下载 PDF",
}

DEFAULT_SKILLS = [
    {"category": "Frontend", "items": ["React", "TypeScript", "Vite", "Tailwind CSS"], "order_index": 0},
    {"category": "Design", "items": ["UI 系统", "Glassmorphism", "Motion Design", "Information Architecture"], "order_index": 1},
    {"category": "Backend", "items": ["FastAPI", "SQLAlchemy", "SQLite", "Docker"], "order_index": 2},
]

DEFAULT_EXPERIENCES = [
    {
        "title": "个人网站与设计系统",
        "company": "Aerisun",
        "period": "2024 - Now",
        "summary": "构建个人网站、设计令牌和可恢复的内容平台。",
        "order_index": 0,
    },
    {
        "title": "前端与视觉实现",
        "company": "Independent",
        "period": "2022 - 2024",
        "summary": "负责个人项目中的页面节奏、动效和交互组织。",
        "order_index": 1,
    },
]


def _is_empty(session: Session, model) -> bool:  # type: ignore[no-untyped-def]
    return session.scalar(select(func.count(model.id))) == 0


def seed_reference_data() -> None:
    init_db()
    session = get_session_factory()()
    try:
        if _is_empty(session, SiteProfile):
            site = SiteProfile(**DEFAULT_SITE_PROFILE)
            session.add(site)
            session.flush()

            session.add_all(
                [SocialLink(site_profile_id=site.id, **item) for item in DEFAULT_SOCIAL_LINKS]
            )
            session.add_all(
                [Poem(site_profile_id=site.id, order_index=index, content=text) for index, text in enumerate(DEFAULT_POEMS)]
            )
            session.add_all([PageCopy(**item) for item in DEFAULT_PAGE_COPIES])
            session.add_all([PageDisplayOption(**item) for item in DEFAULT_PAGE_OPTIONS])
            resume = ResumeBasics(**DEFAULT_RESUME)
            session.add(resume)
            session.flush()
            session.add_all(
                [ResumeSkillGroup(resume_basics_id=resume.id, **group) for group in DEFAULT_SKILLS]
            )
            session.add_all(
                [ResumeExperience(resume_basics_id=resume.id, **experience) for experience in DEFAULT_EXPERIENCES]
            )
            session.commit()
        else:
            session.rollback()
    finally:
        session.close()


def main() -> None:
    seed_reference_data()


if __name__ == "__main__":
    main()

