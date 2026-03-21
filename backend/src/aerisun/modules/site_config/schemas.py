from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SocialLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    href: str
    icon_key: str
    placements: list[str]


class PoemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    text: str
    source: str | None = None


class SiteProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    title: str
    description: str
    author: str
    role: str
    bio: str
    og_image: str
    footer_text: str


class SiteRead(BaseModel):
    profile: SiteProfileRead
    social_links: list[SocialLinkRead]
    poems: list[PoemRead]


class PageConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    eyebrow: str | None = None
    title: str
    subtitle: str | None = None
    description: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    width: str
    search_placeholder: str | None = None
    empty_message: str | None = None
    all_label: str | None = None
    circle_title: str | None = None
    page_size: int | None = None
    download_label: str | None = None


class PagesRead(BaseModel):
    posts: PageConfigRead
    diary: PageConfigRead
    friends: PageConfigRead
    excerpts: PageConfigRead
    thoughts: PageConfigRead
    guestbook: PageConfigRead
    resume: PageConfigRead
    calendar: PageConfigRead


class ResumeSkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str


class ResumeExperienceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    organization: str
    period: str
    description: str


class ResumeProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    title: str
    subtitle: str
    description: str
    meta_title: str | None = None
    meta_description: str | None = None
    download_label: str


class ResumeRead(BaseModel):
    profile: ResumeProfileRead
    skills: list[ResumeSkillRead]
    experiences: list[ResumeExperienceRead]

