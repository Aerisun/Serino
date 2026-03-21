from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aerisun.modules.site_config.models import (
    PageCopy,
    PageDisplayOption,
    Poem,
    ResumeBasic,
    ResumeExperience,
    ResumeSkill,
    SiteProfile,
    SocialLink,
)

DEFAULT_SITE_PROFILE = {
    "slug": "default",
    "name": "Felix",
    "title": "Felix · 个人网站",
    "description": "Felix 的个人网站，收纳网页设计、前端、写作与生活记录。",
    "author": "Felix",
    "role": "UI/UX Designer · Frontend Developer",
    "bio": "我做网页设计，也写前端，把视觉、节奏、内容和交互整理成一个自然流动的个人空间。",
    "og_image": "/images/hero_bg.jpeg",
    "footer_text": "用 ♥ 与代码构建",
}

DEFAULT_SOCIAL_LINKS = [
    {"label": "GitHub", "href": "https://github.com", "icon_key": "github", "placements": ["hero", "footer"], "sort_order": 1},
    {"label": "Telegram", "href": "https://t.me", "icon_key": "telegram", "placements": ["hero", "footer"], "sort_order": 2},
    {"label": "X", "href": "https://x.com", "icon_key": "x", "placements": ["hero", "footer"], "sort_order": 3},
    {"label": "网易云音乐", "href": "https://music.163.com", "icon_key": "netease-music", "placements": ["hero"], "sort_order": 4},
]

DEFAULT_POEMS = [
    "山有木兮木有枝，心悦君兮君不知。",
    "人生若只如初见，何事秋风悲画扇。",
    "曾经沧海难为水，除却巫山不是云。",
    "落霞与孤鹜齐飞，秋水共长天一色。",
    "行到水穷处，坐看云起时。",
    "采菊东篱下，悠然见南山。",
    "大漠孤烟直，长河落日圆。",
    "海内存知己，天涯若比邻。",
    "长风破浪会有时，直挂云帆济沧海。",
    "但愿人长久，千里共婵娟。",
    "世事一场大梦，人生几度秋凉。",
    "浮生若梦，为欢几何。",
]

DEFAULT_PAGE_COPIES = {
    "posts": {
        "eyebrow": "Journal",
        "title": "Posts",
        "subtitle": "文章、设计笔记与前端思考，按主题和节奏慢慢展开。",
        "description": "Felix 的文章列表，收纳设计、前端与个人写作。",
        "meta_description": "Felix 的文章列表，收纳设计、前端与个人写作。",
        "search_placeholder": "搜索文章...",
        "empty_message": "没有找到匹配的文章",
        "all_label": "全部",
    },
    "diary": {
        "eyebrow": "Diary",
        "title": "日记",
        "subtitle": "每天一点点，记录生活的温度，也记录节奏如何从一天里慢慢长出来。",
        "description": "Felix 的日记列表，记录天气、心情与每天的生活片段。",
        "meta_description": "Felix 的日记列表，记录天气、心情与每天的生活片段。",
    },
    "friends": {
        "eyebrow": "Circle",
        "title": "朋友们",
        "subtitle": "海内存知己，天涯若比邻。把常看的小站和最近的回响轻轻放在一起。",
        "description": "Felix 的友链与朋友圈，收纳常去的小站与最近更新。",
        "meta_description": "Felix 的友链与朋友圈，收纳常去的小站与最近更新。",
        "circle_title": "Friend Circle",
    },
    "excerpts": {
        "eyebrow": "Reading Room",
        "title": "文摘",
        "subtitle": "摘录那些让我停下来想一想的文字，留一段回声，也留一点空白。",
        "description": "Felix 的文摘收藏，记录设计、美学与生活阅读中的片段。",
        "meta_description": "Felix 的文摘收藏，记录设计、美学与生活阅读中的片段。",
    },
    "thoughts": {
        "eyebrow": "Dispatches",
        "title": "碎碎念",
        "subtitle": "短句、片段、当下感受，像是从工作和生活里捞出来的一些微光。",
        "description": "Felix 的碎碎念时间线，记录设计、生活与日常想法。",
        "meta_description": "Felix 的碎碎念时间线，记录设计、生活与日常想法。",
    },
    "guestbook": {
        "eyebrow": "Guestbook",
        "title": "留言板",
        "subtitle": "留下一点话语和气味，让这座个人站不只是独白，也有你来过的痕迹。",
        "description": "Felix 的留言板，欢迎留下你的足迹与想法。",
        "meta_description": "Felix 的留言板，欢迎留下你的足迹与想法。",
    },
    "resume": {
        "eyebrow": "Profile",
        "title": "Felix",
        "subtitle": "网页设计与前端开发并行，关注视觉秩序、动效节奏与内容呈现的精度。",
        "description": "Felix 的个人简历，包含设计、前端与工作经历。",
        "meta_description": "Felix 的个人简历，包含设计、前端与工作经历。",
        "download_label": "下载 PDF",
    },
    "calendar": {
        "eyebrow": "Calendar",
        "title": "日历",
        "subtitle": "把帖子、日记和文摘按日期铺开，回看最近一段时间的节奏变化。",
        "description": "Felix 的内容日历，按日期浏览帖子、日记与文摘。",
        "meta_description": "Felix 的内容日历，按日期浏览帖子、日记与文摘。",
    },
}

DEFAULT_DISPLAY_OPTIONS = {
    "posts": {"width": "content", "show_search": True, "show_filters": True},
    "diary": {"width": "narrow", "show_search": False, "show_filters": False},
    "friends": {"width": "wide", "page_size": 10, "show_search": False, "show_filters": False},
    "excerpts": {"width": "content", "show_search": False, "show_filters": False},
    "thoughts": {"width": "narrow", "show_search": False, "show_filters": False},
    "guestbook": {"width": "narrow", "show_search": False, "show_filters": False},
    "resume": {"width": "content", "show_search": False, "show_filters": False},
    "calendar": {"width": "wide", "show_search": False, "show_filters": False},
}

DEFAULT_RESUME_BASIC = {
    "name": "Felix",
    "title": "Felix",
    "subtitle": "UI/UX Designer · Frontend Developer",
    "description": "网页设计与前端开发并行，关注视觉秩序、动效节奏与内容呈现的精度。",
    "meta_title": "简历",
    "meta_description": "Felix 的个人简历，包含设计、前端与工作经历。",
    "download_label": "下载 PDF",
}

DEFAULT_RESUME_SKILLS = [
    "React",
    "TypeScript",
    "Tailwind CSS",
    "Figma",
    "Framer Motion",
    "Next.js",
    "Vue",
    "Design Systems",
    "Responsive Design",
    "SVG/Canvas",
    "Git",
    "Node.js",
]

DEFAULT_RESUME_EXPERIENCES = [
    {
        "role": "独立设计师 & 前端开发",
        "organization": "Freelance",
        "period": "2024 — 至今",
        "description": "为多个品牌和创业团队提供从视觉设计到前端落地的全流程服务，专注个人品牌网站和产品界面设计。",
        "sort_order": 1,
    },
    {
        "role": "前端开发工程师",
        "organization": "某科技公司",
        "period": "2022 — 2024",
        "description": "负责核心产品的前端架构和设计系统搭建，主导了暗色模式适配和动效体系的建立。",
        "sort_order": 2,
    },
    {
        "role": "UI/UX 设计实习",
        "organization": "某设计工作室",
        "period": "2021 — 2022",
        "description": "参与多个 B 端产品的界面设计，学习了从用户调研到交付的完整设计流程。",
        "sort_order": 3,
    },
    {
        "role": "数字媒体艺术",
        "organization": "某大学",
        "period": "2018 — 2022",
        "description": "系统学习了视觉传达、交互设计和前端开发，毕业设计获院级优秀作品。",
        "sort_order": 4,
    },
]


def _table_count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def seed_database(session: Session) -> None:
    if _table_count(session, SiteProfile) > 0:
        return

    profile = SiteProfile(**DEFAULT_SITE_PROFILE)
    session.add(profile)
    session.flush()

    session.add_all(
        SocialLink(site_profile_id=profile.id, **link)
        for link in DEFAULT_SOCIAL_LINKS
    )
    session.add_all(
        Poem(site_profile_id=profile.id, text=poem, sort_order=index)
        for index, poem in enumerate(DEFAULT_POEMS, start=1)
    )

    session.add_all(
        PageCopy(site_profile_id=profile.id, page_key=page_key, **payload)
        for page_key, payload in DEFAULT_PAGE_COPIES.items()
    )
    session.add_all(
        PageDisplayOption(site_profile_id=profile.id, page_key=page_key, **payload)
        for page_key, payload in DEFAULT_DISPLAY_OPTIONS.items()
    )

    resume_basic = ResumeBasic(site_profile_id=profile.id, **DEFAULT_RESUME_BASIC)
    session.add(resume_basic)
    session.add_all(
        ResumeSkill(site_profile_id=profile.id, name=skill, sort_order=index)
        for index, skill in enumerate(DEFAULT_RESUME_SKILLS, start=1)
    )
    session.add_all(
        ResumeExperience(site_profile_id=profile.id, **item)
        for item in DEFAULT_RESUME_EXPERIENCES
    )

