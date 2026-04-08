from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def shanghai_now() -> datetime:
    return datetime.now(BEIJING_TZ)


def normalize_shanghai_datetime(value: datetime) -> datetime:
    return value.astimezone(BEIJING_TZ) if value.tzinfo else value.replace(tzinfo=BEIJING_TZ)


def to_beijing_datetime(value: datetime) -> datetime:
    return normalize_shanghai_datetime(value)


def format_beijing_iso_datetime(value: datetime) -> str:
    return to_beijing_datetime(value).isoformat()


def beijing_today() -> date:
    return shanghai_now().date()


def beijing_date(value: datetime) -> date:
    return to_beijing_datetime(value).date()


def beijing_day_bounds(value: date) -> tuple[datetime, datetime]:
    start = datetime.combine(value, time.min, tzinfo=BEIJING_TZ)
    end = datetime.combine(value + timedelta(days=1), time.min, tzinfo=BEIJING_TZ)
    return start, end
