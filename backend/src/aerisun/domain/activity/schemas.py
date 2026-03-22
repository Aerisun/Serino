from __future__ import annotations

from datetime import datetime

from aerisun.core.schemas import ModelBase


class CalendarEventRead(ModelBase):
    date: str
    type: str
    title: str
    slug: str
    href: str


class CalendarRead(ModelBase):
    range_start: str
    range_end: str
    events: list[CalendarEventRead]


class RecentActivityItemRead(ModelBase):
    kind: str
    actor_name: str
    actor_avatar: str
    target_title: str
    excerpt: str | None
    created_at: datetime
    href: str


class RecentActivityRead(ModelBase):
    items: list[RecentActivityItemRead]


class ActivityHeatmapStatsRead(ModelBase):
    total_contributions: int
    peak_week: int
    average_per_week: int


class ActivityHeatmapWeekRead(ModelBase):
    week_start: str
    total: int
    days: list[int]
    month_label: str
    label: str


class ActivityHeatmapRead(ModelBase):
    stats: ActivityHeatmapStatsRead
    weeks: list[ActivityHeatmapWeekRead]
