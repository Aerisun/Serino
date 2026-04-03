from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def normalize_utc_datetime(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def to_beijing_datetime(value: datetime) -> datetime:
    return normalize_utc_datetime(value).astimezone(BEIJING_TZ)


def beijing_today() -> date:
    return datetime.now(BEIJING_TZ).date()


def beijing_date(value: datetime) -> date:
    return to_beijing_datetime(value).date()


def beijing_day_bounds(value: date) -> tuple[datetime, datetime]:
    start = datetime.combine(value, time.min, tzinfo=BEIJING_TZ).astimezone(UTC)
    end = datetime.combine(value + timedelta(days=1), time.min, tzinfo=BEIJING_TZ).astimezone(UTC)
    return start, end
