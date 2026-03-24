from __future__ import annotations

from datetime import datetime

from pydantic import Field

from aerisun.core.schemas import ModelBase


class CalendarEventRead(ModelBase):
    date: str = Field(description="Event date in YYYY-MM-DD format")
    type: str = Field(description="Event type: post, diary, thought, or excerpt")
    title: str = Field(description="Event title")
    slug: str = Field(description="Content slug")
    href: str = Field(description="Frontend URL path")


class CalendarRead(ModelBase):
    range_start: str = Field(description="Query range start date")
    range_end: str = Field(description="Query range end date")
    events: list[CalendarEventRead] = Field(description="List of calendar events")


class RecentActivityItemRead(ModelBase):
    kind: str = Field(description="Activity type: comment, guestbook, or reaction")
    actor_name: str = Field(description="Name of the person who performed the action")
    actor_avatar: str = Field(description="Actor avatar URL")
    target_title: str = Field(description="Title of the target content")
    excerpt: str | None = Field(description="Brief excerpt of the activity content")
    created_at: datetime = Field(description="Activity timestamp")
    href: str = Field(description="Frontend URL path to the related content")


class RecentActivityRead(ModelBase):
    items: list[RecentActivityItemRead] = Field(description="List of recent activity items")


class ActivityHeatmapStatsRead(ModelBase):
    total_contributions: int = Field(description="Total contributions in the period")
    peak_week: int = Field(description="Highest weekly contribution count")
    average_per_week: int = Field(description="Average contributions per week")


class ActivityHeatmapWeekRead(ModelBase):
    week_start: str = Field(description="Week start date in YYYY-MM-DD format")
    total: int = Field(description="Total contributions in this week")
    days: list[int] = Field(description="Daily contribution counts (7 values, Mon-Sun)")
    month_label: str = Field(description="Month label for display")
    label: str = Field(description="Week label for display")


class ActivityHeatmapRead(ModelBase):
    stats: ActivityHeatmapStatsRead = Field(description="Aggregate heatmap statistics")
    weeks: list[ActivityHeatmapWeekRead] = Field(description="Weekly contribution data")
