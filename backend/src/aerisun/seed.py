from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aerisun.db import get_session_factory, init_db
from aerisun.models import (
    DiaryEntry,
    ExcerptEntry,
    PageCopy,
    PageDisplayOption,
    Poem,
    PostEntry,
    ResumeBasics,
    ResumeExperience,
    ResumeSkillGroup,
    SiteProfile,
    SocialLink,
    ThoughtEntry,
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

DEFAULT_POSTS = [
    {
        "slug": "from-zero-design-system",
        "title": "从零搭建个人设计系统的完整思路",
        "summary": "设计系统不只是组件库，它更像是一套把视觉秩序、协作方式与交付节奏串起来的语言。",
        "body": "设计系统真正有价值的部分，不在于组件数量，而在于它有没有把视觉层级、状态表达和内容节奏说清楚。对个人站来说，它同样可以帮助我把页面气质、动效速度和排版密度保持在同一条线上。",
        "tags": ["design-system", "frontend"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 21, 9, 0, tzinfo=UTC),
    },
    {
        "slug": "liquid-glass-css-notes",
        "title": "液态玻璃效果的 CSS 实现与优化",
        "summary": "从 blur、边框高光到暗色模式折射，这篇文章记录了 Liquid Glass 在 Web 上的取舍。",
        "body": "我把 Liquid Glass 拆成了三层：基础材质、边缘高光和运动反馈。亮色模式更像磨砂玻璃，暗色模式则更依赖 blur 与边框亮度的平衡。真正的难点不是写出效果，而是让它在不同页面里保持克制。",
        "tags": ["css", "glass", "performance"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 18, 20, 30, tzinfo=UTC),
    },
    {
        "slug": "why-i-choose-indie-design",
        "title": "为什么我选择做独立设计师",
        "summary": "独立不只是工作方式变化，它会同时改变你看待时间、责任和表达的角度。",
        "body": "离开团队之后，我最先感受到的不是自由，而是所有决定都必须由自己承担。也是在这个过程中，我开始更认真地处理个人表达、项目边界和长期维护成本。网站本身也是这个思路的一部分。",
        "tags": ["essay", "career"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 14, 8, 15, tzinfo=UTC),
    },
]

DEFAULT_DIARY_ENTRIES = [
    {
        "slug": "spring-equinox-and-warm-light",
        "title": "春分，天气转暖",
        "summary": "阳光从窗帘缝隙里漏进来，整个房间都有一点松动感。",
        "body": "今天把博客首页重新整理了一遍，花了一上午调 Hero 的呼吸感和玻璃层次。下午去咖啡店坐了两个小时，回来的路上看到树上的花苞终于鼓起来了，春天像是在慢慢试探地靠近。",
        "tags": ["life", "spring"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 21, 12, 0, tzinfo=UTC),
    },
    {
        "slug": "rain-day-and-lofi",
        "title": "下雨的一天",
        "summary": "雨声和 lo-fi 混在一起的时候，写代码的节奏会变得很稳。",
        "body": "今天没有出门，把友链页的假数据重新梳理了一次，也顺手重排了页面间距。中午只简单煮了碗面，下午继续修动效节奏。一个人在雨天里工作，意外地不觉得孤单。",
        "tags": ["rain", "worklog"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 19, 14, 45, tzinfo=UTC),
    },
    {
        "slug": "windy-library-day",
        "title": "风大的图书馆日",
        "summary": "出门时几乎被风推着走，回来时手里多了两本书和一杯热可可。",
        "body": "今天去图书馆归还了上周借的书，又带回两本关于字体与写作的作品。回来的路上一直在想，网站里的排版为什么总能透露出作者的节奏感。或许页面其实也是一种书写。",
        "tags": ["library", "reading"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 17, 18, 10, tzinfo=UTC),
    },
]

DEFAULT_THOUGHTS = [
    {
        "slug": "spacing-rhythm-note",
        "title": "排版节奏的一点记录",
        "summary": "今天只是把字距从 -0.02em 调到 -0.03em，页面气质就完全不一样了。",
        "body": "设计里最迷人的地方，是那些看似只差一点点、实际却会改变整段阅读呼吸感的细节。",
        "tags": ["design", "typography"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 21, 15, 5, tzinfo=UTC),
    },
    {
        "slug": "less-but-better-note",
        "title": "少即是多，还是少但更好",
        "summary": "删掉一个不必要的层级，往往比再加一个漂亮组件更难。",
        "body": "最近越来越确信，前端不该一味堆视觉效果。真正重要的是信息的显隐、节奏的松紧，还有用户什么时候该被提醒、什么时候该被放过。",
        "tags": ["product", "reflection"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 20, 10, 20, tzinfo=UTC),
    },
    {
        "slug": "frontend-as-craft",
        "title": "前端有点像手工活",
        "summary": "都是把零散的东西拼成一个完整且可用的整体。",
        "body": "越做越觉得前端和手工很像。你得在结构、材料、手感和最终呈现之间来回试，才能找到一个刚刚好的平衡点。",
        "tags": ["frontend", "craft"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 16, 9, 35, tzinfo=UTC),
    },
]

DEFAULT_EXCERPTS = [
    {
        "slug": "harmony-in-blank-space",
        "title": "关于留白的节选",
        "summary": "留白不是空，而是给观看者留下参与意义生成的空间。",
        "body": "最好的设计往往不是把每一个角落都填满，而是知道在哪里停下来。那个停顿本身，会让画面从有限延伸到无限。",
        "tags": ["reading", "aesthetics"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 17, 8, 0, tzinfo=UTC),
    },
    {
        "slug": "good-design-note",
        "title": "少，但更好",
        "summary": "不是少做东西，而是把非必要部分真正拿掉。",
        "body": "当一个界面去掉多余装饰之后，剩下的层级、边界和节奏都会被放大。所以极简不是偷懒，而是把判断压力提前放回设计者自己身上。",
        "tags": ["reading", "minimalism"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 15, 11, 30, tzinfo=UTC),
    },
    {
        "slug": "repeat-has-power",
        "title": "重复本身的力量",
        "summary": "真正改变人的，通常不是瞬间爆发，而是长期重复。",
        "body": "写作、设计、编程这些事，其实都依赖节律。你不断重复某种动作，慢慢就会在里面长出属于自己的结构和判断。",
        "tags": ["writing", "habits"],
        "status": "published",
        "visibility": "public",
        "published_at": datetime(2026, 3, 12, 19, 45, tzinfo=UTC),
    },
]


def _is_empty(session: Session, model) -> bool:  # type: ignore[no-untyped-def]
    return session.scalar(select(func.count(model.id))) == 0


def _seed_content_entries(session: Session, model, entries: list[dict]) -> None:  # type: ignore[no-untyped-def]
    if not _is_empty(session, model):
        return
    session.add_all([model(**entry) for entry in entries])


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
        else:
            session.rollback()

        _seed_content_entries(session, PostEntry, DEFAULT_POSTS)
        _seed_content_entries(session, DiaryEntry, DEFAULT_DIARY_ENTRIES)
        _seed_content_entries(session, ThoughtEntry, DEFAULT_THOUGHTS)
        _seed_content_entries(session, ExcerptEntry, DEFAULT_EXCERPTS)
        session.commit()
    finally:
        session.close()


def main() -> None:
    seed_reference_data()


if __name__ == "__main__":
    main()
