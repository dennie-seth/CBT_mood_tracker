from __future__ import annotations

from datetime import date, datetime, timedelta

import pytz


def now_in_tz(tz_name: str) -> datetime:
    return datetime.now(tz=pytz.timezone(tz_name))


def today_in_tz(tz_name: str) -> date:
    return now_in_tz(tz_name).date()


def to_user_date(dt: datetime, tz_name: str) -> date:
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(pytz.timezone(tz_name)).date()


def parse_period(period: str, tz_name: str) -> tuple[date, date]:
    """Parse '7d' / '30d' / '90d' / 'all' into (start, end) inclusive dates.

    'all' is represented by start = 1970-01-01.
    """
    today = today_in_tz(tz_name)
    p = period.strip().lower()
    if p == "all":
        return date(1970, 1, 1), today
    if p.endswith("d"):
        try:
            days = int(p[:-1])
        except ValueError as e:
            raise ValueError(f"Invalid period: {period}") from e
        if days <= 0:
            raise ValueError(f"Period must be positive: {period}")
        return today - timedelta(days=days - 1), today
    raise ValueError(f"Unknown period: {period}. Use 7d, 30d, 90d or all.")
